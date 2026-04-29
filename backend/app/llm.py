import os
import json
import requests
from typing import Dict, List, Optional


def local_llm_generate(prompt: str, model: str = "phi3") -> str:
    ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
    payload = {
        "model": model,
        "prompt": prompt,
        "temperature": 0.0,
        "max_tokens": 800,
        "stream": False,
    }
    response = requests.post(ollama_url, json=payload, timeout=60)
    response.raise_for_status()
    data = response.json()
    if isinstance(data, dict):
        if "response" in data:
            return data["response"]
        if "results" in data and isinstance(data["results"], list) and len(data["results"]) > 0:
            first = data["results"][0]
            if isinstance(first, dict) and "output" in first:
                output = first["output"]
                if isinstance(output, dict) and "content" in output:
                    return output["content"]
                return json.dumps(output)
            if isinstance(first, dict) and "content" in first:
                return first["content"]
    return json.dumps(data)

def cloud_llm_generate(prompt: str, model: str = "openai", api_keys: Optional[Dict] = None) -> str:
    # Determine which API to use based on the model
    if model == "openai":
        api_key = api_keys.get("openaiKey") if api_keys else os.getenv("OPENAI_API_KEY")
        api_base = os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1")
        model_name = api_keys.get("openaiModel", "gpt-3.5-turbo") if api_keys else "gpt-3.5-turbo"
    elif model == "claude":
        api_key = api_keys.get("claudeKey") if api_keys else os.getenv("ANTHROPIC_API_KEY")
        api_base = "https://api.anthropic.com/v1"
        model_name = api_keys.get("claudeModel", "claude-3-sonnet-20240229") if api_keys else "claude-3-sonnet-20240229"
    elif model == "grok":
        api_key = api_keys.get("grokKey") if api_keys else os.getenv("GROK_API_KEY")
        api_base = os.getenv("GROK_API_BASE", "https://api.x.ai/v1")
        model_name = api_keys.get("grokModel", "grok-beta") if api_keys else "grok-beta"
    elif model == "groq":
        api_key = api_keys.get("groqKey") if api_keys else os.getenv("GROQ_API_KEY")
        api_base = os.getenv("GROQ_API_BASE", "https://api.groq.com/openai/v1")
        model_name = api_keys.get("groqModel", "llama-3.1-8b-instant") if api_keys else "llama-3.1-8b-instant"
    elif model == "mistral":
        api_key = api_keys.get("mistralKey") if api_keys else os.getenv("MISTRAL_API_KEY")
        api_base = "https://api.mistral.ai/v1"
        model_name = api_keys.get("mistralModel", "mistral-large-latest") if api_keys else "mistral-large-latest"
    elif model == "gemini":
        api_key = api_keys.get("geminiKey") if api_keys else os.getenv("GEMINI_API_KEY")
        # Gemini uses REST API different from chat/completions
        return _gemini_generate(prompt, api_key)
    else:
        # Default to OpenAI for backward compatibility
        api_key = api_keys.get("openaiKey") if api_keys else os.getenv("OPENAI_API_KEY")
        api_base = os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1")
        model_name = "gpt-3.5-turbo"

    if not api_key:
        raise ValueError(f"API key for {model} must be configured")

    # Special handling for Claude/Anthropic which uses different format
    if model == "claude":
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        body = {
            "model": model_name,
            "max_tokens": 800,
            "system": "You are a strict QA assistant. Use only the provided Jira issue data.",
            "messages": [
                {"role": "user", "content": prompt},
            ],
        }
        response = requests.post(f"{api_base}/messages", headers=headers, json=body, timeout=60)
        response.raise_for_status()
        data = response.json()
        content = data.get("content", [])
        if content and isinstance(content, list):
            return content[0].get("text", "")
        return ""
    elif model == "groq":
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        body = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": "You are a strict QA assistant. Use only the provided Jira issue data."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.0,
            "max_tokens": 800,
        }
        response = requests.post(f"{api_base.rstrip('/')}/chat/completions", headers=headers, json=body, timeout=60)
        response.raise_for_status()
        data = response.json()
        choices = data.get("choices", [])
        if not choices:
            raise ValueError(f"No response from Groq API.")
        return choices[0].get("message", {}).get("content", "")
    
    # Standard OpenAI-compatible format for other models
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    body = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": "You are a strict QA assistant. Use only the provided Jira issue data."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.0,
        "max_tokens": 800,
    }
    
    try:
        response = requests.post(f"{api_base.rstrip('/')}/chat/completions", headers=headers, json=body, timeout=60)
        response.raise_for_status()
        data = response.json()
        choices = data.get("choices", [])
        if not choices:
            raise ValueError(f"No response from {model} API.")
        return choices[0].get("message", {}).get("content", "")
    except requests.exceptions.HTTPError as e:
        error_detail = f"{model} API Error {e.response.status_code}"
        if e.response.text:
            error_detail += f": {e.response.text[:200]}"
        raise Exception(error_detail)


