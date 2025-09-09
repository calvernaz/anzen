// Anzen Dashboard JavaScript
console.log('🚀 Dashboard JavaScript loaded!');

// Global state
let currentSection = 'dashboard';
let activityData = [];
let charts = {};

// Initialize dashboard when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    console.log('🚀 DOM loaded, initializing dashboard...');
    initializeCharts();
    loadActivityFeed();
    loadAPIKeys();
    loadUsers();
    startRealTimeUpdates();
});

// Section navigation
function showSection(sectionName) {
    console.log('📍 Navigating to section:', sectionName);
    
    // Hide all sections
    document.querySelectorAll('.section').forEach(section => {
        section.style.display = 'none';
    });
    
    // Remove active class from nav items
    document.querySelectorAll('.nav-item').forEach(item => {
        item.classList.remove('active');
    });
    
    // Show selected section
    const targetSection = document.getElementById(sectionName + '-section');
    if (targetSection) {
        targetSection.style.display = 'block';
    }
    
    // Add active class to clicked nav item
    event.target.classList.add('active');
    
    // Update page title
    const titles = {
        'dashboard': 'Dashboard',
        'demo': 'Live Demo',
        'reports': 'Compliance Reports',
        'policies': 'Policy Management',
        'users': 'User Management',
        'api-keys': 'API Keys',
        'settings': 'Settings'
    };
    const titleElement = document.getElementById('page-title');
    if (titleElement) {
        titleElement.textContent = titles[sectionName] || sectionName;
    }
    currentSection = sectionName;
}

// Agent testing functionality
async function testAgent() {
    console.log('🔥 testAgent function called!');
    
    const prompt = document.getElementById('prompt').value;
    const route = document.getElementById('route-select').value;
    const resultDiv = document.getElementById('result');
    
    console.log('🔥 Elements found:', { prompt, route, resultDiv });
    
    if (!prompt.trim()) {
        alert('Please enter a prompt');
        return;
    }
    
    console.log('🔥 Starting workflow with:', { prompt, route });
    
    resultDiv.style.display = 'block';
    resultDiv.innerHTML = '<div class="spinner"></div> Processing with Anzen safety checks...';
    
    try {
        await simulateAnzenWorkflow(prompt, route, resultDiv);
        updateActivityFeed(prompt, route);
        updateStats();
    } catch (error) {
        console.error('🔥 Error in testAgent:', error);
        resultDiv.innerHTML = `<div class="result blocked">❌ Error: ${error.message}</div>`;
    }
}

