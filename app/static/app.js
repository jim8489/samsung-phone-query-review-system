const api = '';
const grid = document.querySelector('#phone-grid');
const countLabel = document.querySelector('#phone-count');
const searchInput = document.querySelector('#phone-search');
const chatForm = document.querySelector('#chat-form');
const chatInput = document.querySelector('#chat-query');
const sendButton = document.querySelector('#send-button');
const messages = document.querySelector('#chat-messages');
let chatSessionId = null;
let allPhones = [];

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, (char) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
}

function simpleMarkdown(value) {
  let html = escapeHtml(value);
  html = html.replace(/^### (.+)$/gm, '<h3>$1</h3>').replace(/^## (.+)$/gm, '<h2>$1</h2>');
  html = html.replace(/^---$/gm, '<hr>');
  html = html.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noreferrer">$1</a>');
  html = html.replace(/^\s*[-*] (.+)$/gm, '<li>$1</li>');
  html = html.replace(/(?:<li>[\s\S]*?<\/li>\s*)+/g, (list) => `<ul>${list}</ul>`);
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  return html.replace(/\n/g, '<br>');
}

function renderPhoneCard(phone) {
  const quality = phone.data_quality === 'scraped' ? 'scraped' : 'demo_seed';
  const generation = (phone.name.match(/S\d+/i) || ['Galaxy'])[0].toUpperCase();
  return `<article class="phone-card">
    <div class="phone-card-top"><span class="phone-generation">${escapeHtml(generation)} SERIES</span><span class="quality-tag ${quality === 'scraped' ? 'scraped' : ''}">${quality === 'scraped' ? 'LIVE SCRAPED' : 'DEMO DATA'}</span></div>
    <h3>${escapeHtml(phone.name)}</h3>
    <div class="phone-chip">${escapeHtml(phone.chipset || 'Chipset not recorded')}</div>
    <div class="spec-line"><span>Display</span><span>${escapeHtml(phone.display_size || '—')}</span></div>
    <div class="spec-line"><span>Rear camera</span><span>${escapeHtml(phone.camera_rear || '—')}</span></div>
    <div class="spec-line"><span>Battery capacity</span><span>${phone.battery_capacity_mah ? `${Number(phone.battery_capacity_mah).toLocaleString()} mAh` : '—'}</span></div>
    <div class="spec-line"><span>Measured battery test</span><span>${phone.active_use_score_minutes != null ? `${Math.floor(phone.active_use_score_minutes / 60)}:${String(phone.active_use_score_minutes % 60).padStart(2, '0')}h active use` : phone.endurance_rating_hours != null ? `${phone.endurance_rating_hours}h endurance` : 'Not recorded'}</span></div>
    <div class="card-actions"><button data-action="ask" data-name="${escapeHtml(phone.name)}">Ask about model</button><button data-action="review" data-slug="${escapeHtml(phone.slug)}">Generate review</button></div>
  </article>`;
}

function renderPhones(phones) {
  countLabel.textContent = `${phones.length} MODEL${phones.length === 1 ? '' : 'S'}`;
  grid.innerHTML = phones.length ? phones.map(renderPhoneCard).join('') : '<div class="loading-card">No matching Samsung models found.</div>';
}

async function loadPhones() {
  try {
    const response = await fetch(`${api}/api/phones?limit=100`);
    if (!response.ok) throw new Error('Could not load phone catalogue');
    allPhones = await response.json();
    renderPhones(allPhones);
  } catch (error) {
    grid.innerHTML = `<div class="loading-card">${escapeHtml(error.message)}. Check that the API server is running.</div>`;
    countLabel.textContent = 'UNAVAILABLE';
  }
}

function addMessage(role, content, sources = [], mode = null) {
  const wrapper = document.createElement('div');
  wrapper.className = `message ${role === 'user' ? 'user-message' : 'assistant-message'}`;
  const label = role === 'user' ? 'YOU' : 'DEVICE ATLAS';
  let sourceHtml = '';
  if (sources.length) {
    sourceHtml = `<div class="source-list">${sources.map((source, index) => source.url
      ? `<a href="${escapeHtml(source.url)}" target="_blank" rel="noreferrer">[S${index + 1}] ${escapeHtml(source.title)} ↗</a>`
      : `<span>[S${index + 1}] ${escapeHtml(source.title)} · ${escapeHtml(source.data_quality || source.source)}</span>`).join('<br>')}</div>`;
  }
  const modeLabel = mode === 'ollama_rag' ? '<div class="response-mode">LOCAL OPEN MODEL · RAG</div>' : mode === 'rag_fallback' ? '<div class="response-mode">GROUNDED RAG FALLBACK</div>' : '';
  wrapper.innerHTML = `<div class="message-label">${label}</div><div class="message-bubble">${modeLabel}${role === 'assistant' ? simpleMarkdown(content) : escapeHtml(content)}${sourceHtml}</div>`;
  messages.appendChild(wrapper);
  messages.scrollTop = messages.scrollHeight;
}

async function askQuestion(question) {
  const query = question.trim();
  if (query.length < 2) return;
  addMessage('user', query);
  chatInput.value = '';
  sendButton.disabled = true;
  sendButton.querySelector('span').textContent = 'Thinking';
  try {
    const response = await fetch(`${api}/api/chat`, {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({query, session_id: chatSessionId})
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || 'The assistant could not answer that request.');
    chatSessionId = data.session_id;
    addMessage('assistant', data.answer, data.sources || [], data.mode);
  } catch (error) {
    addMessage('assistant', `I could not complete that request: ${error.message}`);
  } finally {
    sendButton.disabled = false;
    sendButton.querySelector('span').textContent = 'Send';
    chatInput.focus();
  }
}

chatForm.addEventListener('submit', (event) => {
  event.preventDefault();
  askQuestion(chatInput.value);
});

messages.addEventListener('click', (event) => {
  const button = event.target.closest('[data-query]');
  if (button) askQuestion(button.dataset.query);
});

searchInput.addEventListener('input', () => {
  const term = searchInput.value.trim().toLowerCase();
  renderPhones(allPhones.filter((phone) => phone.name.toLowerCase().includes(term)));
});

grid.addEventListener('click', async (event) => {
  const button = event.target.closest('button[data-action]');
  if (!button) return;
  if (button.dataset.action === 'ask') {
    document.querySelector('#assistant').scrollIntoView({behavior: 'smooth'});
    askQuestion(`Tell me about the ${button.dataset.name}: display, camera, chipset and battery.`);
  }
  if (button.dataset.action === 'review') {
    button.disabled = true;
    button.textContent = 'Generating…';
    try {
      const response = await fetch(`${api}/api/reviews/${encodeURIComponent(button.dataset.slug)}`, {
        method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({include_limitations: true})
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'Review generation failed');
      document.querySelector('#assistant').scrollIntoView({behavior: 'smooth'});
      const modeLabel = data.generation_mode === 'ollama_rag' ? 'Generated with local open model + retrieved specifications' : 'Generated with deterministic specification review';
      addMessage('assistant', `## ${data.phone} — specification-based review\n\n**${modeLabel}**\n\n${data.review}\n\n**Strengths**\n${data.strengths.map((item) => `- ${item}`).join('\n')}\n\n**Considerations**\n${data.considerations.map((item) => `- ${item}`).join('\n')}`, [data.source]);
    } catch (error) {
      alert(error.message);
    } finally {
      button.disabled = false;
      button.textContent = 'Generate review';
    }
  }
});

loadPhones();
