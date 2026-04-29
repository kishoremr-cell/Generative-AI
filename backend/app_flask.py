"""Flask wrapper for QA Assistant - Python 3.14 compatible"""
from flask import Flask, request, jsonify
from flask_cors import CORS
import json
import os
import requests
from dotenv import load_dotenv

# Import core business logic from backend modules
from app.jira_client import fetch_issue, create_jira_issue, get_jira_projects, get_jira_issue_types
from app.generator import generate_test_cases, normalize_issue_data
from app.llm import format_testcases_with_llm, generate_defect_details

load_dotenv()

app = Flask(__name__)
CORS(app)

@app.route('/fetch-jira', methods=['POST'])
def fetch_jira():
    try:
        data = request.get_json()
        issue_key = data.get('issueKey', '').strip()
        jira_base_url = data.get('jiraBaseUrl', '').strip()
        jira_email = data.get('jiraEmail', '').strip()
        jira_api_token = data.get('jiraApiToken', '').strip()
        
        if not issue_key:
            return jsonify({"error": "Issue key required"}), 400
        if not jira_base_url or not jira_email or not jira_api_token:
            return jsonify({"error": "Jira credentials required"}), 400
        
        # Temporarily set environment variables for this request
        import os
        os.environ['JIRA_BASE_URL'] = jira_base_url
        os.environ['JIRA_EMAIL'] = jira_email
        os.environ['JIRA_API_TOKEN'] = jira_api_token
        
        issue = fetch_issue(issue_key)
        return jsonify(issue)
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/generate-with-llm', methods=['POST'])
def generate_with_llm():
    try:
        data = request.get_json()
        issue_key = data.get('issueKey', '').strip()
        llm_source = data.get('llmSource', 'local')  # 'local' or 'cloud'
        jira_base_url = data.get('jiraBaseUrl', '').strip()
        jira_email = data.get('jiraEmail', '').strip()
        jira_api_token = data.get('jiraApiToken', '').strip()
        custom_prompt = data.get('customPrompt')
        api_keys = data.get('apiKeys', {})
        
        if not issue_key:
            return jsonify({"error": "Issue key required"}), 400
        if not jira_base_url or not jira_email or not jira_api_token:
            return jsonify({"error": "Jira credentials required"}), 400
        
        # Temporarily set environment variables for this request
        original_env = {
            'JIRA_BASE_URL': os.environ.get('JIRA_BASE_URL'),
            'JIRA_EMAIL': os.environ.get('JIRA_EMAIL'),
            'JIRA_API_TOKEN': os.environ.get('JIRA_API_TOKEN'),
            'OPENAI_API_KEY': os.environ.get('OPENAI_API_KEY'),
            'GEMINI_API_KEY': os.environ.get('GEMINI_API_KEY'),
            'GROK_API_KEY': os.environ.get('GROK_API_KEY'),
            'GROQ_API_KEY': os.environ.get('GROQ_API_KEY'),
            'ANTHROPIC_API_KEY': os.environ.get('ANTHROPIC_API_KEY'),
            'MISTRAL_API_KEY': os.environ.get('MISTRAL_API_KEY'),
        }
        os.environ['JIRA_BASE_URL'] = jira_base_url
        os.environ['JIRA_EMAIL'] = jira_email
        os.environ['JIRA_API_TOKEN'] = jira_api_token
        
        # Set API keys for cloud models
        if api_keys:
            if api_keys.get('openaiKey'):
                os.environ['OPENAI_API_KEY'] = api_keys['openaiKey']
            if api_keys.get('geminiKey'):
                os.environ['GEMINI_API_KEY'] = api_keys['geminiKey']
            if api_keys.get('grokKey'):
                os.environ['GROK_API_KEY'] = api_keys['grokKey']
            if api_keys.get('groqKey'):
                os.environ['GROQ_API_KEY'] = api_keys['groqKey']
            if api_keys.get('claudeKey'):
                os.environ['ANTHROPIC_API_KEY'] = api_keys['claudeKey']
            if api_keys.get('mistralKey'):
                os.environ['MISTRAL_API_KEY'] = api_keys['mistralKey']

        try:
            issue_data = fetch_issue(issue_key)
            normalized = normalize_issue_data(issue_data)
            test_cases = generate_test_cases(normalized)
            
            # Enhance with LLM if requested
            if llm_source in ['local', 'cloud']:
                if llm_source == 'local':
                    model = data.get('ollamaModel', 'phi3')
                else:
                    model = data.get('model', 'openai')
                try:
                    enhanced_test_cases = format_testcases_with_llm(test_cases, normalized, llm_source, model, api_keys, custom_prompt)
                    return jsonify({"issueKey": issue_key, "testCases": enhanced_test_cases})
                except requests.exceptions.HTTPError as e:
                    return jsonify({"error": f"LLM API HTTP error: {e.response.status_code} - {e.response.text}"}), 502
                except requests.exceptions.RequestException as e:
                    return jsonify({"error": f"LLM request error: {str(e)}"}), 502
                except Exception as e:
                    return jsonify({"error": f"LLM processing error: {str(e)}"}), 500
            else:
                return jsonify({"issueKey": issue_key, "testCases": test_cases})
        finally:
            # Restore original environment variables
            for key, value in original_env.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 401:
            return jsonify({"error": "Invalid Jira credentials. Please check your email and API token."}), 401
        elif e.response.status_code == 404:
            return jsonify({"error": f"Jira issue '{issue_key}' not found. Please check the issue key and ensure you have access to this project."}), 404
        else:
            return jsonify({"error": f"Jira API error: {str(e)}"}), 400
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500

