/* ─── script.js — JARVIS Frontend Logic ─────────────────────
   Handles: SSE streaming chat, voice recording via MediaRecorder,
   system stats polling, uptime, waveform animation, quick prompts.
─────────────────────────────────────────────────────────────── */

'use strict';

// ─── Configure marked (v12 compatible) ──────────────────────
// In marked v9+, the 'highlight' option was REMOVED from setOptions.
// Syntax highlighting must be done via a custom renderer instead.

marked.use({
  breaks: true,   // \n → <br>
  gfm: true,      // GitHub Flavored Markdown tables, strikethrough, etc.
  renderer: {
    // Override code block rendering to add language label + hljs highlighting
    code({ text, lang }) {
      const rawText = typeof text === 'string' ? text : String(text ?? '');
      const rawLang = typeof lang === 'string' ? lang.trim() : '';
      const validLang = rawLang && typeof hljs !== 'undefined' && hljs.getLanguage(rawLang) ? rawLang : '';
      const label = (rawLang || 'code').toUpperCase();
      
      let highlighted;
      try {
        if (typeof hljs !== 'undefined' && rawText.length > 0) {
          highlighted = validLang
            ? hljs.highlight(rawText, { language: validLang }).value
            : hljs.highlightAuto(rawText).value;
        } else {
          throw new Error('hljs skip');
        }
      } catch (_) {
        highlighted = rawText
          .replace(/&/g, '&amp;')
          .replace(/</g, '&lt;')
          .replace(/>/g, '&gt;');
      }

      // ChatGPT-style structure with Copy button
      return `
        <div class="code-container">
          <div class="code-header">
            <span class="code-lang">${label}</span>
            <button class="copy-btn" onclick="copyCode(this)">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="copy-icon"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
              <span>Copy code</span>
            </button>
          </div>
          <pre><code class="hljs">${highlighted || '/* (no code generated) */'}</code></pre>
        </div>`;
    },
  },
});

function renderMarkdown(text) {
  if (text == null || text === '') return '';
  try {
    return marked.parse(String(text));
  } catch (e) {
    // Fallback: escape HTML and show as plain text
    return '<p>' + String(text)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/\n/g, '<br>') + '</p>';
  }
}

// ─── DOM refs ────────────────────────────────────────────────
const chatMessages  = document.getElementById('chat-messages');
const userInput     = document.getElementById('user-input');
const sendBtn       = document.getElementById('send-btn');
const voiceBtn      = document.getElementById('voice-btn');
const resetBtn      = document.getElementById('reset-btn');
const statusDot     = document.getElementById('status-dot');
const statusText    = document.getElementById('status-text');
const msgCount      = document.getElementById('msg-count');
const uptimeDisplay = document.getElementById('uptime-display');
const waveformBars  = document.getElementById('waveform-bars');
const waveformLabel = document.getElementById('waveform-label');
const inputHint     = document.getElementById('input-hint');

// ─── State ───────────────────────────────────────────────────
let isRecording   = false;
let isStreaming   = false;
let mediaRecorder = null;
let audioChunks   = [];
let messageCount  = 0;
let startTime     = Date.now();

// ─── Init ────────────────────────────────────────────────────
(async function init() {
  buildWaveformBars();
  startUptimeClock();
  pollStatus();
  setInterval(pollStatus, 6000);
  loadHistory();
  // Load memory + sessions panels (waits briefly for server to be ready)
  setTimeout(() => { loadMemoryPanel(); loadSessionsPanel(); }, 1200);
})();

// ─── Waveform bars setup ─────────────────────────────────────
function buildWaveformBars() {
  waveformBars.innerHTML = '';
  for (let i = 0; i < 5; i++) {
    const bar = document.createElement('div');
    bar.className = 'bar';
    waveformBars.appendChild(bar);
  }
}

function setWaveformState(state) {
  // state: 'idle' | 'thinking' | 'speaking' | 'recording'
  waveformBars.classList.remove('active');
  const labels = { idle: 'STANDBY', thinking: 'PROCESSING', speaking: 'RESPONDING', recording: 'RECORDING' };
  waveformLabel.textContent = labels[state] || 'STANDBY';

  if (state !== 'idle') {
    waveformBars.classList.add('active');
    Array.from(waveformBars.children).forEach(bar => {
      bar.style.setProperty('--scale', (1.5 + Math.random() * 2).toFixed(1));
    });
  }
}

// ─── Uptime clock ────────────────────────────────────────────
function startUptimeClock() {
  setInterval(() => {
    const elapsed = Math.floor((Date.now() - startTime) / 1000);
    const h = String(Math.floor(elapsed / 3600)).padStart(2, '0');
    const m = String(Math.floor((elapsed % 3600) / 60)).padStart(2, '0');
    const s = String(elapsed % 60).padStart(2, '0');
    uptimeDisplay.textContent = `${h}:${m}:${s}`;
  }, 1000);
}