def _gemini_generate(prompt: str, api_key: str) -> str:
    """Generate response from Google Gemini API"""
    if not api_key:
        raise ValueError("Gemini API key must be configured")
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={api_key}"
    body = {
        "contents": [
            {
                "parts": [
                    {"text": f"You are a strict QA assistant. Use only the provided Jira issue data.\n\n{prompt}"}
                ]
            }
        ],
        "safetySettings": [
            {"category": "HARM_CATEGORY_UNSPECIFIED", "threshold": "BLOCK_NONE"}
        ],
    }
    
    response = requests.post(url, json=body, timeout=60)
    response.raise_for_status()
    data = response.json()
    candidates = data.get("candidates", [])
    if candidates:
        content = candidates[0].get("content", {})
        parts = content.get("parts", [])
        if parts:
            return parts[0].get("text", "")
    raise ValueError("No response from Gemini API.")


def generate_defect_details(test_case: Dict, issue_data: Dict, llm_source: str, model: str = "phi3", api_keys: Optional[Dict] = None) -> Dict[str, str]:
    """Generate defect details from a test case and issue data"""
    if llm_source not in {"local", "cloud"}:
        # Return basic defect details without AI enhancement
        return {
            "summary": f"Bug: {test_case.get('title', 'Test Case Failure')}",
            "description": f"Test case '{test_case.get('title', 'Unknown')}' failed during execution.",
            "steps_to_reproduce": "\n".join(test_case.get("steps", [])),
            "expected_result": test_case.get("expectedResult", "Test should pass"),
            "actual_result": "Test failed",
            "severity": "Medium",
            "priority": "Medium"
        }

    prompt = f"""
Based on the following Jira issue and failed test case, generate appropriate defect details.

Jira Issue:
- Summary: {issue_data.get('summary', 'Unknown')}
- Description: {issue_data.get('description', 'Not provided')}

Failed Test Case:
- Title: {test_case.get('title', 'Unknown')}
- Description: {test_case.get('description', 'Not provided')}
- Steps: {json.dumps(test_case.get('steps', []), ensure_ascii=False)}
- Expected Result: {test_case.get('expectedResult', 'Not provided')}

Generate defect details in JSON format with these fields:
- summary: A concise bug title (max 100 characters)
- description: Detailed description of the bug
- steps_to_reproduce: Clear reproduction steps
- expected_result: What should happen
- actual_result: What actually happened (assume test failure)
- severity: Low, Medium, or High
- priority: Low, Medium, or High

Output only valid JSON.
"""

    raw = local_llm_generate(prompt, model) if llm_source == "local" else cloud_llm_generate(prompt, model, api_keys)
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict) and "summary" in parsed:
            return parsed
    except json.JSONDecodeError:
        pass

    # Fallback to basic details
    return {
        "summary": f"Bug: {test_case.get('title', 'Test Case Failure')}",
        "description": f"Test case '{test_case.get('title', 'Unknown')}' failed during execution.",
        "steps_to_reproduce": "\n".join(test_case.get("steps", [])),
        "expected_result": test_case.get("expectedResult", "Test should pass"),
        "actual_result": "Test failed",
        "severity": "Medium",
        "priority": "Medium"
    }
    if llm_source not in {"local", "cloud"}:
        return testcases

    base_prompt = (
        "Given the Jira issue data and test case payload below, return the exact same list of test cases in JSON array format. "
        "Use only provided information and do not invent additional scenarios or fields. "
        "If any field is missing, leave it as 'Not Provided'.\n\n"
        f"Jira issue: {json.dumps(issue_data, ensure_ascii=False)}\n\n"
        f"Preliminary test cases: {json.dumps(testcases, ensure_ascii=False)}\n\n"
        "Output only valid JSON. Do not add any commentary."
    )

    # Add custom prompt if provided
    if custom_prompt and custom_prompt.strip():
        prompt = f"{custom_prompt}\n\n{base_prompt}"
    else:
        prompt = base_prompt

    raw = local_llm_generate(prompt, model) if llm_source == "local" else cloud_llm_generate(prompt, model, api_keys)
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return parsed
    except json.JSONDecodeError:
        pass
    return testcases


def format_testcases_with_llm(testcases: List[Dict], issue_data: Dict, llm_source: str, model: str = "phi3", api_keys: Optional[Dict] = None, custom_prompt: Optional[str] = None) -> List[Dict]:
    """Format test cases using LLM enhancement"""
    if llm_source not in {"local", "cloud"}:
        return testcases

    base_prompt = (
        "Given the Jira issue data and test case payload below, return the exact same list of test cases in JSON array format. "
        "Use only provided information and do not invent additional scenarios or fields. "
        "If any field is missing, leave it as 'Not Provided'.\n\n"
        f"Jira issue: {json.dumps(issue_data, ensure_ascii=False)}\n\n"
        f"Preliminary test cases: {json.dumps(testcases, ensure_ascii=False)}\n\n"
        "Output only valid JSON. Do not add any commentary."
    )

    # Add custom prompt if provided
    if custom_prompt and custom_prompt.strip():
        prompt = f"{custom_prompt}\n\n{base_prompt}"
    else:
        prompt = base_prompt

    raw = local_llm_generate(prompt, model) if llm_source == "local" else cloud_llm_generate(prompt, model, api_keys)
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return parsed
    except json.JSONDecodeError:
        pass
    return testcases