@app.route('/generate-defect', methods=['POST'])
def generate_defect():
    try:
        data = request.get_json()
        test_case = data.get('testCase', {})
        issue_data = data.get('issueData', {})
        llm_source = data.get('llmSource', 'local')
        model = data.get('model', 'phi3')
        api_keys = data.get('apiKeys', {})
        jira_base_url = data.get('jiraBaseUrl', '').strip()
        jira_email = data.get('jiraEmail', '').strip()
        jira_api_token = data.get('jiraApiToken', '').strip()
        
        if not jira_base_url or not jira_email or not jira_api_token:
            return jsonify({"error": "Jira credentials required"}), 400
        
        # Temporarily set environment variables for this request
        original_env = {
            'JIRA_BASE_URL': os.environ.get('JIRA_BASE_URL'),
            'JIRA_EMAIL': os.environ.get('JIRA_EMAIL'),
            'JIRA_API_TOKEN': os.environ.get('JIRA_API_TOKEN'),
            'OPENAI_API_KEY': os.environ.get('OPENAI_API_KEY'),
            'GEMINI_API_KEY': os.environ.get('GEMINI_API_KEY'),
            'GROK_API_KEY': os.environ.get('GROK_API_KEY'),
            'GROQ_API_KEY': os.environ.get('GROQ_API_KEY'),
            'ANTHROPIC_API_KEY': os.environ.get('ANTHROPIC_API_KEY'),
            'MISTRAL_API_KEY': os.environ.get('MISTRAL_API_KEY'),
        }
        os.environ['JIRA_BASE_URL'] = jira_base_url
        os.environ['JIRA_EMAIL'] = jira_email
        os.environ['JIRA_API_TOKEN'] = jira_api_token
        
        # Set API keys for cloud models
        if api_keys:
            if api_keys.get('openaiKey'):
                os.environ['OPENAI_API_KEY'] = api_keys['openaiKey']
            if api_keys.get('geminiKey'):
                os.environ['GEMINI_API_KEY'] = api_keys['geminiKey']
            if api_keys.get('grokKey'):
                os.environ['GROK_API_KEY'] = api_keys['grokKey']
            if api_keys.get('groqKey'):
                os.environ['GROQ_API_KEY'] = api_keys['groqKey']
            if api_keys.get('claudeKey'):
                os.environ['ANTHROPIC_API_KEY'] = api_keys['claudeKey']
            if api_keys.get('mistralKey'):
                os.environ['MISTRAL_API_KEY'] = api_keys['mistralKey']

        try:
            defect_details = generate_defect_details(test_case, issue_data, llm_source, model, api_keys)
            return jsonify(defect_details)
        finally:
            # Restore original environment variables
            for key, value in original_env.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
    except Exception as e:
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500

