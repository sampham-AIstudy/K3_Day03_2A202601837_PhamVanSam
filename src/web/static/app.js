let currentMode = 'agent'; // 'agent' (V2), 'agent_v1' (V1), 'chatbot'
let currentProvider = 'gemini';
let currentModelName = 'gemini-3.1-flash-lite';
let currentModelDisplayName = 'Gemini 3.1 Lite';
let currentModelKey = 'g31fl';

function togglePopover(event) {
    if (event) {
        event.preventDefault();
        event.stopPropagation();
    }
    const menu = document.getElementById('popover-menu');
    if (menu) {
        menu.classList.toggle('open');
    }
}

document.addEventListener('DOMContentLoaded', () => {
    const btn = document.getElementById('selector-pill-btn');
    if (btn) {
        btn.addEventListener('click', (e) => {
            togglePopover(e);
        });
    }
});

function selectMode(mode) {
    currentMode = mode;
    
    document.getElementById('item-mode-agent').classList.toggle('active', mode === 'agent');
    document.getElementById('item-mode-agent_v1').classList.toggle('active', mode === 'agent_v1');
    document.getElementById('item-mode-chatbot').classList.toggle('active', mode === 'chatbot');
    
    updatePillLabel();
    closePopover();
}

function selectModel(modelKey, modelName, displayName, providerType) {
    currentModelKey = modelKey;
    currentModelName = modelName;
    currentModelDisplayName = displayName;
    currentProvider = providerType;

    ['g31fl', 'g35fl', 'g36f', 'g35f', 'g25f', 'scripted'].forEach(k => {
        const item = document.getElementById(`item-model-${k}`);
        if (item) item.classList.toggle('active', k === modelKey);
    });

    const statusText = document.getElementById('header-status-text');
    if (statusText) statusText.innerText = displayName;

    updatePillLabel();
    closePopover();
}

function updatePillLabel() {
    const pillLabel = document.getElementById('pill-label');
    if (!pillLabel) return;

    let modeTitle = 'ReAct V2';
    if (currentMode === 'agent_v1') modeTitle = 'ReAct V1';
    if (currentMode === 'chatbot') modeTitle = 'Chatbot';

    let modelShort = currentModelDisplayName.replace('Gemini ', '');
    pillLabel.innerText = `${modeTitle} • ${modelShort}`;
}

function closePopover() {
    const menu = document.getElementById('popover-menu');
    if (menu) menu.classList.remove('open');
}

// Close popover when clicking anywhere outside
document.addEventListener('click', (event) => {
    const wrapper = document.querySelector('.popover-wrapper');
    if (wrapper && !wrapper.contains(event.target)) {
        closePopover();
    }
});

function usePreset(text) {
    document.getElementById('user-input').value = text;
    document.getElementById('chat-form').requestSubmit();
}

async function sendMessage(event) {
    event.preventDefault();
    closePopover();

    const inputEl = document.getElementById('user-input');
    const query = inputEl.value.trim();
    if (!query) return;

    inputEl.value = '';
    
    // 1. Append User Message Row
    appendUserMessage(query);

    // 2. Append Live Grok-style Thinking Bubble
    const pendingMsgId = 'msg-' + Date.now();
    appendLiveThinkingMessage(pendingMsgId);

    const liveStatusText = document.getElementById(`thinking-text-${pendingMsgId}`);
    if (liveStatusText && currentMode !== 'chatbot') {
        setTimeout(() => { if (liveStatusText) liveStatusText.innerText = "Analyzing query & checking tools..."; }, 300);
        setTimeout(() => { if (liveStatusText) liveStatusText.innerText = "Executing e-commerce tools..."; }, 800);
    } else if (liveStatusText) {
        liveStatusText.innerText = "Generating answer...";
    }

    try {
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                query: query,
                mode: currentMode,
                provider: currentProvider,
                model_name: currentModelName
            })
        });

        if (!response.ok) {
            throw new Error(`Server returned HTTP ${response.status}`);
        }

        const data = await response.json();
        
        // 3. Transform Thinking Bubble into Kimi Collapsible Accordion & Final Response
        updateBotMessageWithTrace(pendingMsgId, data);

    } catch (err) {
        updateBotMessageWithError(pendingMsgId, err.message);
    }
}

