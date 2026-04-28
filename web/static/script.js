'use strict';
marked.use({
  breaks: true,
  gfm: true,
  renderer: {
    code({ text, lang }) {
      const rawText = typeof text === 'string' ? text : String(text ?? '');
      const rawLang = typeof lang === 'string' ? lang.trim() : '';
      const validLang = rawLang && typeof hljs !== 'undefined' && hljs.getLanguage(rawLang) ? rawLang : 'plaintext';

      let highlighted = rawText;
      try {
        if (typeof hljs !== 'undefined' && rawText.trim().length > 0) {
          highlighted = hljs.highlight(rawText, { language: validLang }).value;
        }
      } catch (_) {
        highlighted = rawText.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
      }

      return `
        <div class="code-container">
          <div class="code-header">
            <span class="code-lang">${(rawLang || 'code').toUpperCase()}</span>
            <button class="copy-btn" onclick="copyCode(this)">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="copy-icon"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
              <span>Copy code</span>
            </button>
          </div>
          <pre><code class="hljs ${validLang}">${highlighted || '/* (no code generated) */'}</code></pre>
        </div>`;
    },
  },
});

function renderMarkdown(text) {
  if (text == null || text === '') return '';
  try {
    return marked.parse(String(text));
  } catch (e) {
    return '<p>' + String(text)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/\n/g, '<br>') + '</p>';
  }
}

const chatMessages = document.getElementById('chat-messages');
const userInput = document.getElementById('user-input');
const sendBtn = document.getElementById('send-btn');
const voiceBtn = document.getElementById('voice-btn');
const resetBtn = document.getElementById('reset-btn');
const statusDot = document.getElementById('status-dot');
const statusText = document.getElementById('status-text');
const msgCount = document.getElementById('msg-count');
const uptimeDisplay = document.getElementById('uptime-display');
const waveformBars = document.getElementById('waveform-bars');
const waveformLabel = document.getElementById('waveform-label');
const inputHint = document.getElementById('input-hint');

let isRecording = false;
let isStreaming = false;
let mediaRecorder = null;
let audioChunks = [];
let messageCount = 0;
let startTime = Date.now();
let abortController = null;

(async function init() {
  buildWaveformBars();
  startUptimeClock();
  pollStatus();
  setInterval(pollStatus, 6000);
  loadHistory();
})();

function buildWaveformBars() {
  waveformBars.innerHTML = '';
  for (let i = 0; i < 5; i++) {
    const bar = document.createElement('div');
    bar.className = 'bar';
    waveformBars.appendChild(bar);
  }
}

