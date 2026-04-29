# QA AI Assistant

A powerful, AI-driven Quality Assurance web application that streamlines the test creation process. It integrates directly with Jira and various Large Language Models (LLMs) to automatically generate comprehensive test cases and log defects.

## 🚀 Features

- **Jira Integration**: Fetch Jira tickets, including summaries, descriptions, and acceptance criteria.
- **Local Document Parsing**: Upload and parse local Excel (`.xlsx`) requirement documents to extract testable features directly from your file system.
- **AI-Powered Test Generation**: Automatically generate positive, negative, and edge test cases based on ticket criteria or document requirements.
- **Multi-Model Support**: 
  - **Local**: Support for offline execution via [Ollama](https://ollama.ai/).
  - **Cloud**: Integration with OpenAI, Anthropic (Claude), Google (Gemini), Grok, Groq, and Mistral.
- **Defect Logging**: One-click defect generation using AI to format the bug report, which can be pushed directly to Jira.
- **Global Settings Management**: Save your API keys, Jira credentials, and default project keys across sessions.

## 🏗️ Architecture

- **Frontend**: React.js (Bootstrapped with Create React App)
- **Backend**: Python / Flask
- **Data/Docs Parsing**: `openpyxl` for Excel spreadsheets
- **Integration**: Atlassian Jira REST API (v2 & v3)

## ⚙️ Setup Instructions

### Prerequisites
1. Node.js (v16+)
2. Python (v3.8+)
3. *Optional*: [Ollama](https://ollama.ai/) installed locally for offline LLM execution.

### Backend Setup

1. Navigate to the `backend` directory:
   ```bash
   cd backend
   ```
2. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Set up your environment variables. Create a `.env` file in the `backend` directory:
   ```env
   JIRA_BASE_URL=https://your-domain.atlassian.net
   JIRA_EMAIL=your-email@example.com
   JIRA_API_TOKEN=your-api-token
   # Optional Cloud API Keys (can also be configured via the UI)
   OPENAI_API_KEY=sk-...
   ```
4. Run the Flask server:
   ```bash
   python app_flask.py
   ```
   *The backend will run on `http://127.0.0.1:8000`*

### Frontend Setup

1. Navigate to the `frontend` directory:
   ```bash
   cd frontend
   ```
2. Install Node dependencies:
   ```bash
   npm install
   ```
3. Start the React development server:
   ```bash
   npm start
   ```
   *The frontend will open automatically at `http://localhost:3001`*

## 💡 Usage Guide

1. **Configure Settings**: Click the ⚙️ icon in the top right to set your Jira credentials and API keys. These are saved to your local storage.
2. **Fetch Requirements**:
   - **Jira**: Select "Jira Ticket", enter an issue key (e.g., `PROJ-123`), and click "Fetch".
   - **Document**: Select "Local Document", choose an Excel file from the `Requirement` folder, and click "Parse Document".
3. **Generate Tests**: Review the extracted content in the "Editable Content" section, select your preferred AI model, and click "Generate".
4. **Log Defects**: If a generated test case fails during your manual testing, navigate to the "Create Defect" tab to generate a Jira bug report and push it directly to your project.

## 📁 Project Structure

```text
qa-assistant/
├── backend/
│   ├── app/
│   │   ├── generator.py      # Test case extraction logic
│   │   ├── jira_client.py    # Jira REST API client
│   │   └── llm.py            # LLM API wrappers
│   ├── app_flask.py          # Flask application entry point
│   └── requirements.txt      # Python dependencies
├── frontend/
│   ├── Requirement/          # Local Excel requirement documents
│   ├── public/
│   └── src/
│       ├── App.js            # Main React UI logic
│       └── App.css           # Styling
└── README.md
```