// ─── Status poll ─────────────────────────────────────────────
async function pollStatus() {
  try {
    const res  = await fetch('/api/status');
    const data = await res.json();

    if (data.llm_ready) {
      statusDot.className  = 'status-dot ready';
      statusText.textContent = 'ONLINE';
      sendBtn.disabled = false;
    } else {
      statusDot.className  = 'status-dot loading';
      statusText.textContent = 'Loading LLM…';
      sendBtn.disabled = true;
    }

    // Update system stats
    const s = data.system;
    updateStat('cpu-value', `${s.cpu_percent}%`, 'cpu-bar', s.cpu_percent);
    updateStat('ram-value', `${s.ram_used_gb}GB`, 'ram-bar', s.ram_percent);
    updateStat('disk-value', `${s.disk_percent}%`, 'disk-bar', s.disk_percent);

    if (s.battery) {
      updateStat('battery-value', `${s.battery.percent}%`, 'battery-bar', s.battery.percent);
    } else {
      document.getElementById('battery-value').textContent = 'N/A';
      document.getElementById('battery-bar').style.width = '100%';
      document.getElementById('battery-bar').style.background = 'var(--clr-accent)';
    }
  } catch (_) {
    statusDot.className  = 'status-dot error';
    statusText.textContent = 'OFFLINE';
  }
}

function updateStat(valueId, valueText, barId, percent) {
  document.getElementById(valueId).textContent = valueText;
  const bar = document.getElementById(barId);
  bar.style.width = `${Math.min(percent, 100)}%`;
  // Color code: green < 60, yellow < 85, red >= 85
  if (percent >= 85) bar.style.background = 'linear-gradient(90deg, #cc3300, var(--clr-red))';
  else if (percent >= 60) bar.style.background = 'linear-gradient(90deg, #cc8800, var(--clr-gold))';
  else bar.style.background = 'linear-gradient(90deg, var(--clr-accent2), var(--clr-accent))';
}

// ─── History ─────────────────────────────────────────────────
async function loadHistory() {
  try {
    const res  = await fetch('/api/history');
    const data = await res.json();
    if (data.history && data.history.length > 0) {
      clearWelcome();
      data.history.forEach(msg => {
        appendMessage(msg.role === 'user' ? 'user' : 'jarvis', msg.content, false);
      });
    }
  } catch (_) {}
}

// ─── Messaging ───────────────────────────────────────────────
function clearWelcome() {
  const w = chatMessages.querySelector('.welcome-msg');
  if (w) w.remove();
}

function appendMessage(role, text, animate = true) {
  clearWelcome();
  messageCount++;
  msgCount.textContent = messageCount;

  const div = document.createElement('div');
  div.className = `message ${role}`;
  if (!animate) div.style.animation = 'none';

  const label = document.createElement('div');
  label.className = 'msg-label';
  label.textContent = role === 'user' ? '▲ YOU' : '▼ JARVIS';

  const bubble = document.createElement('div');
  bubble.className = 'msg-bubble';

  if (role === 'jarvis') {
    // Render markdown for JARVIS responses
    bubble.innerHTML = renderMarkdown(text);
  } else {
    // Plain text for user messages (safe)
    bubble.textContent = text;
  }

  div.appendChild(label);
  div.appendChild(bubble);
  chatMessages.appendChild(div);
  scrollToBottom();
  return bubble;
}

function appendThinking() {
  clearWelcome();
  const div = document.createElement('div');
  div.className = 'message jarvis thinking-msg';
  div.id = 'thinking-indicator';

  const label = document.createElement('div');
  label.className = 'msg-label';
  label.textContent = '▼ JARVIS';

  const bubble = document.createElement('div');
  bubble.className = 'msg-bubble';
  bubble.innerHTML = '<div class="thinking-dot"></div><div class="thinking-dot"></div><div class="thinking-dot"></div>';

  div.appendChild(label);
  div.appendChild(bubble);
  chatMessages.appendChild(div);
  scrollToBottom();
  return div;
}

function removeThinking() {
  const el = document.getElementById('thinking-indicator');
  if (el) el.remove();
}