function appendUserMessage(text) {
    const thread = document.getElementById('chat-thread');
    const row = document.createElement('div');
    row.className = 'message-row user-row';

    row.innerHTML = `
        <div class="avatar-icon">👤</div>
        <div class="message-bubble">
            <div class="message-text">${escapeHtml(text)}</div>
        </div>
    `;

    thread.appendChild(row);
    thread.scrollTop = thread.scrollHeight;
}

function appendLiveThinkingMessage(msgId) {
    const thread = document.getElementById('chat-thread');
    const row = document.createElement('div');
    row.className = 'message-row bot-row';
    row.id = msgId;

    row.innerHTML = `
        <div class="avatar-icon">⚡</div>
        <div class="message-bubble" id="bubble-${msgId}">
            <div class="thinking-bubble">
                <span class="pulse-dot"></span>
                <span id="thinking-text-${msgId}">Thinking...</span>
            </div>
        </div>
    `;

    thread.appendChild(row);
    thread.scrollTop = thread.scrollHeight;
}

function updateBotMessageWithTrace(msgId, data) {
    const bubbleContainer = document.getElementById(`bubble-${msgId}`);
    if (!bubbleContainer) return;

    bubbleContainer.innerHTML = '';

    // If ReAct Agent mode & trace exists, build Collapsible Accordion (Collapsed by Default)
    if (data.mode !== 'chatbot' && data.trace && data.trace.length > 0) {
        const accordion = document.createElement('div');
        accordion.className = 'thought-accordion';

        const seconds = ((data.latency_ms || 300) / 1000).toFixed(1);
        const toolCalls = data.tool_calls || 0;

        const headerBtn = document.createElement('button');
        headerBtn.className = 'accordion-header';
        headerBtn.innerHTML = `
            <span>🧠 Thought for ${seconds}s • Called ${toolCalls} tool(s)</span>
            <span class="chevron">▼</span>
        `;

        const contentDiv = document.createElement('div');
        contentDiv.className = 'accordion-content';

        data.trace.forEach(step => {
            const item = document.createElement('div');
            item.className = 'trace-item';

            let stepHtml = `<div class="trace-thought">Step ${step.step}: ${escapeHtml(step.thought)}</div>`;
            if (step.action) {
                stepHtml += `<div class="trace-action">⚡ Action: ${escapeHtml(step.action)}</div>`;
            }
            if (step.observation) {
                stepHtml += `<div class="trace-obs">👁️ Observation: ${escapeHtml(step.observation)}</div>`;
            }
            item.innerHTML = stepHtml;
            contentDiv.appendChild(item);
        });

        headerBtn.onclick = () => {
            contentDiv.classList.toggle('expanded');
            headerBtn.querySelector('.chevron').innerText = contentDiv.classList.contains('expanded') ? '▲' : '▼';
        };

        accordion.appendChild(headerBtn);
        accordion.appendChild(contentDiv);
        bubbleContainer.appendChild(accordion);
    }

    // Append Final Answer Text Bubble
    const answerText = document.createElement('div');
    answerText.className = 'message-text';
    answerText.innerHTML = escapeHtml(data.final_answer || "No response received.");
    bubbleContainer.appendChild(answerText);

    const thread = document.getElementById('chat-thread');
    thread.scrollTop = thread.scrollHeight;
}

function updateBotMessageWithError(msgId, errorMsg) {
    const bubbleContainer = document.getElementById(`bubble-${msgId}`);
    if (!bubbleContainer) return;

    bubbleContainer.innerHTML = `
        <div class="message-text" style="border-color: #ef4444; color: #f87171;">
            ❌ Error: ${escapeHtml(errorMsg)}
        </div>
    `;
}

function escapeHtml(str) {
    if (!str) return '';
    return str
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}
