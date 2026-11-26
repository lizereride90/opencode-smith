const $ = (s) => document.querySelector(s);
const $$ = (s) => Array.from(document.querySelectorAll(s));

const store = {
  get(key, fallback) { try { return localStorage.getItem(key) ?? fallback; } catch { return fallback; } },
  set(key, value) { try { localStorage.setItem(key, value); } catch {} },
};

const state = { sessionId: null, busy: false, sessions: [], commands: [], skills: [], models: [], selectedCmd: 0, paletteKind: null };

function toast(message) {
  const el = $('#toast');
  el.textContent = message;
  el.classList.add('show');
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => el.classList.remove('show'), 2600);
}

async function api(path, options) {
  const response = await fetch(path, options);
  try { return await response.json(); }
  catch { return { ok: false, error: `bad response ${response.status}` }; }
}
const post = (path, body) => api(path, {
  method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
});

function escapeHTML(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

function applyPrefs() {
  const accent = store.get('accent', '242,166,90');
  document.documentElement.style.setProperty('--accent', accent);
  document.body.classList.toggle('compact', store.get('density', 'cozy') === 'compact');
  const size = store.get('fontsize', 'normal');
  document.body.dataset.font = size;
  const slider = $('#fontsize');
  if (slider) slider.value = size === 'small' ? 12 : size === 'large' ? 18 : 14;
  $$('#swatches button').forEach((b) => b.classList.toggle('on', b.dataset.accent === accent));
  $$('#density button').forEach((b) => b.classList.toggle('on', b.dataset.density === store.get('density', 'cozy')));
  const stamps = store.get('timestamps', '0') === '1';
  const input = $('#timestamps');
  if (input) input.checked = stamps;
  document.body.classList.toggle('stamps', stamps);
}

function stamp() {
  if (store.get('timestamps', '0') !== '1') return '';
  return `<div class="stamp">${new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</div>`;
}

function addMessage(role, text, error) {
  $('#intro').style.display = 'none';
  const wrap = document.createElement('div');
  wrap.className = `msg ${role}`;
  wrap.innerHTML = `<div class="who">${role === 'user' ? 'you' : '4080'}</div>
    <div><div class="bubble${error ? ' error' : ''}">${escapeHTML(text)}</div>${stamp()}</div>`;
  $('#messages').append(wrap);
  const thread = $('#thread');
  thread.scrollTop = thread.scrollHeight;
  return wrap;
}

async function loadSessions() {
  const data = await api('/api/sessions');
  if (!Array.isArray(data)) return;
  state.sessions = data.filter((s) => !/^(smith|nest (ui|chat))/i.test(s.title || ''));
  $('#chats').innerHTML = state.sessions.length
    ? state.sessions.map((s) => `<button class="chat-item ${s.id === state.sessionId ? 'on' : ''}" data-id="${escapeHTML(s.id)}">
        <i>◌</i>${escapeHTML(s.title)}</button>`).join('')
    : '<div class="side-empty">no chats yet</div>';
  $$('.chat-item').forEach((item) => item.addEventListener('click', () => openSession(item.dataset.id)));
}

async function openSession(id) {
  state.sessionId = id;
  const session = state.sessions.find((s) => s.id === id);
  $('#head-title').textContent = session ? session.title : 'chat';
  $('#messages').innerHTML = '';
  const data = await api(`/api/session/${encodeURIComponent(id)}`);
  if (!Array.isArray(data)) return;
  for (const message of data) {
    if (!message.text) continue;
    addMessage(message.role, message.text);
  }
  document.body.classList.remove('drawer');
  loadSessions();
}

function newChat() {
  state.sessionId = null;
  $('#messages').innerHTML = '';
  $('#intro').style.display = '';
  $('#head-title').textContent = 'new chat';
  $$('.chat-item').forEach((c) => c.classList.remove('on'));
  document.body.classList.remove('drawer');
  $('#input').focus();
}

async function send(text) {
  if (state.busy) return;
  state.busy = true;
  $('#send').disabled = true;
  addMessage('user', text);
  const pending = addMessage('assistant', 'gnawing the wire…');
  pending.querySelector('.bubble').classList.add('pending');
  try {
    const result = await post('/api/chat', {
      text,
      model: $('#model').value,
      agent: $('#agent').checked ? 'lowkeyy' : 'build',
      session_id: state.sessionId,
    });
    const bubbleEl = pending.querySelector('.bubble');
    bubbleEl.classList.remove('pending');
    if (result.ok) {
      bubbleEl.textContent = result.text || '(empty)';
      pending.querySelector('.stamp')?.remove();
      pending.insertAdjacentHTML('beforeend', stamp());
      if (!state.sessionId && result.sessionID) {
        state.sessionId = result.sessionID;
        loadSessions();
      }
    } else {
      bubbleEl.textContent = result.error || 'no response';
      bubbleEl.classList.add('error');
      if (result.reset) toast('quota hit — reset fired automatically');
    }
  } catch (error) {
    const bubbleEl = pending.querySelector('.bubble');
    bubbleEl.classList.remove('pending');
    bubbleEl.textContent = String(error);
    bubbleEl.classList.add('error');
  } finally {
    state.busy = false;
    $('#send').disabled = false;
  }
}

async function loadStatus() {
  const data = await api('/api/status');
  const hit = !!data.limit_detected;
  $('#usage-status').textContent = hit ? 'limit detected' : 'clear';
  $('#usage-status').style.color = hit ? '#ff9b9b' : '';
  $('#usage-project').textContent = data.project_id ? data.project_id.slice(0, 10) + '…' : '—';
  $('#installed-version').textContent = data.version || '—';
  $('#smith-status').textContent = data.smith_ready ? 'installed' : 'missing';
  $('#smith-status').style.color = data.smith_ready ? '' : '#ff9b9b';
  $('#agent-status').textContent = `${data.default_agent} (${data.agent_mode})`;
}

async function loadModels() {
  const data = await api('/api/models');
  if (!Array.isArray(data) || !data.length) return;
  state.models = data;
  const groups = new Map();
  data.forEach((m) => {
    const key = m.providerID || 'other';
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(m);
  });
  const preferred = ['opencode', 'apinex', 'openrouter', 'google', 'groq', 'orcarouter', 'teamorouter'];
  const keys = [...preferred.filter((k) => groups.has(k)), ...[...groups.keys()].filter((k) => !preferred.includes(k))];
  const previous = store.get('model', 'big-pickle');
  $('#model').innerHTML = keys.map((key) =>
    `<optgroup label="${escapeHTML(key)}">${groups.get(key).map((m) =>
      `<option value="${escapeHTML(m.id)}">${escapeHTML(m.name)}</option>`).join('')}</optgroup>`).join('');
  $('#model').value = previous;
  if (![...$('#model').options].some((o) => o.value === previous)) $('#model').value = 'big-pickle';
}

async function loadCommands() {
  const data = await api('/api/commands');
  if (Array.isArray(data)) state.commands = data;
}

async function loadSkills() {
  const data = await api('/api/skills');
  if (Array.isArray(data)) state.skills = data;
}

function updateCatalog() {
  const el = $('#catalog-counts');
  if (!el) return;
  el.textContent = `${state.models.length} models · ${state.commands.length} cmds · ${state.skills.length} skills`;
}

function atToken() {
  const input = $('#input');
  const caret = input.selectionStart ?? input.value.length;
  const before = input.value.slice(0, caret);
  const match = before.match(/(^|\s)@([^\s@]*)$/);
  return match ? { query: match[2], start: caret - match[2].length - 1, end: caret } : null;
}

function paletteItems() {
  const input = $('#input').value;
  if (state.paletteKind === 'skill') {
    const token = atToken();
    const query = (token ? token.query : '').toLowerCase();
    return state.skills.filter((s) =>
      s.id.toLowerCase().includes(query) || s.name.toLowerCase().includes(query));
  }
  const query = (input.match(/^\/([^\s]*)/) || [,''])[1].toLowerCase();
  return state.commands.filter((c) => c.name.toLowerCase().includes(query));
}

function renderPalette(items) {
  if (!items.length) {
    const label = state.paletteKind === 'skill' ? 'skill' : 'command';
    $('#palette-list').innerHTML = `<div class="palette-empty">no matching ${label}</div>`;
    return;
  }
  if (state.paletteKind === 'skill') {
    $('#palette-list').innerHTML = items.map((s, i) =>
      `<button class="cmd ${i === state.selectedCmd ? 'on' : ''}" data-id="${escapeHTML(s.id)}">
        <b>@${escapeHTML(s.id)}</b><span>${escapeHTML(s.description)}</span></button>`).join('');
    $$('.cmd').forEach((button) => button.addEventListener('click', () => insertSkill(button.dataset.id)));
    return;
  }
  $('#palette-list').innerHTML = items.map((c, i) =>
    `<button class="cmd ${i === state.selectedCmd ? 'on' : ''}" data-name="${escapeHTML(c.name)}">
      <b>/${escapeHTML(c.name)}</b><span>${escapeHTML(c.description)}</span></button>`).join('');
  $$('.cmd').forEach((button) => button.addEventListener('click', () => runCommand(button.dataset.name)));
}

function showPalette(kind) {
  state.paletteKind = kind;
  state.selectedCmd = 0;
  $('#palette-query').textContent = $('#input').value || (kind === 'skill' ? '@' : '/');
  $('#palette').classList.add('open');
  renderPalette(paletteItems());
}

function closePalette() {
  $('#palette').classList.remove('open');
  state.paletteKind = null;
}

function insertSkill(id) {
  const input = $('#input');
  const token = atToken();
  if (!token) return;
  const value = input.value.slice(0, token.start) + `@${id} ` + input.value.slice(token.end);
  input.value = value;
  const caret = token.start + id.length + 2;
  input.focus();
  input.setSelectionRange(caret, caret);
  input.style.height = 'auto';
  input.style.height = Math.min(input.scrollHeight, 180) + 'px';
  closePalette();
  $('#palette-query').textContent = value;
  toast(`${id} mentioned — send to load it`);
}

async function runCommand(name) {
  if (state.busy) return;
  const raw = $('#input').value.trim();
  const args = raw.slice(name.length + 1).trim();
  closePalette();
  $('#input').value = '';
  $('#input').style.height = 'auto';
  state.busy = true;
  $('#send').disabled = true;
  addMessage('user', `/${name}${args ? ' ' + args : ''}`);
  const pending = addMessage('assistant', 'running command…');
  pending.querySelector('.bubble').classList.add('pending');
  try {
    const result = await post('/api/command', {
      name, text: args, model: $('#model').value,
      agent: $('#agent').checked ? 'lowkeyy' : 'build',
      session_id: state.sessionId,
    });
    const bubbleEl = pending.querySelector('.bubble');
    bubbleEl.classList.remove('pending');
    if (result.ok) {
      bubbleEl.textContent = result.text || '(command returned no text)';
      if (!state.sessionId && result.sessionID) { state.sessionId = result.sessionID; loadSessions(); }
    } else {
      bubbleEl.textContent = result.error || 'command failed';
      bubbleEl.classList.add('error');
    }
  } catch (error) {
    const bubbleEl = pending.querySelector('.bubble');
    bubbleEl.classList.remove('pending');
    bubbleEl.textContent = String(error);
    bubbleEl.classList.add('error');
  } finally {
    state.busy = false;
    $('#send').disabled = false;
  }
}

function openSheet() {
  $('#sheet').classList.add('open');
  loadStatus();
}
function closeSheet() { $('#sheet').classList.remove('open'); }

async function resetUsage() {
  toast('resetting usage…');
  const result = await post('/api/reset', {});
  toast(result.ok ? 'usage reset. header synced.' : 'reset failed — check the nest logs');
  loadStatus();
}

function bind() {
  $('#composer').addEventListener('submit', (e) => {
    e.preventDefault();
    const input = $('#input');
    const text = input.value.trim();
    if (!text || state.busy) return;
    input.value = '';
    input.style.height = 'auto';
    send(text);
  });
  $('#input').addEventListener('input', (e) => {
    e.target.style.height = 'auto';
    e.target.style.height = Math.min(e.target.scrollHeight, 180) + 'px';
    if (atToken()) {
      state.paletteKind = 'skill';
      const items = paletteItems();
      $('#palette-query').textContent = e.target.value;
      $('#palette').classList.add('open');
      state.selectedCmd = Math.min(state.selectedCmd, Math.max(0, items.length - 1));
      renderPalette(items);
    } else if (e.target.value.startsWith('/')) {
      state.paletteKind = 'command';
      const items = paletteItems();
      $('#palette-query').textContent = e.target.value;
      $('#palette').classList.add('open');
      state.selectedCmd = Math.min(state.selectedCmd, Math.max(0, items.length - 1));
      renderPalette(items);
    } else closePalette();
  });
  $('#input').addEventListener('keydown', (e) => {
    const open = $('#palette').classList.contains('open');
    const items = open ? paletteItems() : [];
    if (e.key === 'ArrowDown' && items.length) {
      e.preventDefault();
      state.selectedCmd = (state.selectedCmd + 1) % items.length;
      renderPalette(items);
      return;
    }
    if (e.key === 'ArrowUp' && items.length) {
      e.preventDefault();
      state.selectedCmd = (state.selectedCmd - 1 + items.length) % items.length;
      renderPalette(items);
      return;
    }
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (open && items.length && state.paletteKind === 'skill') {
        insertSkill(items[state.selectedCmd].id);
        return;
      }
      if (open && items.length) { runCommand(items[state.selectedCmd].name); return; }
      if (open && !items.length) { closePalette(); return; }
      $('#composer').requestSubmit();
    }
  });
  $('#palette').addEventListener('click', (e) => { if (e.target === $('#palette')) closePalette(); });
  $('#model').addEventListener('change', () => store.set('model', $('#model').value));
  $('#cmd-open').addEventListener('click', () => {
    showPalette('command');
    $('#input').focus();
  });
  $('#skill-open').addEventListener('click', () => {
    const input = $('#input');
    if (!atToken()) input.value = (input.value && !input.value.endsWith(' ') ? input.value + ' ' : input.value) + '@';
    input.focus();
    input.setSelectionRange(input.value.length, input.value.length);
    showPalette('skill');
  });
  $('#new-chat').addEventListener('click', newChat);
  $('#menu').addEventListener('click', () => document.body.classList.add('drawer'));
  $('#close-side').addEventListener('click', () => document.body.classList.remove('drawer'));
  $('#scrim').addEventListener('click', () => document.body.classList.remove('drawer'));
  $('#settings-open').addEventListener('click', openSheet);
  $('#settings-open-2').addEventListener('click', openSheet);
  $('#settings-close').addEventListener('click', closeSheet);
  $('#sheet').addEventListener('click', (e) => { if (e.target === $('#sheet')) closeSheet(); });
  $('#reset').addEventListener('click', resetUsage);
  $('#sync').addEventListener('click', async () => {
    await post('/api/sync-header', {});
    toast('header synced');
    loadStatus();
  });

  $$('#swatches button').forEach((button) => button.addEventListener('click', () => {
    store.set('accent', button.dataset.accent);
    applyPrefs();
  }));
  $$('#density button').forEach((button) => button.addEventListener('click', () => {
    store.set('density', button.dataset.density);
    applyPrefs();
  }));
  $('#fontsize').addEventListener('input', (e) => {
    const value = Number(e.target.value);
    const size = value <= 12 ? 'small' : value >= 18 ? 'large' : 'normal';
    store.set('fontsize', size);
    applyPrefs();
  });
  $('#timestamps').addEventListener('change', (e) => {
    store.set('timestamps', e.target.checked ? '1' : '0');
    applyPrefs();
  });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') { closeSheet(); closePalette(); }
  });
}

(async function boot() {
  applyPrefs();
  bind();
  await Promise.all([loadSessions(), loadStatus(), loadModels(), loadCommands(), loadSkills()]);
  updateCatalog();
})();