function scrollToBottom() {
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

// ─── Send message (with SSE streaming) ───────────────────────
async function sendMessage(text) {
  if (!text.trim() || isStreaming) return;

  const msg = text.trim();
  userInput.value = '';
  userInput.style.height = 'auto';
  appendMessage('user', msg);

  isStreaming = true;
  sendBtn.disabled = true;
  setWaveformState('thinking');

  const thinking = appendThinking();

  try {
    const res = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: msg, stream: true }),
    });

    if (!res.ok) {
      removeThinking();
      const err = await res.json().catch(() => ({ detail: 'Server error' }));
      appendMessage('jarvis', `⚠️ Error: ${err.detail || 'Something went wrong.'}`);
      return;
    }

    removeThinking();
    setWaveformState('speaking');

    // Create the JARVIS bubble for streaming
    messageCount++;
    msgCount.textContent = messageCount;
    const msgDiv = document.createElement('div');
    msgDiv.className = 'message jarvis';
    const lbl = document.createElement('div');
    lbl.className = 'msg-label';
    lbl.textContent = '▼ JARVIS';
    const bubble = document.createElement('div');
    bubble.className = 'msg-bubble typing-cursor';
    bubble.textContent = '';
    msgDiv.appendChild(lbl);
    msgDiv.appendChild(bubble);
    chatMessages.appendChild(msgDiv);

    // Read SSE stream — accumulate raw text, show plain while streaming
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let rawText = '';  // full accumulated raw text

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      const lines = buffer.split('\n');
      buffer = lines.pop();

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue;
        const payload = line.slice(6).trim();
        if (payload === '[DONE]') {
          // Stream complete — now render full markdown
          bubble.classList.remove('typing-cursor');
          bubble.innerHTML = renderMarkdown(rawText);
          scrollToBottom();
          continue;
        }
        try {
          const { token } = JSON.parse(payload);
          rawText += token;
          // Show plain text while still streaming (fast, no re-parsing)
          bubble.textContent = rawText;
          scrollToBottom();
        } catch (_) {}
      }
    }

    // Ensure markdown is rendered even if [DONE] wasn't sent
    bubble.classList.remove('typing-cursor');
    if (rawText) bubble.innerHTML = renderMarkdown(rawText);

  } catch (err) {
    removeThinking();
    appendMessage('jarvis', `⚠️ Network error: ${err.message}`);
  } finally {
    isStreaming = false;
    sendBtn.disabled = false;
    setWaveformState('idle');
    // Refresh memory + sessions after each conversation turn
    setTimeout(() => { loadMemoryPanel(); loadSessionsPanel(); }, 1000);
  }
}

// ─── Voice recording ─────────────────────────────────────────
async function startRecording() {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    audioChunks = [];
    mediaRecorder = new MediaRecorder(stream);

    mediaRecorder.ondataavailable = e => { if (e.data.size > 0) audioChunks.push(e.data); };
    mediaRecorder.onstop = async () => {
      stream.getTracks().forEach(t => t.stop());
      await processVoice();
    };

    mediaRecorder.start();
    isRecording = true;
    voiceBtn.classList.add('recording');
    setWaveformState('recording');
    inputHint.textContent = '🔴 Recording … click mic again to stop';
  } catch (err) {
    alert('Microphone access denied. Please allow mic permission in your browser.');
  }
}

function stopRecording() {
  if (mediaRecorder && mediaRecorder.state !== 'inactive') {
    mediaRecorder.stop();
  }
  isRecording = false;
  voiceBtn.classList.remove('recording');
  setWaveformState('thinking');
  inputHint.textContent = '🔄 Transcribing …';
}

async function processVoice() {
  try {
    const blob = new Blob(audioChunks, { type: 'audio/webm' });
    const arrayBuffer = await blob.arrayBuffer();
    const base64 = btoa(String.fromCharCode(...new Uint8Array(arrayBuffer)));

    const res = await fetch('/api/voice', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ audio_b64: base64 }),
    });

    if (!res.ok) throw new Error('Transcription failed');
    const data = await res.json();
    const transcript = data.transcript.trim();

    if (transcript) {
      userInput.value = transcript;
      inputHint.textContent = `✅ Heard: "${transcript}" — press Enter or Send`;
      // Auto-send after a short delay
      setTimeout(() => sendMessage(transcript), 800);
    } else {
      inputHint.textContent = '⚠️ Couldn\'t hear anything clearly. Try speaking closer to the mic.';
    }
  } catch (err) {
    inputHint.textContent = `⚠️ Voice error: ${err.message}`;
  } finally {
    setWaveformState('idle');
    setTimeout(() => { inputHint.textContent = 'Press Enter to send · Shift+Enter for newline · or click 🎤 to speak'; }, 4000);
  }
}

// ─── Event Listeners ─────────────────────────────────────────

// Send on Enter (Shift+Enter = newline)
userInput.addEventListener('keydown', e => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendMessage(userInput.value);
  }
});

// Auto-resize textarea
userInput.addEventListener('input', () => {
  userInput.style.height = 'auto';
  userInput.style.height = Math.min(userInput.scrollHeight, 120) + 'px';
});

// Send button
sendBtn.addEventListener('click', () => sendMessage(userInput.value));

// Voice button toggle
voiceBtn.addEventListener('click', () => {
  if (isRecording) stopRecording();
  else startRecording();
});

