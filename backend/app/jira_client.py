import os
import re
import requests

from typing import Any, Dict, List


def get_jira_auth():
    email = os.getenv("JIRA_EMAIL")
    token = os.getenv("JIRA_API_TOKEN")
    if not email or not token:
        raise ValueError("JIRA_EMAIL and JIRA_API_TOKEN must be configured in environment variables.")
    return (email, token)


def format_description(description: Any) -> str:
    if not description:
        return "Not Provided"
    if isinstance(description, str):
        return description.strip() or "Not Provided"

    if isinstance(description, dict):
        content = []
        for block in description.get("content", []):
            if block.get("type") == "paragraph":
                for paragraph_part in block.get("content", []):
                    content.append(paragraph_part.get("text", ""))
            elif block.get("type") == "heading":
                for heading_part in block.get("content", []):
                    content.append(heading_part.get("text", ""))
            elif block.get("type") == "bulletList":
                for list_block in block.get("content", []):
                    if list_block.get("type") == "listItem":
                        item_text = []
                        for item_child in list_block.get("content", []):
                            for part in item_child.get("content", []):
                                item_text.append(part.get("text", ""))
                        content.append("- " + "".join(item_text))
        return "\n".join([line for line in content if line.strip()]) or "Not Provided"

    return "Not Provided"


def extract_acceptance_criteria(text: str) -> List[str]:
    if not text or text.strip() == "":
        return []

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    criteria = []
    capture = False

    for line in lines:
        lower = line.lower()
        if re.match(r"^acceptance criteria[:\-]*$", lower):
            capture = True
            continue
        if capture:
            if re.match(r"^[A-Za-z ].*:$", line) and not line.startswith("-"):
                # Stop capture when a new heading starts
                break
            if line.startswith("-") or line.startswith("*") or line.startswith("•"):
                criteria.append(line.lstrip("-*• ").strip())
            elif line:
                criteria.append(line)

    if not criteria:
        for line in lines:
            if line.startswith("-") or line.startswith("*") or line.startswith("•"):
                criteria.append(line.lstrip("-*• ").strip())
            elif re.match(r"^\d+\.", line):
                criteria.append(re.sub(r"^\d+\.\s*", "", line))

    return criteria


def fetch_issue(issue_key: str) -> Dict[str, Any]:
    base_url = os.getenv("JIRA_BASE_URL")
    if not base_url:
        raise ValueError("JIRA_BASE_URL must be configured in environment variables.")

    url = f"{base_url.rstrip('/')}/rest/api/3/issue/{issue_key}"
    params = {"fields": "summary,description,priority,labels,comment"}
    response = requests.get(url, auth=get_jira_auth(), headers={"Accept": "application/json"}, params=params, timeout=30)
    response.raise_for_status()
    data = response.json()
    fields = data.get("fields", {})

    description = format_description(fields.get("description"))
    labels = fields.get("labels") or []
    priority = fields.get("priority", {}).get("name") or "Not Provided"
    comments = []
    comment_data = fields.get("comment", {}).get("comments", [])
    for comment in comment_data:
        body = format_description(comment.get("body"))
        if body and body != "Not Provided":
            comments.append(body)

    return {
        "issueKey": issue_key,
        "summary": fields.get("summary") or "Not Provided",
        "description": description,
        "acceptanceCriteria": extract_acceptance_criteria(description),
        "priority": priority,
        "labels": labels,
        "comments": comments,
    }


def get_jira_projects() -> List[Dict[str, Any]]:
    """Get list of accessible Jira projects"""
    base_url = os.getenv("JIRA_BASE_URL")
    if not base_url:
        raise ValueError("JIRA_BASE_URL must be configured in environment variables.")

    url = f"{base_url.rstrip('/')}/rest/api/3/project"
    
    response = requests.get(
        url, 
        auth=get_jira_auth(), 
        headers={"Accept": "application/json"}, 
        timeout=30
    )
    response.raise_for_status()
    return response.json()


