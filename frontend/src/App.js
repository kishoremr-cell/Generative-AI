import React, { useState } from 'react';
import './App.css';

function App() {
  const [ticketId, setTicketId] = useState('');
  const [jiraData, setJiraData] = useState(null);
  const [jiraContent, setJiraContent] = useState('');
  const [sourceType, setSourceType] = useState('jira');
  const [reqFiles, setReqFiles] = useState([]);
  const [selectedReqFile, setSelectedReqFile] = useState('');
  const [selectedModel, setSelectedModel] = useState('ollama');
  const [customPrompt, setCustomPrompt] = useState('');
  const [testCases, setTestCases] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [showSettings, setShowSettings] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [activeTab, setActiveTab] = useState('generate');
  const [operationHistory, setOperationHistory] = useState([]);
  const [defectForm, setDefectForm] = useState({
    projectKey: '',
    summary: '',
    description: '',
    stepsToReproduce: '',
    expectedResult: '',
    actualResult: '',
    severity: 'Medium',
    priority: 'Medium'
  });
  const [isCreatingDefect, setIsCreatingDefect] = useState(false);
  const [settings, setSettings] = useState({
    jiraBaseUrl: '',
    jiraEmail: '',
    jiraApiToken: '',
    jiraProjectKey: '',
    openaiKey: '',
    openaiModel: 'gpt-3.5-turbo',
    geminiKey: '',
    grokKey: '',
    grokModel: 'grok-beta',
    groqKey: '',
    groqModel: 'llama-3.1-8b-instant',
    claudeKey: '',
    claudeModel: 'claude-3-sonnet-20240229',
    mistralKey: '',
    mistralModel: 'mistral-large-latest',
    ollamaModel: 'phi3'
  });

  // Load settings and history from localStorage on mount
  React.useEffect(() => {
    const savedSettings = localStorage.getItem('qaSettings');
    if (savedSettings) {
      setSettings(JSON.parse(savedSettings));
    }

    const savedHistory = localStorage.getItem('qaHistory');
    if (savedHistory) {
      setOperationHistory(JSON.parse(savedHistory));
    }
  }, []);

  React.useEffect(() => {
    if (sourceType === 'document') {
      fetch('/list-requirements')
        .then(res => res.json())
        .then(data => {
          if (Array.isArray(data)) setReqFiles(data);
        })
        .catch(err => console.error("Failed to fetch requirements", err));
    }
  }, [sourceType]);

  const saveSettings = () => {
    localStorage.setItem('qaSettings', JSON.stringify(settings));
    setShowSettings(false);
    setSuccess('Settings saved! 🎉');
    setTimeout(() => setSuccess(''), 3000);
  };

  const addToHistory = (type, data) => {
    const newEntry = {
      id: Date.now(),
      timestamp: new Date().toISOString(),
      type,
      ...data
    };
    const updatedHistory = [newEntry, ...operationHistory.slice(0, 49)]; // Keep last 50 entries
    setOperationHistory(updatedHistory);
    localStorage.setItem('qaHistory', JSON.stringify(updatedHistory));
  };

  const clearHistory = () => {
    setOperationHistory([]);
    localStorage.removeItem('qaHistory');
    setSuccess('History cleared! 🗑️');
    setTimeout(() => setSuccess(''), 2000);
  };

  const loadFromHistory = (entry) => {
    if (entry.type === 'jira-fetch') {
      setTicketId(entry.ticketId);
      setJiraData(entry.jiraData);
      setJiraContent(entry.jiraContent);
      setActiveTab('generate');
      setSuccess('Loaded from history! 📚');
      setTimeout(() => setSuccess(''), 2000);
    } else if (entry.type === 'test-generation') {
      setTicketId(entry.ticketId);
      setJiraData(entry.jiraData);
      setJiraContent(entry.jiraContent);
      setSelectedModel(entry.model);
      setTestCases(entry.testCases);
      setActiveTab('results');
      setSuccess('Loaded from history! 📚');
      setTimeout(() => setSuccess(''), 2000);
    }
  };

  const fetchJira = async () => {
    if (!ticketId.trim()) {
      setError('Please enter a Jira Ticket ID');
      return;
    }

    setIsLoading(true);
    setError('');
    setSuccess('');

    try {
      const response = await fetch('/fetch-jira', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          issueKey: ticketId.trim(),
          jiraBaseUrl: settings.jiraBaseUrl,
          jiraEmail: settings.jiraEmail,
          jiraApiToken: settings.jiraApiToken
        }),
      });

      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.error || `HTTP error! status: ${response.status}`);
      }

      if (data.error) {
        setError(data.error);
        setJiraData(null);
      } else {
        setJiraData(data);
        const content = `${data.summary || 'No Summary'}\n\n${data.description || 'No Description'}\n\nAcceptance Criteria:\n${data.acceptance_criteria || 'Not Provided'}`;
        setJiraContent(content);
        setSuccess(`Successfully fetched issue: ${ticketId} 🎯`);

        // Add to history
        addToHistory('jira-fetch', {
          ticketId: ticketId.trim(),
          jiraData: data,
          jiraContent: content
        });
      }
    } catch (err) {
      setError(`Failed to fetch issue: ${err.message}`);
      setJiraData(null);
    } finally {
      setIsLoading(false);
    }
  };

  const fetchDocument = async () => {
    if (!selectedReqFile) {
      setError('Please select a requirement document');
      return;
    }

    setIsLoading(true);
    setError('');
    setSuccess('');

    try {
      const response = await fetch('/parse-requirement', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ filename: selectedReqFile }),
      });

      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Failed to parse document');

      const content = data.content;
      setJiraContent(content);
      // Create a pseudo jiraData so generateTestCases has something truthy
      setJiraData({
        summary: `Requirements from ${selectedReqFile}`,
        description: content,
        acceptance_criteria: ''
      });
      setSuccess(`Successfully parsed ${selectedReqFile} 🎯`);
    } catch (err) {
      setError(`Failed to parse document: ${err.message}`);
      setJiraData(null);
    } finally {
      setIsLoading(false);
    }
  };

  const generateTestCases = async () => {
    if (!jiraData) {
      setError('Please fetch a Jira issue first');
      return;
    }

    setIsLoading(true);
    setError('');
    setSuccess('');

    try {
      let endpoint = '/generate-with-llm';
      let payload = {
        issueKey: ticketId,
        llmSource: selectedModel === 'ollama' ? 'local' : 'cloud',
        model: selectedModel,
        ollamaModel: settings.ollamaModel,
        jiraBaseUrl: settings.jiraBaseUrl,
        jiraEmail: settings.jiraEmail,
        jiraApiToken: settings.jiraApiToken,
        customPrompt: customPrompt.trim() || null,
        apiKeys: selectedModel !== 'ollama' ? {
          openaiKey: settings.openaiKey,
          openaiModel: settings.openaiModel,
          geminiKey: settings.geminiKey,
          grokKey: settings.grokKey,
          grokModel: settings.grokModel,
          groqKey: settings.groqKey,
          groqModel: settings.groqModel,
          claudeKey: settings.claudeKey,
          claudeModel: settings.claudeModel,
          mistralKey: settings.mistralKey,
          mistralModel: settings.mistralModel
        } : null
      };

      if (sourceType === 'document') {
        endpoint = '/generate-from-text';
        payload = {
          content: jiraContent,
          llmSource: selectedModel === 'ollama' ? 'local' : 'cloud',
          model: selectedModel,
          ollamaModel: settings.ollamaModel,
          customPrompt: customPrompt.trim() || null,
          apiKeys: payload.apiKeys
        };
      }

      const response = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.error || `HTTP error! status: ${response.status}`);
      }

      if (data.error) {
        setError(data.error);
      } else {
        setTestCases(data.testCases || []);
        setSuccess(`Generated test cases using ${selectedModel} ✨`);

        // Add to history
        addToHistory('test-generation', {
          ticketId: ticketId.trim(),
          jiraData,
          jiraContent,
          model: selectedModel,
          customPrompt: customPrompt.trim(),
          testCases: data.testCases || []
        });

        setActiveTab('results');
      }
    } catch (err) {
      setError(`Failed to generate test cases: ${err.message}`);
    } finally {
      setIsLoading(false);
    }
  };

  const generateDefect = async () => {
    if (!jiraData || testCases.length === 0) {
      setError('Please fetch a Jira issue and generate test cases first');
      return;
    }

    setIsLoading(true);
    setError('');
    setSuccess('');

    try {
      // Use the first test case for defect generation (can be extended to select specific test case)
      const testCase = testCases[0];

      const response = await fetch('/generate-defect', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          testCase,
          issueData: jiraData,
          llmSource: selectedModel === 'ollama' ? 'local' : 'cloud',
          model: selectedModel,
          apiKeys: selectedModel !== 'ollama' ? {
            openaiKey: settings.openaiKey,
            openaiModel: settings.openaiModel,
            geminiKey: settings.geminiKey,
            grokKey: settings.grokKey,
            grokModel: settings.grokModel,
            groqKey: settings.groqKey,
            groqModel: settings.groqModel,
            claudeKey: settings.claudeKey,
            claudeModel: settings.claudeModel,
            mistralKey: settings.mistralKey,
            mistralModel: settings.mistralModel
          } : null,
          jiraBaseUrl: settings.jiraBaseUrl,
          jiraEmail: settings.jiraEmail,
          jiraApiToken: settings.jiraApiToken
        }),
      });

      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.error || `HTTP error! status: ${response.status}`);
      }

      setDefectForm({
        projectKey: defectForm.projectKey || '',
        summary: data.summary || '',
        description: data.description || '',
        stepsToReproduce: data.steps_to_reproduce || '',
        expectedResult: data.expected_result || '',
        actualResult: data.actual_result || '',
        severity: data.severity || 'Medium',
        priority: data.priority || 'Medium'
      });

      setSuccess('Defect details generated using AI ✨');
      setActiveTab('defect');
    } catch (err) {
      setError(`Failed to generate defect: ${err.message}`);
    } finally {
      setIsLoading(false);
    }
  };

  const createDefect = async () => {
    if (!defectForm.summary.trim()) {
      setError('Defect summary is required');
      return;
    }

    setIsCreatingDefect(true);
    setError('');
    setSuccess('');

    try {
      const response = await fetch('/create-defect', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ...defectForm,
          projectKey: defectForm.projectKey || settings.jiraProjectKey,
          jiraBaseUrl: settings.jiraBaseUrl,
          jiraEmail: settings.jiraEmail,
          jiraApiToken: settings.jiraApiToken
        }),
      });

      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.error || `HTTP error! status: ${response.status}`);
      }

      setSuccess(`Defect created successfully! Issue: ${data.issueKey} 🐛`);

      // Add to history
      addToHistory('defect-creation', {
        issueKey: data.issueKey,
        defectData: defectForm,
        jiraData: data
      });

      // Reset form (keep projectKey for convenience)
      setDefectForm({
        ...defectForm,
        summary: '',
        description: '',
        stepsToReproduce: '',
        expectedResult: '',
        actualResult: '',
        severity: 'Medium',
        priority: 'Medium'
      });
    } catch (err) {
      setError(`Failed to create defect: ${err.message}`);
    } finally {
      setIsCreatingDefect(false);
    }
  };

  return (
    <div className="app">
      <header className="app-header">
        <div className="header-content">
          <div className="logo">
            <div className="logo-icon">🧪</div>
            <div>
              <h1>QA AI Assistant</h1>
              <p>Jira Integration & Test Case Generation</p>
            </div>
          </div>
          <div className="header-actions">
            <button
              onClick={() => setShowHistory(!showHistory)}
              className="settings-btn history-btn"
              title="View History"
            >
              📚
            </button>
            <button onClick={() => setShowSettings(!showSettings)} className="settings-btn">⚙️</button>
          </div>
        </div>
      </header>

      <div className="container">
        {/* History Panel */}
        <div className={`history-panel ${showHistory ? 'open' : ''}`}>
          <div className="history-header">
            <h3>📚 Operation History</h3>
            <div className="history-actions">
              <button onClick={clearHistory} className="clear-history-btn" title="Clear History">
                🗑️
              </button>
              <button onClick={() => setShowHistory(false)} className="close-btn">×</button>
            </div>
          </div>
          <div className="history-content">
            {operationHistory.length === 0 ? (
              <div className="empty-history">
                <div className="empty-icon">📝</div>
                <p>No history yet</p>
                <small>Start by fetching a Jira ticket or generating test cases</small>
              </div>
            ) : (
              <div className="history-list">
                {operationHistory.map((entry) => (
                  <div key={entry.id} className="history-item" onClick={() => loadFromHistory(entry)}>
                    <div className="history-item-header">
                      <div className="history-type">
                        {entry.type === 'jira-fetch' ? '📋' : '🤖'} {entry.type === 'jira-fetch' ? 'Jira Fetch' : 'Test Generation'}
                      </div>
                      <div className="history-timestamp">
                        {new Date(entry.timestamp).toLocaleString()}
                      </div>
                    </div>
                    <div className="history-item-content">
                      <div className="history-ticket">Ticket: {entry.ticketId}</div>
                      {entry.type === 'test-generation' && (
                        <div className="history-model">Model: {entry.model}</div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Settings Panel */}
        <div className={`settings-panel ${showSettings ? 'open' : ''}`}>
          <div className="settings-header">
            <h3>API Settings</h3>
            <button onClick={() => setShowSettings(false)} className="close-btn">×</button>
          </div>
          <div className="settings-content">
            <div className="settings-section">
              <h4>Jira Configuration</h4>
              <div className="form-group">
                <label>Jira Base URL:</label>
                <input
                  type="text"
                  value={settings.jiraBaseUrl}
                  onChange={e => setSettings({...settings, jiraBaseUrl: e.target.value})}
                  placeholder="https://your-domain.atlassian.net"
                />
              </div>
              <div className="form-group">
                <label>Jira Email:</label>
                <input
                  type="email"
                  value={settings.jiraEmail}
                  onChange={e => setSettings({...settings, jiraEmail: e.target.value})}
                  placeholder="your-email@example.com"
                />
              </div>
              <div className="form-group">
                <label>Jira API Token:</label>
                <input
                  type="password"
                  value={settings.jiraApiToken}
                  onChange={e => setSettings({...settings, jiraApiToken: e.target.value})}
                  placeholder="your-api-token"
                />
              </div>
              <div className="form-group">
                <label>Jira Project Key:</label>
                <input
                  type="text"
                  value={settings.jiraProjectKey}
                  onChange={e => setSettings({...settings, jiraProjectKey: e.target.value.toUpperCase()})}
                  placeholder="e.g. PROJ (Optional)"
                />
              </div>
            </div>

            <div className="settings-section">
              <h4>AI Model Configuration</h4>
              <div className="form-group">
                <label>OpenAI API Key:</label>
                <input
                  type="password"
                  value={settings.openaiKey}
                  onChange={e => setSettings({...settings, openaiKey: e.target.value})}
                  placeholder="sk-..."
                />
              </div>
              <div className="form-group">
                <label>OpenAI Model:</label>
                <select
                  value={settings.openaiModel}
                  onChange={e => setSettings({...settings, openaiModel: e.target.value})}
                >
                  <option value="gpt-3.5-turbo">GPT-3.5 Turbo</option>
                  <option value="gpt-4">GPT-4</option>
                </select>
              </div>
              <div className="form-group">
                <label>Gemini API Key:</label>
                <input
                  type="password"
                  value={settings.geminiKey}
                  onChange={e => setSettings({...settings, geminiKey: e.target.value})}
                  placeholder="..."
                />
              </div>
              <div className="form-group">
                <label>Grok API Key:</label>
                <input
                  type="password"
                  value={settings.grokKey}
                  onChange={e => setSettings({...settings, grokKey: e.target.value})}
                  placeholder="..."
                />
              </div>
              <div className="form-group">
                <label>Grok Model:</label>
                <select
                  value={settings.grokModel}
                  onChange={e => setSettings({...settings, grokModel: e.target.value})}
                >
                  <option value="grok-beta">Grok Beta</option>
                  <option value="grok-1">Grok 1</option>
                  <option value="grok-2">Grok 2</option>
                </select>
              </div>
              <div className="form-group">
                <label>Groq API Key:</label>
                <input
                  type="password"
                  value={settings.groqKey}
                  onChange={e => setSettings({...settings, groqKey: e.target.value})}
                  placeholder="..."
                />
              </div>
              <div className="form-group">
                <label>Groq Model:</label>
                <select
                  value={settings.groqModel}
                  onChange={e => setSettings({...settings, groqModel: e.target.value})}
                >
                  <option value="llama-3.1-8b-instant">llama-3.1-8b-instant</option>
                  <option value="llama3-70b-8192">llama3-70b-8192</option>
                  <option value="llama3-8b-8192">llama3-8b-8192</option>
                </select>
              </div>
              <div className="form-group">
                <label>Claude API Key:</label>
                <input
                  type="password"
                  value={settings.claudeKey}
                  onChange={e => setSettings({...settings, claudeKey: e.target.value})}
                  placeholder="sk-ant-..."
                />
              </div>
              <div className="form-group">
                <label>Claude Model:</label>
                <select
                  value={settings.claudeModel}
                  onChange={e => setSettings({...settings, claudeModel: e.target.value})}
                >
                  <option value="claude-3-opus-20240229">Claude 3 Opus</option>
                  <option value="claude-3-sonnet-20240229">Claude 3 Sonnet</option>
                  <option value="claude-3-haiku-20240307">Claude 3 Haiku</option>
                </select>
              </div>
              <div className="form-group">
                <label>Mistral API Key:</label>
                <input
                  type="password"
                  value={settings.mistralKey}
                  onChange={e => setSettings({...settings, mistralKey: e.target.value})}
                  placeholder="..."
                />
              </div>
              <div className="form-group">
                <label>Mistral Model:</label>
                <select
                  value={settings.mistralModel}
                  onChange={e => setSettings({...settings, mistralModel: e.target.value})}
                >
                  <option value="mistral-large-latest">Mistral Large</option>
                  <option value="mistral-medium-latest">Mistral Medium</option>
                  <option value="mistral-small-latest">Mistral Small</option>
                </select>
              </div>
              <div className="form-group">
                <label>Ollama Model:</label>
                <input
                  value={settings.ollamaModel}
                  onChange={e => setSettings({...settings, ollamaModel: e.target.value})}
                  placeholder="phi3"
                />
              </div>
            </div>

            <button onClick={saveSettings} className="btn-primary save-btn">💾 Save Settings</button>
          </div>
        </div>

        {/* Main Content */}
        <main className="main-content">
          {/* Alerts */}
          {error && <div className="alert alert-error">❌ {error}</div>}
          {success && <div className="alert alert-success">✅ {success}</div>}

          {/* Navigation Tabs */}
          <div className="tabs">
            <button
              className={`tab ${activeTab === 'generate' ? 'active' : ''}`}
              onClick={() => setActiveTab('generate')}
            >
              🚀 Generate
            </button>
            <button
              className={`tab ${activeTab === 'results' ? 'active' : ''}`}
              onClick={() => setActiveTab('results')}
              disabled={!testCases}
            >
              📋 Results {testCases && Array.isArray(testCases) ? `(${testCases.length})` : ''}
            </button>
            <button
              className={`tab ${activeTab === 'test-cases' ? 'active' : ''}`}
              onClick={() => setActiveTab('test-cases')}
              disabled={!testCases}
            >
              🧪 Test Cases {testCases && Array.isArray(testCases) ? `(${testCases.length})` : ''}
            </button>
            <button
              className={`tab ${activeTab === 'defect' ? 'active' : ''}`}
              onClick={() => setActiveTab('defect')}
            >
              🐛 Create Defect
            </button>
          </div>

          {/* Tab Content */}
          {activeTab === 'generate' && (
            <>
              {/* Fetch Requirements Card */}
              <div className="card">
                <div className="card-header">
                  <h3>📋 Fetch Requirements</h3>
                </div>
                <div className="card-content">
                  <div className="source-toggle">
                    <label>
                      <input 
                        type="radio" 
                        name="sourceType" 
                        value="jira" 
                        checked={sourceType === 'jira'} 
                        onChange={() => setSourceType('jira')} 
                      /> Jira Ticket
                    </label>
                    <label>
                      <input 
                        type="radio" 
                        name="sourceType" 
                        value="document" 
                        checked={sourceType === 'document'} 
                        onChange={() => setSourceType('document')} 
                      /> Local Document
                    </label>
                  </div>

                  {sourceType === 'jira' ? (
                    <div className="input-group" style={{marginTop: '15px'}}>
                      <input
                        type="text"
                        className="ticket-input"
                        value={ticketId}
                        onChange={(e) => setTicketId(e.target.value.toUpperCase())}
                        onKeyPress={(e) => e.key === 'Enter' && fetchJira()}
                        placeholder="Enter Jira Ticket ID (e.g., PROJ-123)"
                      />
                      <button onClick={fetchJira} disabled={isLoading} className="btn-primary">
                        {isLoading ? (
                          <>
                            <div className="spinner">
                              <div className="spinner-circle"></div>
                            </div>
                            Fetching...
                          </>
                        ) : (
                          <>📥 Fetch Ticket</>
                        )}
                      </button>
                    </div>
                  ) : (
                    <div className="input-group" style={{marginTop: '15px'}}>
                      <select 
                        className="ticket-input"
                        value={selectedReqFile}
                        onChange={(e) => setSelectedReqFile(e.target.value)}
                      >
                        <option value="">Select a document...</option>
                        {reqFiles.map(file => (
                          <option key={file} value={file}>{file}</option>
                        ))}
                      </select>
                      <button onClick={fetchDocument} disabled={isLoading || !selectedReqFile} className="btn-primary">
                        {isLoading ? (
                          <>
                            <div className="spinner">
                              <div className="spinner-circle"></div>
                            </div>
                            Parsing...
                          </>
                        ) : (
                          <>📥 Parse Document</>
                        )}
                      </button>
                    </div>
                  )}
                </div>
              </div>

              {/* Data Display */}
              {jiraData && sourceType === 'jira' && (
                <div className="card">
                  <div className="card-header">
                    <h3>📄 Jira Issue Details</h3>
                  </div>
                  <div className="card-content">
                    <div className="jira-details">
                      <div className="detail-item">
                        <strong>Summary</strong>
                        <div className="description">{jiraData.summary || 'Not Provided'}</div>
                      </div>
                      <div className="detail-item">
                        <strong>Description</strong>
                        <div className="description">{jiraData.description || 'Not Provided'}</div>
                      </div>
                      <div className="detail-item">
                        <strong>Acceptance Criteria</strong>
                        <div className="criteria">{jiraData.acceptance_criteria || 'Not Provided'}</div>
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* Editable Jira Content */}
              <div className="card">
                <div className="card-header">
                  <h3>✏️ Editable Content</h3>
                </div>
                <div className="card-content">
                  <textarea
                    className="content-textarea"
                    value={jiraContent}
                    onChange={(e) => setJiraContent(e.target.value)}
                    placeholder="Jira content will appear here after fetching..."
                  />
                </div>
              </div>

              {/* Custom Prompt */}
              <div className="card">
                <div className="card-header">
                  <h3>💬 Custom AI Prompt (Optional)</h3>
                </div>
                <div className="card-content">
                  <textarea
                    className="prompt-textarea"
                    value={customPrompt}
                    onChange={(e) => setCustomPrompt(e.target.value)}
                    placeholder="Add custom instructions for the AI model (e.g., 'Focus on edge cases', 'Include performance tests', 'Generate BDD scenarios', etc.)"
                    rows={3}
                  />
                  <div className="prompt-hint">
                    💡 Leave empty for default test case generation, or specify custom requirements
                  </div>
                </div>
              </div>

              {/* Model Selection and Generate */}
              <div className="card">
                <div className="card-header">
                  <h3>🤖 Generate Test Cases</h3>
                </div>
                <div className="card-content">
                  <div className="input-group">
                    <select
                      className="model-select"
                      value={selectedModel}
                      onChange={(e) => setSelectedModel(e.target.value)}
                    >
                      <option value="ollama">🖥️ Ollama (Local)</option>
                      <option value="openai">🤖 OpenAI (GPT)</option>
                      <option value="claude">🧠 Claude</option>
                      <option value="grok">🚀 Grok</option>
                      <option value="groq">📘 Groq</option>
                      <option value="mistral">✨ Mistral</option>
                      <option value="gemini">🌟 Gemini</option>
                    </select>
                    <button onClick={generateTestCases} disabled={isLoading || !jiraData} className="btn-primary">
                      {isLoading ? (
                        <>
                          <div className="spinner">
                            <div className="spinner-circle"></div>
                          </div>
                          Generating...
                        </>
                      ) : (
                        <>🚀 Generate</>
                      )}
                    </button>
                  </div>
                </div>
              </div>
            </>
          )}

          {/* Test Cases Tab */}
          {activeTab === 'test-cases' && testCases && (
            <div className="test-cases-viewer">
              <div className="viewer-header">
                <h3>🧪 Detailed Test Cases</h3>
                <div className="viewer-meta">
                  <span className="model-badge">{selectedModel}</span>
                  <span className="ticket-badge">{ticketId}</span>
                  <span className="count-badge">{Array.isArray(testCases) ? testCases.length : 0} Test Cases</span>
                </div>
              </div>

              {Array.isArray(testCases) ? (
                <div className="test-cases-grid">
                  {testCases.map((testCase, index) => (
                    <div key={index} className="test-case-card">
                      <div className="test-case-card-header">
                        <div className="test-case-number">TC-{String(index + 1).padStart(3, '0')}</div>
                        <div className="test-case-badges">
                          <span className={`badge priority-${testCase.priority?.toLowerCase() || 'medium'}`}>
                            {testCase.priority || 'Medium'}
                          </span>
                          <span className={`badge type-${testCase.type?.toLowerCase() || 'functional'}`}>
                            {testCase.type || 'Functional'}
                          </span>
                        </div>
                      </div>

                      <div className="test-case-card-content">
                        <div className="test-case-title">
                          <h4>{testCase.title || 'Untitled Test Case'}</h4>
                        </div>

                        <div className="test-case-section">
                          <h5>📝 Description</h5>
                          <p>{testCase.description || 'No description provided'}</p>
                        </div>

                        <div className="test-case-section">
                          <h5>⚙️ Preconditions</h5>
                          <p>{testCase.preconditions || 'None specified'}</p>
                        </div>

                        <div className="test-case-section">
                          <h5>📋 Test Steps</h5>
                          <div className="steps-container">
                            {testCase.steps && testCase.steps.length > 0 ? (
                              <ol className="steps-list">
                                {testCase.steps.map((step, stepIndex) => (
                                  <li key={stepIndex} className="step-item">
                                    <span className="step-number">{stepIndex + 1}</span>
                                    <span className="step-text">{step}</span>
                                  </li>
                                ))}
                              </ol>
                            ) : (
                              <p className="no-steps">No steps defined</p>
                            )}
                          </div>
                        </div>

                        <div className="test-case-section">
                          <h5>✅ Expected Result</h5>
                          <div className="expected-result">
                            {testCase.expectedResult || 'Not specified'}
                          </div>
                        </div>
                      </div>

                      <div className="test-case-card-footer">
                        <button
                          className="copy-btn"
                          onClick={() => {
                            const text = `Test Case: ${testCase.title}\n\nDescription: ${testCase.description}\n\nPreconditions: ${testCase.preconditions}\n\nSteps:\n${testCase.steps?.map((step, i) => `${i + 1}. ${step}`).join('\n') || 'No steps'}\n\nExpected Result: ${testCase.expectedResult}`;
                            navigator.clipboard.writeText(text);
                            setSuccess('Test case copied to clipboard!');
                            setTimeout(() => setSuccess(''), 2000);
                          }}
                          title="Copy test case details"
                        >
                          📋 Copy
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="no-test-cases">
                  <div className="empty-icon">📝</div>
                  <p>No test cases available</p>
                  <small>Generate test cases first to view them here</small>
                </div>
              )}
            </div>
          )}

          {/* Create Defect Tab */}
          {activeTab === 'defect' && (
            <div className="defect-creator">
              <div className="defect-header">
                <h3>🐛 Create Jira Defect</h3>
                <div className="defect-actions">
                  <button
                    onClick={generateDefect}
                    disabled={isLoading || !jiraData || !testCases.length}
                    className="btn-secondary"
                  >
                    {isLoading ? (
                      <>
                        <div className="spinner">
                          <div className="spinner-circle"></div>
                        </div>
                        Generating...
                      </>
                    ) : (
                      <>🤖 Generate with AI</>
                    )}
                  </button>
                </div>
              </div>

              <div className="defect-form">
                <div className="form-row">
                  <div className="form-group full-width">
                    <label>Project Key</label>
                    <input
                      type="text"
                      value={defectForm.projectKey}
                      onChange={(e) => setDefectForm({...defectForm, projectKey: e.target.value.toUpperCase()})}
                      placeholder="e.g. PROJ (Optional, overrides default)"
                    />
                  </div>
                </div>

                <div className="form-row">
                  <div className="form-group full-width">
                    <label>Summary *</label>
                    <input
                      type="text"
                      value={defectForm.summary}
                      onChange={(e) => setDefectForm({...defectForm, summary: e.target.value})}
                      placeholder="Brief description of the bug"
                      maxLength={100}
                    />
                  </div>
                </div>

                <div className="form-row">
                  <div className="form-group full-width">
                    <label>Description</label>
                    <textarea
                      value={defectForm.description}
                      onChange={(e) => setDefectForm({...defectForm, description: e.target.value})}
                      placeholder="Detailed description of the bug"
                      rows={4}
                    />
                  </div>
                </div>

                <div className="form-row">
                  <div className="form-group full-width">
                    <label>Steps to Reproduce</label>
                    <textarea
                      value={defectForm.stepsToReproduce}
                      onChange={(e) => setDefectForm({...defectForm, stepsToReproduce: e.target.value})}
                      placeholder="Step-by-step instructions to reproduce the bug"
                      rows={6}
                    />
                  </div>
                </div>

                <div className="form-row">
                  <div className="form-group">
                    <label>Expected Result</label>
                    <textarea
                      value={defectForm.expectedResult}
                      onChange={(e) => setDefectForm({...defectForm, expectedResult: e.target.value})}
                      placeholder="What should happen"
                      rows={3}
                    />
                  </div>
                  <div className="form-group">
                    <label>Actual Result</label>
                    <textarea
                      value={defectForm.actualResult}
                      onChange={(e) => setDefectForm({...defectForm, actualResult: e.target.value})}
                      placeholder="What actually happened"
                      rows={3}
                    />
                  </div>
                </div>

                <div className="form-row">
                  <div className="form-group">
                    <label>Severity</label>
                    <select
                      value={defectForm.severity}
                      onChange={(e) => setDefectForm({...defectForm, severity: e.target.value})}
                    >
                      <option value="Low">Low</option>
                      <option value="Medium">Medium</option>
                      <option value="High">High</option>
                      <option value="Critical">Critical</option>
                    </select>
                  </div>
                  <div className="form-group">
                    <label>Priority</label>
                    <select
                      value={defectForm.priority}
                      onChange={(e) => setDefectForm({...defectForm, priority: e.target.value})}
                    >
                      <option value="Low">Low</option>
                      <option value="Medium">Medium</option>
                      <option value="High">High</option>
                      <option value="Highest">Highest</option>
                    </select>
                  </div>
                </div>

                <div className="form-actions">
                  <button
                    onClick={createDefect}
                    disabled={isCreatingDefect || !defectForm.summary.trim()}
                    className="btn-primary"
                  >
                    {isCreatingDefect ? (
                      <>
                        <div className="spinner">
                          <div className="spinner-circle"></div>
                        </div>
                        Creating Defect...
                      </>
                    ) : (
                      <>🐛 Create Defect in Jira</>
                    )}
                  </button>
                </div>
              </div>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}

export default App;