function setWaveformState(state) {
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

function startUptimeClock() {
  setInterval(() => {
    const elapsed = Math.floor((Date.now() - startTime) / 1000);
    const h = String(Math.floor(elapsed / 3600)).padStart(2, '0');
    const m = String(Math.floor((elapsed % 3600) / 60)).padStart(2, '0');
    const s = String(elapsed % 60).padStart(2, '0');
    uptimeDisplay.textContent = `${h}:${m}:${s}`;
  }, 1000);
}

async function pollStatus() {
  try {
    const res = await fetch('/api/status');
    const data = await res.json();

    if (data.llm_ready) {
      statusDot.className = 'status-dot ready';
      statusText.textContent = 'ONLINE';
      sendBtn.disabled = false;
    } else {
      statusDot.className = 'status-dot loading';
      statusText.textContent = 'Loading LLM…';
      sendBtn.disabled = true;
    }
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
    statusDot.className = 'status-dot error';
    statusText.textContent = 'OFFLINE';
  }
}

function updateStat(valueId, valueText, barId, percent) {
  document.getElementById(valueId).textContent = valueText;
  const bar = document.getElementById(barId);
  bar.style.width = `${Math.min(percent, 100)}%`;
  if (percent >= 85) bar.style.background = 'linear-gradient(90deg, #cc3300, var(--clr-red))';
  else if (percent >= 60) bar.style.background = 'linear-gradient(90deg, #cc8800, var(--clr-gold))';
  else bar.style.background = 'linear-gradient(90deg, var(--clr-accent2), var(--clr-accent))';
}

async function loadHistory() {
  try {
    const res = await fetch('/api/history');
    const data = await res.json();
    if (data.history && data.history.length > 0) {
      clearWelcome();
      data.history.forEach(msg => {
        appendMessage(msg.role === 'user' ? 'user' : 'jarvis', msg.content, false);
      });
    }
  } catch (_) { }
}

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
async function sendMessage(text) {
  if (!text.trim() || isStreaming) return;

  const msg = text.trim();
  userInput.value = '';
  userInput.style.height = 'auto';
  appendMessage('user', msg);

  isStreaming = true;

  // Transform send button to Stop button
  const sendIcon = document.getElementById('send-icon');
  if (sendIcon) {
    sendIcon.innerHTML = '<rect x="6" y="6" width="12" height="12" stroke-width="2"/>';
    sendIcon.style.color = '#ff3b5c';
  }

  setWaveformState('thinking');
  const thinking = appendThinking();

  abortController = new AbortController();

  try {
    const res = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: msg, stream: true }),
      signal: abortController.signal
    });

    if (!res.ok) {
      removeThinking();
      const err = await res.json().catch(() => ({ detail: 'Server error' }));
      appendMessage('jarvis', `Error: ${err.detail || 'Something went wrong.'}`);
      return;
    }

    removeThinking();
    setWaveformState('speaking');

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
          bubble.classList.remove('typing-cursor');
          bubble.innerHTML = renderMarkdown(rawText);
          scrollToBottom();
          continue;
        }
        try {
          const { token } = JSON.parse(payload);
          rawText += token;
          bubble.textContent = rawText;
          scrollToBottom();
        } catch (_) { }
      }
    }
    bubble.classList.remove('typing-cursor');
    if (rawText) bubble.innerHTML = renderMarkdown(rawText);

  } catch (err) {
    removeThinking();
    if (err.name === 'AbortError') {
      appendMessage('jarvis', `*Generation stopped by user.*`);
    } else {
      appendMessage('jarvis', `Network error: ${err.message}`);
    }
  } finally {
    isStreaming = false;
    abortController = null;
    const sendIcon = document.getElementById('send-icon');
    if (sendIcon) {
      sendIcon.innerHTML = '<line x1="22" y1="2" x2="11" y2="13" stroke-linecap="round" stroke-linejoin="round" stroke-width="2"/><polygon points="22 2 15 22 11 13 2 9 22 2" stroke-linecap="round" stroke-linejoin="round" stroke-width="2"/>';
      sendIcon.style.color = 'currentColor';
    }

    setWaveformState('idle');
    setTimeout(() => { loadMemoryPanel(); loadSessionsPanel(); }, 1000);
  }
}

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
    inputHint.textContent = 'Recording … click mic again to stop';
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
  inputHint.textContent = 'Transcribing …';
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
      inputHint.textContent = `Heard: "${transcript}" — press Enter or Send`;
      setTimeout(() => sendMessage(transcript), 800);
    } else {
      inputHint.textContent = 'Couldn\'t hear anything clearly. Try speaking closer to the mic.';
    }
  } catch (err) {
    inputHint.textContent = `Voice error: ${err.message}`;
  } finally {
    setWaveformState('idle');
    setTimeout(() => { inputHint.textContent = 'Press Enter to send · Shift+Enter for newline · or click 🎤 to speak'; }, 4000);
  }
}
const mobileMenuBtn = document.getElementById('mobile-menu-btn');
const leftPanel = document.getElementById('left-panel');
const mobileBackdrop = document.getElementById('mobile-backdrop');

function toggleMobileMenu() {
  const isLeftOpen = !leftPanel.classList.contains('-translate-x-full');

  if (isLeftOpen) {
    leftPanel.classList.add('-translate-x-full');
    mobileBackdrop.classList.add('opacity-0');
    setTimeout(() => mobileBackdrop.classList.add('hidden'), 300);
  } else {
    leftPanel.classList.remove('-translate-x-full');
    mobileBackdrop.classList.remove('hidden');
    setTimeout(() => mobileBackdrop.classList.remove('opacity-0'), 10);
  }
}

if (mobileMenuBtn) mobileMenuBtn.addEventListener('click', toggleMobileMenu);
if (mobileBackdrop) mobileBackdrop.addEventListener('click', toggleMobileMenu);

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
sendBtn.addEventListener('click', () => {
  if (isStreaming) {
    if (abortController) {
      abortController.abort();
      abortController = null;
    }
  } else {
    sendMessage(userInput.value);
  }
});

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
window.copyCode = function (btn) {
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