// Reset conversation
resetBtn.addEventListener('click', async () => {
  if (!confirm('Clear all conversation history?')) return;
  await fetch('/api/reset', { method: 'POST' });
  chatMessages.innerHTML = `
    <div class="welcome-msg">
      <div class="welcome-icon">🤖</div>
      <h2>Conversation cleared, Sir.</h2>
      <p>Ready for new instructions.</p>
    </div>`;
  messageCount = 0;
  msgCount.textContent = 0;
  startTime = Date.now();
});

// Quick prompt buttons
document.querySelectorAll('.quick-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    const prompt = btn.dataset.prompt;
    if (prompt) sendMessage(prompt);
  });
});

// ─── Memory Panel ─────────────────────────────────────────────
async function loadMemoryPanel() {
  const panel = document.getElementById('memory-panel');
  if (!panel) return;
  try {
    const res  = await fetch('/api/memory');
    if (!res.ok) throw new Error('not ready');
    const mem  = await res.json();
    renderMemoryPanel(panel, mem);
  } catch (_) {
    panel.innerHTML = '<div class="memory-empty">Memory unavailable while loading…</div>';
  }
}

function renderMemoryPanel(panel, mem) {
  const rows = [];

  const addRow = (key, val) => {
    if (!val) return;
    if (Array.isArray(val) && val.length === 0) return;
    rows.push({ key, val });
  };

  addRow('Name',     mem.name);
  addRow('Role',     mem.role);
  addRow('Location', mem.location);
  addRow('Language', mem.preferred_language);
  addRow('Projects', mem.projects);
  addRow('Interests',mem.interests);
  addRow('Facts',    mem.facts);

  if (rows.length === 0) {
    panel.innerHTML = '<div class="memory-empty">No facts learned yet. Chat with JARVIS to build your profile.</div>';
    return;
  }

  panel.innerHTML = rows.map(({ key, val }) => {
    const isArr = Array.isArray(val);
    const valHtml = isArr
      ? `<div class="memory-tags">${val.slice(-8).map(t => `<span class="memory-tag">${escHtml(t)}</span>`).join('')}</div>`
      : `<div class="memory-val">${escHtml(String(val))}</div>`;
    return `<div class="memory-row"><div class="memory-key">${escHtml(key)}</div>${valHtml}</div>`;
  }).join('');
}

// ─── Sessions Panel ───────────────────────────────────────────
async function loadSessionsPanel() {
  const list = document.getElementById('sessions-list');
  const countEl = document.getElementById('session-count');
  if (!list) return;
  try {
    const res  = await fetch('/api/history/all');
    if (!res.ok) throw new Error('not ready');
    const data = await res.json();
    const sessions = (data.sessions || []).reverse(); // newest first

    if (countEl) countEl.textContent = sessions.length || '0';

    if (sessions.length === 0) {
      list.innerHTML = '<div class="memory-empty">No past sessions yet.</div>';
      return;
    }

    list.innerHTML = sessions.map(s => {
      const dt  = s.timestamp ? new Date(s.timestamp).toLocaleString('en-IN', { dateStyle: 'short', timeStyle: 'short' }) : '—';
      const pre = s.preview ? escHtml(s.preview.slice(0, 60)) : '(empty)';
      return `
        <div class="session-card" title="${escHtml(s.preview || '')}">
          <div class="session-date">${dt}</div>
          <div class="session-preview">${pre}</div>
          <div class="session-count-badge">${s.message_count} message${s.message_count !== 1 ? 's' : ''}</div>
        </div>`;
    }).join('');
  } catch (_) {
    if (list) list.innerHTML = '<div class="memory-empty">Sessions unavailable while loading…</div>';
  }
}

// ─── Refresh memory after each JARVIS reply ───────────────────
// Patch sendMessage to refresh memory panel after completion
const _origSendMessage = sendMessage;
window._refreshMemoryAfterReply = function() {
  setTimeout(() => { loadMemoryPanel(); loadSessionsPanel(); }, 800);
};

// Refresh button
const refreshMemBtn = document.getElementById('refresh-memory-btn');
if (refreshMemBtn) {
  refreshMemBtn.addEventListener('click', () => {
    loadMemoryPanel();
    loadSessionsPanel();
  });
}

// ─── Utility ─────────────────────────────────────────────────
window.copyCode = function(btn) {
  const container = btn.closest('.code-container');
  const code = container.querySelector('code').innerText;
  
  navigator.clipboard.writeText(code).then(() => {
    const originalContent = btn.innerHTML;
    btn.innerHTML = `
      <svg viewBox="0 0 24 24" fill="none" stroke="#00ff88" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="copy-icon"><polyline points="20 6 9 17 4 12"></polyline></svg>
      <span style="color: #00ff88">Copied!</span>
    `;
    setTimeout(() => {
      btn.innerHTML = originalContent;
    }, 2000);
  });
};

function escHtml(str) {
  return String(str ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}