@app.route('/create-defect', methods=['POST'])
def create_defect():
    try:
        data = request.get_json()
        summary = data.get('summary', '').strip()
        description = data.get('description', '').strip()
        steps_to_reproduce = data.get('stepsToReproduce', '').strip()
        expected_result = data.get('expectedResult', '').strip()
        actual_result = data.get('actualResult', '').strip()
        project_key = data.get('projectKey', '').strip()
        severity = data.get('severity', 'Medium')
        priority = data.get('priority', 'Medium')
        jira_base_url = data.get('jiraBaseUrl', '').strip()
        jira_email = data.get('jiraEmail', '').strip()
        jira_api_token = data.get('jiraApiToken', '').strip()
        
        if not summary or not description:
            return jsonify({"error": "Summary and description are required"}), 400
        if not jira_base_url or not jira_email or not jira_api_token:
            return jsonify({"error": "Jira credentials required"}), 400
        
        # Temporarily set environment variables for this request
        original_env = {
            'JIRA_BASE_URL': os.environ.get('JIRA_BASE_URL'),
            'JIRA_EMAIL': os.environ.get('JIRA_EMAIL'),
            'JIRA_API_TOKEN': os.environ.get('JIRA_API_TOKEN'),
        }
        os.environ['JIRA_BASE_URL'] = jira_base_url
        os.environ['JIRA_EMAIL'] = jira_email
        os.environ['JIRA_API_TOKEN'] = jira_api_token
        
        try:
            defect_data = {
                "projectKey": project_key,
                "summary": summary,
                "description": description,
                "stepsToReproduce": steps_to_reproduce,
                "expectedResult": expected_result,
                "actualResult": actual_result,
                "severity": severity,
                "priority": priority
            }
            
            result = create_jira_issue(defect_data)
            return jsonify(result)
        finally:
            # Restore original environment variables
            for key, value in original_env.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
    except Exception as e:
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500

@app.route('/jira-projects', methods=['POST'])
def get_projects():
    try:
        data = request.get_json()
        jira_base_url = data.get('jiraBaseUrl', '').strip()
        jira_email = data.get('jiraEmail', '').strip()
        jira_api_token = data.get('jiraApiToken', '').strip()
        
        if not jira_base_url or not jira_email or not jira_api_token:
            return jsonify({"error": "Jira credentials required"}), 400
        
        # Temporarily set environment variables for this request
        original_env = {
            'JIRA_BASE_URL': os.environ.get('JIRA_BASE_URL'),
            'JIRA_EMAIL': os.environ.get('JIRA_EMAIL'),
            'JIRA_API_TOKEN': os.environ.get('JIRA_API_TOKEN'),
        }
        os.environ['JIRA_BASE_URL'] = jira_base_url
        os.environ['JIRA_EMAIL'] = jira_email
        os.environ['JIRA_API_TOKEN'] = jira_api_token
        
        try:
            projects = get_jira_projects()
            return jsonify(projects)
        finally:
            # Restore original environment variables
            for key, value in original_env.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
    except Exception as e:
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500

@app.route('/jira-issue-types/<project_key>', methods=['POST'])
def get_issue_types(project_key):
    try:
        data = request.get_json()
        jira_base_url = data.get('jiraBaseUrl', '').strip()
        jira_email = data.get('jiraEmail', '').strip()
        jira_api_token = data.get('jiraApiToken', '').strip()
        
        if not jira_base_url or not jira_email or not jira_api_token:
            return jsonify({"error": "Jira credentials required"}), 400
        
        # Temporarily set environment variables for this request
        original_env = {
            'JIRA_BASE_URL': os.environ.get('JIRA_BASE_URL'),
            'JIRA_EMAIL': os.environ.get('JIRA_EMAIL'),
            'JIRA_API_TOKEN': os.environ.get('JIRA_API_TOKEN'),
        }
        os.environ['JIRA_BASE_URL'] = jira_base_url
        os.environ['JIRA_EMAIL'] = jira_email
        os.environ['JIRA_API_TOKEN'] = jira_api_token
        
        try:
            issue_types = get_jira_issue_types(project_key)
            return jsonify(issue_types)
        finally:
            # Restore original environment variables
            for key, value in original_env.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
    except Exception as e:
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500