def get_jira_issue_types(project_key: str) -> List[Dict[str, Any]]:
    """Get issue types for a specific project"""
    base_url = os.getenv("JIRA_BASE_URL")
    if not base_url:
        raise ValueError("JIRA_BASE_URL must be configured in environment variables.")

    url = f"{base_url.rstrip('/')}/rest/api/3/project/{project_key}/statuses"
    
    response = requests.get(
        url, 
        auth=get_jira_auth(), 
        headers={"Accept": "application/json"}, 
        timeout=30
    )
    response.raise_for_status()
    data = response.json()
    
    # Extract unique issue types
    issue_types = {}
    for status_info in data:
        issue_type = status_info.get("statuses", [{}])[0].get("statusCategory", {}).get("name", "")
        if issue_type and status_info.get("name") not in issue_types:
            issue_types[status_info["name"]] = {
                "name": status_info["name"],
                "id": status_info["id"]
            }
    
    return list(issue_types.values())


def create_jira_issue(defect_data: Dict[str, Any]) -> Dict[str, Any]:
    base_url = os.getenv("JIRA_BASE_URL")
    if not base_url:
        raise ValueError("JIRA_BASE_URL must be configured in environment variables.")

    url = f"{base_url.rstrip('/')}/rest/api/2/issue"
    
    # Try to extract project key from defect_data, environment, or base URL
    project_key = defect_data.get("projectKey") or os.getenv("JIRA_PROJECT_KEY")
    if not project_key:
        # Try to extract from URL like https://company.atlassian.net/projects/PROJ
        import re
        match = re.search(r'/projects/([A-Z]+)', base_url)
        if match:
            project_key = match.group(1)
        else:
            # Default fallback - user should set JIRA_PROJECT_KEY
            project_key = "PROJ"
    
    # Build a comprehensive description with all defect details
    description_parts = []
    if defect_data.get("description"):
        description_parts.append(f"Description:\n{defect_data['description']}")
    
    if defect_data.get("stepsToReproduce"):
        description_parts.append(f"\n\nSteps to Reproduce:\n{defect_data['stepsToReproduce']}")
    
    if defect_data.get("expectedResult"):
        description_parts.append(f"\n\nExpected Result:\n{defect_data['expectedResult']}")
    
    if defect_data.get("actualResult"):
        description_parts.append(f"\n\nActual Result:\n{defect_data['actualResult']}")
    
    full_description = "\n".join(description_parts)
    
    # Build the issue payload for Jira - use simple text description
    issue_payload = {
        "fields": {
            "project": {
                "key": project_key
            },
            "summary": defect_data["summary"],
            "description": full_description,  # Use plain text description
            "issuetype": {
                "name": "Bug"  # Assuming defect is a Bug type
            }
        }
    }
    
    # Set priority if provided
    if defect_data.get("priority"):
        issue_payload["fields"]["priority"] = {"name": defect_data["priority"]}
    
    # Add severity as a label
    if defect_data.get("severity"):
        issue_payload["fields"]["labels"] = [f"Severity-{defect_data['severity']}"]
    
    try:
        response = requests.post(
            url, 
            auth=get_jira_auth(), 
            headers={"Content-Type": "application/json"}, 
            json=issue_payload, 
            timeout=30
        )
        response.raise_for_status()
        data = response.json()
        
        return {
            "issueKey": data.get("key"),
            "issueId": data.get("id"),
            "self": data.get("self"),
            "summary": defect_data["summary"],
            "status": "Created successfully"
        }
    except requests.exceptions.HTTPError as e:
        # Provide more detailed error information
        error_msg = f"Jira API Error: {e.response.status_code}"
        if e.response.text:
            try:
                error_data = e.response.json()
                if "errors" in error_data:
                    error_details = []
                    for field, msg in error_data["errors"].items():
                        error_details.append(f"{field}: {msg}")
                    error_msg += f" - {', '.join(error_details)}"
                elif "errorMessages" in error_data:
                    error_msg += f" - {', '.join(error_data['errorMessages'])}"
                else:
                    error_msg += f" - {e.response.text[:200]}"
            except:
                error_msg += f" - {e.response.text[:200]}"
        raise Exception(error_msg)
