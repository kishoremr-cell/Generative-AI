import re
import uuid
from typing import Any, Dict, List


def determine_test_type(text: str) -> str:
    lower = text.lower()
    if any(keyword in lower for keyword in ["api", "endpoint", "http", "request", "response", "payload"]):
        return "API"
    if any(keyword in lower for keyword in ["ui", "screen", "page", "button", "modal", "dropdown", "click"]):
        return "UI"
    return "Functional"


def determine_case_category(text: str) -> str:
    lower = text.lower()
    if any(keyword in lower for keyword in ["invalid", "fail", "error", "reject", "unauthorized", "forbidden"]):
        return "Negative"
    if any(keyword in lower for keyword in ["boundary", "boundary value", "maximum", "minimum", "limit", "edge"]):
        return "Edge"
    return "Positive"


def build_preconditions(description: str, labels: List[str]) -> str:
    normalized = [label.lower() for label in labels]
    if any(keyword in description.lower() for keyword in ["logged in", "login", "authenticated"]):
        return "User is logged in with appropriate permissions."
    if any(keyword in normalized for keyword in ["authenticated", "login-required", "requires-login"]):
        return "User is logged in with appropriate permissions."
    return "Not Provided"


def normalize_lines(text: str) -> List[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def generate_test_cases(issue_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    criteria = issue_data.get("acceptanceCriteria") or []
    if not criteria and issue_data.get("description"):
        lines = normalize_lines(issue_data["description"])
        criteria = [line.lstrip("-*• ").strip() for line in lines if line.startswith(("-", "*", "•"))]
    if not criteria and issue_data.get("description"):
        description = issue_data["description"].strip()
        if description:
            criteria = [description]

    if not criteria:
        return []

    preconditions = build_preconditions(issue_data.get("description", ""), issue_data.get("labels", []))
    test_cases = []

    for index, criterion in enumerate(criteria, start=1):
        if not criterion:
            continue
        title = f"Verify: {criterion if len(criterion) <= 100 else criterion[:97] + '...'}"
        case_type = determine_test_type(criterion)
        category = determine_case_category(criterion)
        test_cases.append({
            "testCaseId": str(uuid.uuid4()),
            "title": title,
            "description": criterion,
            "preconditions": preconditions,
            "steps": [
                f"Review the acceptance criterion: {criterion}",
                "Execute the actions required by this criterion in the target system.",
            ],
            "expectedResult": criterion,
            "priority": issue_data.get("priority", "Not Provided"),
            "testType": case_type,
            "caseCategory": category,
            "sourceJiraId": issue_data.get("issueKey", "Not Provided"),
        })

    return test_cases


def normalize_issue_data(raw_issue: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "issueKey": raw_issue.get("issueKey", "Not Provided"),
        "summary": raw_issue.get("summary", "Not Provided"),
        "description": raw_issue.get("description", "Not Provided"),
        "acceptanceCriteria": raw_issue.get("acceptanceCriteria") or [],
        "priority": raw_issue.get("priority", "Not Provided"),
        "labels": raw_issue.get("labels") or [],
        "comments": raw_issue.get("comments") or [],
    }