@app.route('/list-requirements', methods=['GET'])
def list_requirements():
    try:
        req_dir = os.path.join(os.path.dirname(__file__), '..', 'frontend', 'Requirement')
        if not os.path.exists(req_dir):
            return jsonify([])
        files = [f for f in os.listdir(req_dir) if f.endswith('.xlsx')]
        return jsonify(files)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/parse-requirement', methods=['POST'])
def parse_requirement():
    try:
        data = request.get_json()
        filename = data.get('filename')
        if not filename:
            return jsonify({"error": "Filename required"}), 400
            
        filepath = os.path.join(os.path.dirname(__file__), '..', 'frontend', 'Requirement', filename)
        if not os.path.exists(filepath):
            return jsonify({"error": "File not found"}), 404
            
        import openpyxl
        wb = openpyxl.load_workbook(filepath, data_only=True)
        text_content = []
        for sheet in wb.worksheets:
            for row in sheet.iter_rows(values_only=True):
                row_texts = [str(cell).strip() for cell in row if cell is not None and str(cell).strip()]
                if row_texts:
                    text_content.append(" | ".join(row_texts))
                    
        return jsonify({"content": "\n".join(text_content)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/generate-from-text', methods=['POST'])
def generate_from_text():
    try:
        data = request.get_json()
        content = data.get('content', '').strip()
        llm_source = data.get('llmSource', 'local')
        custom_prompt = data.get('customPrompt')
        api_keys = data.get('apiKeys', {})
        
        if not content:
            return jsonify({"error": "Content required"}), 400
            
        # Temporarily set environment variables
        original_env = {}
        for k in ['OPENAI_API_KEY', 'GEMINI_API_KEY', 'GROK_API_KEY', 'GROQ_API_KEY', 'ANTHROPIC_API_KEY', 'MISTRAL_API_KEY']:
            original_env[k] = os.environ.get(k)
            
        if api_keys:
            if api_keys.get('openaiKey'): os.environ['OPENAI_API_KEY'] = api_keys['openaiKey']
            if api_keys.get('geminiKey'): os.environ['GEMINI_API_KEY'] = api_keys['geminiKey']
            if api_keys.get('grokKey'): os.environ['GROK_API_KEY'] = api_keys['grokKey']
            if api_keys.get('groqKey'): os.environ['GROQ_API_KEY'] = api_keys['groqKey']
            if api_keys.get('claudeKey'): os.environ['ANTHROPIC_API_KEY'] = api_keys['claudeKey']
            if api_keys.get('mistralKey'): os.environ['MISTRAL_API_KEY'] = api_keys['mistralKey']

        try:
            issue_data = {
                "issueKey": "REQ-DOC",
                "summary": "Requirement Document",
                "description": content,
                "acceptanceCriteria": [],
                "priority": "Medium",
                "labels": [],
                "comments": []
            }
            test_cases = generate_test_cases(issue_data)
            
            if llm_source in ['local', 'cloud']:
                model = data.get('ollamaModel', 'phi3') if llm_source == 'local' else data.get('model', 'openai')
                enhanced_test_cases = format_testcases_with_llm(test_cases, issue_data, llm_source, model, api_keys, custom_prompt)
                return jsonify({"issueKey": "REQ-DOC", "testCases": enhanced_test_cases})
            else:
                return jsonify({"issueKey": "REQ-DOC", "testCases": test_cases})
        finally:
            for key, value in original_env.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True)