async function simulateAnzenWorkflow(prompt, route, resultDiv) {
    console.log('🚀 Starting Anzen workflow:', { prompt, route });
    
    // Step 1: Input safety check with REAL API call
    resultDiv.innerHTML = '🛡️ Step 1: Checking input for PII...';
    
    try {
        console.log('📡 Calling gateway API for input check...');
        const response = await fetch('http://localhost:8000/v1/anzen/check/input', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                text: prompt,
                route: route,
                language: 'en'
            })
        });
        
        console.log('📡 Gateway response status:', response.status);
        
        if (!response.ok) {
            throw new Error(`Gateway API call failed: ${response.status}`);
        }
        
        const safetyResult = await response.json();
        console.log('🛡️ Safety result:', safetyResult);
        
        const decision = safetyResult.decision;
        const entities = safetyResult.entities;
        const safeText = safetyResult.safe_text;

        if (decision === 'BLOCK') {
            resultDiv.innerHTML = `
                <div class="result blocked">
                    <h3>🚫 Request Blocked</h3>
                    <p><strong>Reason:</strong> Input contains sensitive information that violates ${route} policy</p>
                    <p><strong>Detected:</strong> ${entities.map(e => e.type).join(', ')}</p>
                    <p><strong>Trace ID:</strong> ${safetyResult.trace_id}</p>
                </div>
            `;
            return;
        }

        // Step 2: Agent processing with REAL API call
        resultDiv.innerHTML = '🤖 Step 2: Testing agent connectivity...';
        
        // First test simple connectivity
        console.log('🧪 Testing agent connectivity...');
        const testResponse = await fetch('http://localhost:8001/v1/test');
        console.log('🧪 Test response status:', testResponse.status);
        
        if (testResponse.ok) {
            const testResult = await testResponse.json();
            console.log('🧪 Test result:', testResult);
            resultDiv.innerHTML = '🤖 Step 2: Processing with AI agent...';
        } else {
            throw new Error(`Agent connectivity test failed: ${testResponse.status}`);
        }
        
        console.log('🤖 Calling agent API with safe text:', safeText);
        
        // Create a timeout for the agent call
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 30000); // 30 second timeout
        
        const agentResponse = await fetch('http://localhost:8001/v1/agents/secure', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                prompt: safeText, // Use the safe text from step 1
                user_id: 'demo-user'
            }),
            signal: controller.signal
        });
        
        clearTimeout(timeoutId);
        console.log('🤖 Agent response status:', agentResponse.status);
        
        let agentResult;
        if (agentResponse.ok) {
            console.log('🤖 Agent responded successfully, parsing JSON...');
            agentResult = await agentResponse.json();
            console.log('🤖 Agent result:', agentResult);
        } else {
            console.warn('🤖 Agent call failed, using fallback');
            const errorText = await agentResponse.text();
            console.error('🤖 Agent error:', errorText);
            
            // Fallback if agent fails
            agentResult = {
                response: "I've processed your request safely using demo mode. The system has completed safety checks and provided a secure response.",
                plan: generatePlan(prompt),
                trace_id: safetyResult.trace_id,
                error: `Agent unavailable (${agentResponse.status})`
            };
        }
        
        const finalResponse = agentResult.response || "Request processed successfully with safety guardrails.";

        // Final result
        const resultClass = decision === 'BLOCK' ? 'blocked' : (decision === 'REDACT' ? 'redacted' : 'allowed');
        
        resultDiv.innerHTML = `
            <div class="result ${resultClass}">
                <h3>✅ Response (Safe)</h3>
                <div style="background: #f8fafc; padding: 16px; border-radius: 8px; margin: 12px 0; border-left: 4px solid #3b82f6;">
                    <strong>Agent Response:</strong><br>
                    ${finalResponse}
                </div>
                
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin: 16px 0;">
                    <div>
                        <h4>🛡️ Safety Summary</h4>
                        <p><strong>Input Safety:</strong> ${decision} 
                           ${entities.length > 0 ? `(${entities.length} PII entities detected)` : '(Clean)'}</p>
                        <p><strong>Safe Text:</strong> ${safeText}</p>
                        <p><strong>Route Policy:</strong> ${route}</p>
                        <p><strong>Risk Level:</strong> ${safetyResult.risk_level}</p>
                    </div>
                    <div>
                        <h4>🤖 Processing Details</h4>
                        <p><strong>Original Text:</strong> ${prompt}</p>
                        <p><strong>Entities Found:</strong> ${entities.map(e => e.type).join(', ') || 'None'}</p>
                        <p><strong>Processing Method:</strong> ${safetyResult.metadata.processing_method}</p>
                        <p><strong>Organization:</strong> ${safetyResult.metadata.organization}</p>
                    </div>
                </div>
                
                <p style="margin-top: 16px; color: #64748b;"><strong>Trace ID:</strong> ${safetyResult.trace_id}</p>
            </div>
        `;
        
    } catch (error) {
        console.error('❌ Workflow error:', error);
        
        let errorMessage = error.message;
        let errorDetails = "Unable to connect to Anzen services.";
        
        if (error.name === 'AbortError') {
            errorMessage = "Agent request timed out";
            errorDetails = "The agent took too long to respond (>30 seconds). This might be due to OpenAI API delays.";
        } else if (error.message.includes('fetch')) {
            errorDetails = "Network connection failed. Please ensure all services are running.";
        }
        
        resultDiv.innerHTML = `
            <div class="result blocked">
                <h3>❌ Error</h3>
                <p><strong>Message:</strong> ${errorMessage}</p>
                <p><strong>Details:</strong> ${errorDetails}</p>
                <p><strong>Services needed:</strong></p>
                <ul>
                    <li>Gateway: http://localhost:8000</li>
                    <li>Agent: http://localhost:8001</li>
                </ul>
                <p><strong>Debug:</strong> Check browser console for detailed logs</p>
            </div>
        `;
    }
}

// Demo utilities
function clearDemo() {
    document.getElementById('prompt').value = '';
    document.getElementById('result').style.display = 'none';
}

function loadExample() {
    const examples = [
        "My email is john.doe@company.com, can you help me with the weather in Paris?",
        "I need to process payment with card 4532-1234-5678-9012",
        "Customer SSN 123-45-6789 needs account verification",
        "What's the latest news about artificial intelligence?",
        "Internal project status: Phase 2 completion by Q3"
    ];
    const randomExample = examples[Math.floor(Math.random() * examples.length)];
    document.getElementById('prompt').value = randomExample;
}

// Utility functions
function generatePlan(prompt) {
    if (prompt.toLowerCase().includes('weather')) {
        return {
            steps: [
                {action: 'get_weather', description: 'Get weather information for requested location'},
                {action: 'synthesize', description: 'Format weather response for user'}
            ],
            complexity: 'low'
        };
    } else if (prompt.toLowerCase().includes('python') || prompt.toLowerCase().includes('programming')) {
        return {
            steps: [
                {action: 'search_wikipedia', description: 'Search for programming information'},
                {action: 'synthesize', description: 'Format educational response'}
            ],
            complexity: 'medium'
        };
    } else {
        return {
            steps: [
                {action: 'analyze', description: 'Analyze user request'},
                {action: 'synthesize', description: 'Generate helpful response'}
            ],
            complexity: 'low'
        };
    }
}

// Placeholder functions for other features
function initializeCharts() {
    console.log('📊 Charts initialized (placeholder)');
}

function loadActivityFeed() {
    console.log('📋 Activity feed loaded (placeholder)');
}

function loadAPIKeys() {
    console.log('🔑 API keys loaded (placeholder)');
}

function loadUsers() {
    console.log('👥 Users loaded (placeholder)');
}

function startRealTimeUpdates() {
    console.log('🔄 Real-time updates started (placeholder)');
}

function updateActivityFeed(prompt, route) {
    console.log('📋 Activity feed updated:', { prompt, route });
}

function updateStats() {
    console.log('📊 Stats updated');
}

console.log('✅ Dashboard JavaScript fully loaded!');
