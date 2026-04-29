from typing import List, Optional
from pydantic import BaseModel


class JiraFetchRequest(BaseModel):
    issueKey: str


class JiraIssueData(BaseModel):
    issueKey: str
    summary: str
    description: str
    acceptanceCriteria: List[str]
    priority: str
    labels: List[str]
    comments: List[str]


class TestCaseOutput(BaseModel):
    testCaseId: str
    title: str
    description: str
    preconditions: str
    steps: List[str]
    expectedResult: str
    priority: str
    testType: str
    sourceJiraId: str


class GenerateRequest(BaseModel):
    issueKey: str
    llmSource: str = "local"
    model: str = "phi3"
    jiraBaseUrl: str
    jiraEmail: str
    jiraApiToken: str
    customPrompt: Optional[str] = None
    apiKeys: Optional[Dict[str, str]] = None


class BulkGenerateRequest(BaseModel):
    issueKeys: List[str]
    llmSource: str = "local"
    jobName: Optional[str] = None


class CreateDefectRequest(BaseModel):
    summary: str
    description: str
    stepsToReproduce: str
    expectedResult: str
    actualResult: str
    severity: str = "Medium"
    priority: str = "Medium"
    jiraBaseUrl: str
    jiraEmail: str
    jiraApiToken: str


class GenerateDefectRequest(BaseModel):
    testCase: Dict[str, Any]
    issueData: Dict[str, Any]
    llmSource: str = "local"
    model: str = "phi3"
    apiKeys: Optional[Dict[str, str]] = None
    jiraBaseUrl: str
    jiraEmail: str
    jiraApiToken: str


class JobStatusResponse(BaseModel):
    jobId: str
    name: str
    status: str
    llmSource: str
    createdAt: str
    updatedAt: str
    tickets: List[TicketStatus]
    testCases: List[TestCaseOutput] = []
