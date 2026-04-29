import io
import json
import uuid
from datetime import datetime
from typing import List

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from sqlalchemy.orm import Session

from app.db import get_db, init_db
from app.generator import generate_test_cases, normalize_issue_data
from app.jira_client import fetch_issue, create_jira_issue, get_jira_projects, get_jira_issue_types
from app.llm import format_testcases_with_llm, generate_defect_details
from app.models import Job, Ticket, TestCase
from app.schemas import (
    BulkGenerateRequest,
    GenerateRequest,
    JiraFetchRequest,
    JobStatusResponse,
    TestCaseOutput,
    TicketStatus,
    CreateDefectRequest,
    GenerateDefectRequest,
)

app = FastAPI(title="Jira QA Assistant")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup_event():
    init_db()


def create_job(db: Session, name: str, llm_source: str) -> Job:
    job = Job(
        id=str(uuid.uuid4()),
        name=name,
        status="pending",
        llm_source=llm_source,
        error_message=None,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def create_ticket_placeholder(db: Session, job_id: str, issue_key: str) -> Ticket:
    ticket = Ticket(
        id=str(uuid.uuid4()),
        job_id=job_id,
        issue_key=issue_key,
        summary="Pending Jira fetch",
        description="Not Provided",
        acceptance_criteria="Not Provided",
        priority="Not Provided",
        labels="",
        comments="",
        status="pending",
        error_message=None,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    return ticket


def update_ticket_with_issue(db: Session, ticket: Ticket, issue_data: dict) -> Ticket:
    ticket.summary = issue_data.get("summary", "Not Provided")
    ticket.description = issue_data.get("description", "Not Provided")
    ticket.acceptance_criteria = "\n".join(issue_data.get("acceptanceCriteria", [])) or "Not Provided"
    ticket.priority = issue_data.get("priority", "Not Provided")
    ticket.labels = ",".join(issue_data.get("labels", []))
    ticket.comments = "\n\n".join(issue_data.get("comments", []))
    ticket.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(ticket)
    return ticket


def save_test_cases(db: Session, ticket: Ticket, test_cases: List[dict]) -> None:
    for case in test_cases:
        db.add(
            TestCase(
                id=case.get("testCaseId", str(uuid.uuid4())),
                ticket_id=ticket.id,
                source_issue_key=ticket.issue_key,
                title=case.get("title", "Not Provided"),
                description=case.get("description", "Not Provided"),
                preconditions=case.get("preconditions", "Not Provided"),
                steps=json.dumps(case.get("steps", []), ensure_ascii=False),
                expected_result=case.get("expectedResult", "Not Provided"),
                priority=case.get("priority", "Not Provided"),
                test_type=case.get("testType", "Functional"),
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
        )
    db.commit()


def update_job_status(db: Session, job: Job) -> None:
    statuses = {ticket.status for ticket in job.tickets}
    if "in_progress" in statuses:
        job.status = "in_progress"
    elif statuses == {"failed"}:
        job.status = "failed"
    elif statuses.issubset({"completed", "failed"}) and "completed" in statuses:
        job.status = "completed"
    else:
        job.status = "pending"
    job.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(job)


def process_single_ticket(job_id: str, issue_key: str, llm_source: str) -> None:
    db = next(get_db())
    job = None
    try:
        job = db.get(Job, job_id)
        ticket = db.query(Ticket).filter(Ticket.job_id == job_id, Ticket.issue_key == issue_key).first()
        if not ticket:
            ticket = create_ticket_placeholder(db, job_id, issue_key)

        ticket.status = "in_progress"
        ticket.updated_at = datetime.utcnow()
        db.commit()

        issue_data = fetch_issue(issue_key)
        update_ticket_with_issue(db, ticket, issue_data)

        normalized = normalize_issue_data(issue_data)
        preliminary_cases = generate_test_cases(normalized)
        formatted_cases = format_testcases_with_llm(preliminary_cases, normalized, llm_source)

        save_test_cases(db, ticket, formatted_cases)
        ticket.status = "completed"
        ticket.error_message = None
        ticket.updated_at = datetime.utcnow()
        db.commit()
    except Exception as error:
        if "ticket" in locals():
            ticket.status = "failed"
            ticket.error_message = str(error)
            ticket.updated_at = datetime.utcnow()
            db.commit()
    finally:
        if job is not None:
            update_job_status(db, job)
        db.close()


def finalize_job(job_id: str) -> None:
    db = next(get_db())
    try:
        job = db.get(Job, job_id)
        if job:
            update_job_status(db, job)
    finally:
        db.close()


@app.post("/fetch-jira")
def fetch_jira(payload: JiraFetchRequest):
    try:
        issue = fetch_issue(payload.issueKey.strip())
        return issue
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/generate-testcases")
def generate_testcases_route(payload: GenerateRequest):
    try:
        # Set Jira environment variables for this request
        import os
        original_env = {}
        env_vars = {
            'JIRA_BASE_URL': payload.jiraBaseUrl,
            'JIRA_EMAIL': payload.jiraEmail,
            'JIRA_API_TOKEN': payload.jiraApiToken
        }
        
        # Store original values and set new ones
        for key, value in env_vars.items():
            original_env[key] = os.environ.get(key)
            os.environ[key] = value
        
        # Set API keys for cloud models
        if payload.apiKeys:
            api_env_vars = {
                'OPENAI_API_KEY': payload.apiKeys.get('openaiKey'),
                'GEMINI_API_KEY': payload.apiKeys.get('geminiKey'),
                'GROK_API_KEY': payload.apiKeys.get('grokKey'),
                'GROQ_API_KEY': payload.apiKeys.get('groqKey')
            }
            for key, value in api_env_vars.items():
                if value:
                    original_env[key] = os.environ.get(key)
                    os.environ[key] = value
        
        try:
            issue_data = fetch_issue(payload.issueKey.strip())
            normalized = normalize_issue_data(issue_data)
            test_cases = generate_test_cases(normalized)
            formatted = format_testcases_with_llm(test_cases, normalized, payload.llmSource, payload.model, payload.apiKeys, payload.customPrompt)
            return {"issueKey": payload.issueKey.strip(), "testCases": formatted}
        finally:
            # Restore original environment variables
            for key, value in original_env.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
                    
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/bulk-generate")
def bulk_generate(payload: BulkGenerateRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    issue_keys = [key.strip() for key in payload.issueKeys if key and key.strip()]
    if not issue_keys:
        raise HTTPException(status_code=400, detail="At least one Jira issue key is required.")

    job = create_job(db, payload.jobName or "Bulk Jira Test Generation", payload.llmSource)
    for issue_key in issue_keys:
        create_ticket_placeholder(db, job.id, issue_key)

    for issue_key in issue_keys:
        background_tasks.add_task(process_single_ticket, job.id, issue_key, payload.llmSource)

    background_tasks.add_task(finalize_job, job.id)
    return {"jobId": job.id}


@app.get("/job-status/{job_id}")
def job_status(job_id: str, db: Session = Depends(get_db)):
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")

    ticket_statuses = [
        TicketStatus(issueKey=ticket.issue_key, status=ticket.status, errorMessage=ticket.error_message)
        for ticket in job.tickets
    ]

    test_cases = []
    for ticket in job.tickets:
        for case in ticket.test_cases:
            test_cases.append(
                TestCaseOutput(
                    testCaseId=case.id,
                    title=case.title,
                    description=case.description,
                    preconditions=case.preconditions,
                    steps=json.loads(case.steps or "[]"),
                    expectedResult=case.expected_result,
                    priority=case.priority,
                    testType=case.test_type,
                    sourceJiraId=case.source_issue_key,
                )
            )

    return JobStatusResponse(
        jobId=job.id,
        name=job.name,
        status=job.status,
        llmSource=job.llm_source,
        createdAt=job.created_at.isoformat(),
        updatedAt=job.updated_at.isoformat(),
        tickets=ticket_statuses,
        testCases=test_cases,
    )


@app.post("/jira-projects")
def get_projects(payload: JiraFetchRequest):
    try:
        # Set Jira environment variables for this request
        import os
        original_env = {}
        env_vars = {
            'JIRA_BASE_URL': payload.jiraBaseUrl,
            'JIRA_EMAIL': payload.jiraEmail,
            'JIRA_API_TOKEN': payload.jiraApiToken
        }
        
        # Store original values and set new ones
        for key, value in env_vars.items():
            original_env[key] = os.environ.get(key)
            os.environ[key] = value
        
        try:
            projects = get_jira_projects()
            return projects
        finally:
            # Restore original environment variables
            for key, value in original_env.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
                    
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/jira-issue-types/{project_key}")
def get_issue_types(project_key: str, payload: JiraFetchRequest):
    try:
        # Set Jira environment variables for this request
        import os
        original_env = {}
        env_vars = {
            'JIRA_BASE_URL': payload.jiraBaseUrl,
            'JIRA_EMAIL': payload.jiraEmail,
            'JIRA_API_TOKEN': payload.jiraApiToken
        }
        
        # Store original values and set new ones
        for key, value in env_vars.items():
            original_env[key] = os.environ.get(key)
            os.environ[key] = value
        
        try:
            issue_types = get_jira_issue_types(project_key)
            return issue_types
        finally:
            # Restore original environment variables
            for key, value in original_env.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
                    
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/generate-defect")
def generate_defect(payload: GenerateDefectRequest):
    try:
        # Set Jira environment variables for this request
        import os
        original_env = {}
        env_vars = {
            'JIRA_BASE_URL': payload.jiraBaseUrl,
            'JIRA_EMAIL': payload.jiraEmail,
            'JIRA_API_TOKEN': payload.jiraApiToken
        }
        
        # Store original values and set new ones
        for key, value in env_vars.items():
            original_env[key] = os.environ.get(key)
            os.environ[key] = value
        
        # Set API keys for cloud models
        if payload.apiKeys:
            api_env_vars = {
                'OPENAI_API_KEY': payload.apiKeys.get('openaiKey'),
                'GEMINI_API_KEY': payload.apiKeys.get('geminiKey'),
                'GROK_API_KEY': payload.apiKeys.get('grokKey'),
                'GROQ_API_KEY': payload.apiKeys.get('groqKey'),
                'ANTHROPIC_API_KEY': payload.apiKeys.get('claudeKey'),
                'MISTRAL_API_KEY': payload.apiKeys.get('mistralKey')
            }
            for key, value in api_env_vars.items():
                if value:
                    original_env[key] = os.environ.get(key)
                    os.environ[key] = value
        
        try:
            defect_details = generate_defect_details(payload.testCase, payload.issueData, payload.llmSource, payload.model, payload.apiKeys)
            return defect_details
        finally:
            # Restore original environment variables
            for key, value in original_env.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
                    
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/create-defect")
def create_defect(payload: CreateDefectRequest):
    try:
        # Set Jira environment variables for this request
        import os
        original_env = {}
        env_vars = {
            'JIRA_BASE_URL': payload.jiraBaseUrl,
            'JIRA_EMAIL': payload.jiraEmail,
            'JIRA_API_TOKEN': payload.jiraApiToken
        }
        
        # Store original values and set new ones
        for key, value in env_vars.items():
            original_env[key] = os.environ.get(key)
            os.environ[key] = value
        
        try:
            defect_data = {
                "summary": payload.summary,
                "description": payload.description,
                "stepsToReproduce": payload.stepsToReproduce,
                "expectedResult": payload.expectedResult,
                "actualResult": payload.actualResult,
                "severity": payload.severity,
                "priority": payload.priority
            }
            
            result = create_jira_issue(defect_data)
            return result
        finally:
            # Restore original environment variables
            for key, value in original_env.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
                    
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/export/{job_id}")
def export_job(job_id: str, format: str = Query("json", regex="^(json|xlsx|pdf)$"), db: Session = Depends(get_db)):
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")

    rows = []
    for ticket in job.tickets:
        for case in ticket.test_cases:
            rows.append(
                {
                    "testCaseId": case.id,
                    "sourceJiraId": case.source_issue_key,
                    "title": case.title,
                    "description": case.description,
                    "preconditions": case.preconditions,
                    "steps": json.loads(case.steps or "[]"),
                    "expectedResult": case.expected_result,
                    "priority": case.priority,
                    "testType": case.test_type,
                }
            )

    if format == "json":
        return JSONResponse(rows)

    if format == "xlsx":
        try:
            import xlsxwriter
        except ImportError:
            raise HTTPException(status_code=500, detail="xlsxwriter is required for Excel export.")

        buffer = io.BytesIO()
        workbook = xlsxwriter.Workbook(buffer, {"in_memory": True})
        sheet = workbook.add_worksheet("TestCases")
        headers = ["TestCase ID", "Jira ID", "Title", "Priority", "Test Type", "Preconditions", "Steps", "Expected Result"]
        for col, header in enumerate(headers):
            sheet.write(0, col, header)

        for row_index, row in enumerate(rows, start=1):
            sheet.write(row_index, 0, row["testCaseId"])
            sheet.write(row_index, 1, row["sourceJiraId"])
            sheet.write(row_index, 2, row["title"])
            sheet.write(row_index, 3, row["priority"])
            sheet.write(row_index, 4, row["testType"])
            sheet.write(row_index, 5, row["preconditions"])
            sheet.write(row_index, 6, json.dumps(row["steps"], ensure_ascii=False))
            sheet.write(row_index, 7, row["expectedResult"])

        workbook.close()
        buffer.seek(0)
        return StreamingResponse(buffer, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": f"attachment; filename=job_{job_id}.xlsx"})

    buffer = io.BytesIO()
    pdf_canvas = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    y = height - 40
    pdf_canvas.setFont("Helvetica-Bold", 14)
    pdf_canvas.drawString(40, y, f"QA Test Cases - Job {job.id}")
    y -= 30
    pdf_canvas.setFont("Helvetica", 10)

    for row in rows:
        if y < 100:
            pdf_canvas.showPage()
            y = height - 40
            pdf_canvas.setFont("Helvetica", 10)

        pdf_canvas.drawString(40, y, f"{row['sourceJiraId']} - {row['testCaseId']}")
        y -= 16
        pdf_canvas.drawString(60, y, f"Title: {row['title']}")
        y -= 14
        pdf_canvas.drawString(60, y, f"Priority: {row['priority']} | Type: {row['testType']}")
        y -= 14
        pdf_canvas.drawString(60, y, f"Preconditions: {row['preconditions']}")
        y -= 14
        pdf_canvas.drawString(60, y, f"Expected Result: {row['expectedResult']}")
        y -= 22

    pdf_canvas.save()
    buffer.seek(0)
    return StreamingResponse(buffer, media_type="application/pdf", headers={"Content-Disposition": f"attachment; filename=job_{job_id}.pdf"})
