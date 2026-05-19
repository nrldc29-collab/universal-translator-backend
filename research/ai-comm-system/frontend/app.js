const socket = io();
let lastTranslation = '';

function append(msg, role) {
  const div = document.getElementById("chat");
  const p = document.createElement("p");
  const text = typeof msg === "string" ? msg : JSON.stringify(msg);
  p.className = role ? `msg ${role}` : '';
  const content = document.createElement('span');
  content.className = 'text';
  content.textContent = text;
  const copy = document.createElement('button');
  copy.className = 'copy-inline';
  copy.textContent = 'Copy';
  copy.addEventListener('click', (e) => {
    e.stopPropagation();
    try { navigator.clipboard.writeText(text); } catch {}
  });
  const ts = document.createElement('span');
  ts.className = 'timestamp';
  ts.textContent = new Date().toLocaleTimeString();
  p.appendChild(content);
  p.appendChild(copy);
  p.appendChild(ts);
  div.appendChild(p);
  div.scrollTop = div.scrollHeight;
}

function send() {
  const el = document.getElementById("input");
  const lang = document.getElementById("lang");
  const text = el.value.trim();
  if (!text) return;
  socket.emit("message", {
    text,
    sessionId: "demo",
    targetLanguage: lang?.value || 'es',
    sttConfidence: 0.9,
    noise: 0.1,
    id: String(Date.now())
  });
  append(text, 'user');
  el.value = "";
}

socket.on("connect", () => {
  append("Connected.", 'ai');
  document.getElementById('status-text').textContent = 'Online';
  document.getElementById('status-dot').classList.add('online');
});
socket.on("disconnect", () => {
  document.getElementById('status-text').textContent = 'Disconnected';
  document.getElementById('status-dot').classList.remove('online');
});
socket.on("message", (data) => {
  if (data?.translated) {
    lastTranslation = data.translated;
    append(`→ ${data.targetLanguage}: ${data.translated}`, 'ai');
    const autoplay = document.getElementById('autoplay-voice')?.checked;
    if (autoplay && window.speechSynthesis) {
      try {
        const u = new SpeechSynthesisUtterance(data.translated);
        u.lang = (data.targetLanguage || 'es');
        window.speechSynthesis.speak(u);
      } catch (e) {
        append(`tts-error: ${e?.message || e}`);
      }
    }
  } else {
    append(data, 'ai');
  }
  // Clarification UI
  const clarifyBar = document.getElementById('clarify');
  const clarifyText = document.getElementById('clarify-text');
  if (data?.decision?.type === 'clarification') {
    clarifyText.textContent = data?.decision?.message || 'Clarification requested.';
    clarifyBar.style.display = 'block';
  } else if (clarifyBar.style.display !== 'none') {
    clarifyBar.style.display = 'none';
  }
});

window.addEventListener("DOMContentLoaded", () => {
  document.getElementById("send").addEventListener("click", send);
  document.getElementById("input").addEventListener("keydown", (e) => {
    if (e.key === "Enter") send();
  });
  document.getElementById('copy-last').addEventListener('click', (e) => {
    e.preventDefault();
    if (!lastTranslation) return;
    try { navigator.clipboard.writeText(lastTranslation); } catch {}
  });
  document.getElementById('clear-chat').addEventListener('click', (e) => {
    e.preventDefault();
    const div = document.getElementById('chat');
    div.innerHTML = '';
  });
  // Keepalive ping
  setInterval(() => socket.emit('ping'), 15000);
  socket.on('pong', () => {/* no-op */});
  socket.on('ack', (m) => append(`ack: ${JSON.stringify(m)}`));
  const toast = document.getElementById('toast');
  function showToast(t) {
    if (!toast) return;
    toast.textContent = t;
    toast.style.display = 'block';
    setTimeout(() => { toast.style.display = 'none'; }, 1800);
  }

  // Web Speech API (STT) if available
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (SpeechRecognition) {
    const rec = new SpeechRecognition();
    rec.continuous = true;
    rec.interimResults = false;
    document.getElementById('start-speech').addEventListener('click', () => {
      try { rec.start(); } catch {}
    });
    document.getElementById('stop-speech').addEventListener('click', () => {
      try { rec.stop(); } catch {}
    });
    rec.onresult = (e) => {
      const last = e.results[e.results.length - 1];
      if (last && last.isFinal) {
        document.getElementById('input').value = last[0].transcript;
        send();
      }
    };
    rec.onerror = (e) => showToast(`STT error: ${e?.error || 'unknown'}`);
  } else {
    document.getElementById('start-speech').disabled = true;
    document.getElementById('stop-speech').disabled = true;
  }

  // Refine action: suggests a clearer rephrase and resends
  document.getElementById('refine').addEventListener('click', () => {
    const el = document.getElementById('input');
    const original = el.value || '';
    const suggestion = original ? `Please clarify: ${original}` : 'Please clarify your request.';
    el.value = suggestion;
    send();
    showToast('Sent refined phrase');
  });

  document.getElementById('toggle-hc').addEventListener('click', (e) => {
    e.preventDefault();
    document.documentElement.classList.toggle('hc');
  });
});
