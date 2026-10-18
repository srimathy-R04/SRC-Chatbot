(() => {
  'use strict';

  const DEFAULT_URL = 'http://127.0.0.1:5000/chat';
  const TIMEOUT_MS = 60000;
  const $ = (id) => document.getElementById(id);

  const el = {
    sidebar: $('sidebar'), overlay: $('overlay'), menuBtn: $('menuBtn'), nav: $('nav'),
    newChat: $('newChatBtn'), settingsBtn: $('settingsBtn'), modal: $('settingsModal'),
    backendUrl: $('backendUrl'), saveSettings: $('saveSettingsBtn'), resetUrl: $('resetUrlBtn'),
    clearChat: $('clearChatBtn'), chatArea: $('chatArea'), welcome: $('welcome'),
    messages: $('messages'), typing: $('typing'), form: $('chatForm'), input: $('userInput'),
    send: $('sendBtn'), lang: $('languageSelect'), status: $('status'), statusText: $('statusText'),
    landing: $('landing'), app: $('app'), enter: $('enterBtn'), historyPanel: $('historyPanel'),
    historyList: $('historyList'), historyEmpty: $('historyEmpty'), userChip: $('userChip'),
    userName: $('userName'), userSub: $('userSub'), userAvatar: $('userAvatar'),
    accountName: $('accountName'), accountSub: $('accountSub'), loginOpenBtn: $('loginOpenBtn'),
    logoutBtn: $('logoutBtn'), loginModal: $('loginModal'), loginName: $('loginName'),
    loginEmail: $('loginEmail'), loginSubmit: $('loginSubmit'), loginCancel: $('loginCancel'),
    loginError: $('loginError'),
  };

  let backendUrl = DEFAULT_URL;
  try { backendUrl = localStorage.getItem('src_backend_url') || DEFAULT_URL; } catch (_) {}

  let busy = false;
  let controller = null;

  // Frontend-only account + history (saved in this browser's localStorage)
  let user = null;
  try { user = JSON.parse(localStorage.getItem('src_user')); } catch (_) {}
  const storeKey = () => 'src_chats_' + (user ? (user.email || user.name).toLowerCase() : 'guest');
  const loadChats = () => { try { return JSON.parse(localStorage.getItem(storeKey())) || []; } catch (_) { return []; } };
  let chats = loadChats();
  let current = null;
  const saveChats = () => { try { localStorage.setItem(storeKey(), JSON.stringify(chats.slice(0, 50))); } catch (_) {} };

  function record(role, content) {
    if (!current) { current = { id: Date.now().toString(36), title: 'New chat', messages: [] }; chats.unshift(current); }
    current.messages.push({ role, content });
    if (role === 'user' && current.title === 'New chat') current.title = content.slice(0, 42);
    saveChats();
    renderHistory();
  }

  /* ---------- Helpers ---------- */
  const esc = (s) => s.replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

  // Safe, lightweight formatting: escapes HTML first, then supports **bold**, `code`, bullet lists, paragraphs.
  function format(text) {
    const inline = (s) => esc(s).replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>').replace(/`(.+?)`/g, '<code>$1</code>');
    let out = '', inList = false;
    for (const line of String(text).split('\n')) {
      const m = line.match(/^\s*[*\-•]\s+(.*)/);
      if (m) {
        if (!inList) { out += '<ul>'; inList = true; }
        out += `<li>${inline(m[1])}</li>`;
      } else {
        if (inList) { out += '</ul>'; inList = false; }
        if (line.trim()) out += `<p>${inline(line)}</p>`;
      }
    }
    return inList ? out + '</ul>' : out;
  }

  const now = () => new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  const scrollDown = () => { el.chatArea.scrollTop = el.chatArea.scrollHeight; };

  function setStatus(state, text) {
    el.status.className = 'status' + (state ? ' ' + state : '');
    el.statusText.textContent = text;
  }

  function updateSend() { el.send.disabled = busy || !el.input.value.trim(); }

  function autoGrow() {
    el.input.style.height = 'auto';
    el.input.style.height = Math.min(el.input.scrollHeight, 150) + 'px';
  }

  const BOT_ICON = '<svg class="ico" viewBox="0 0 24 24"><rect x="4" y="8" width="16" height="12" rx="4"/><path d="M12 8V5M9 14h.01M15 14h.01"/></svg>';

  function addMessage(role, content, opts = {}) {
    if (!opts.error && !opts.restore) record(role, content);
    el.welcome.hidden = true;
    const row = document.createElement('div');
    row.className = `msg ${role}${opts.error ? ' error' : ''}`;

    if (role === 'bot') {
      const av = document.createElement('div');
      av.className = 'avatar';
      av.innerHTML = BOT_ICON;
      row.appendChild(av);
    }

    const col = document.createElement('div');
    col.className = 'col';
    const bubble = document.createElement('div');
    bubble.className = 'bubble';
    if (role === 'bot') bubble.innerHTML = format(content);
    else bubble.textContent = content;
    col.appendChild(bubble);

    if (opts.retry) {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'retry';
      btn.textContent = 'Try again';
      btn.addEventListener('click', () => { row.remove(); sendMessage(opts.retry, { silentUser: true }); });
      bubble.appendChild(btn);
    }

    const t = document.createElement('span');
    t.className = 'time';
    t.textContent = now();
    col.appendChild(t);

    row.appendChild(col);
    el.messages.appendChild(row);
    scrollDown();
  }

  function showTyping(on) {
    el.typing.hidden = !on;
    if (on) scrollDown();
  }

  /* ---------- Chat ---------- */
  async function sendMessage(text, { silentUser = false } = {}) {
    text = text.trim();
    if (!text || busy) return;

    if (!silentUser) addMessage('user', text);
    el.input.value = '';
    autoGrow();
    busy = true;
    updateSend();
    showTyping(true);
    setStatus('busy', 'Thinking…');

    controller = new AbortController();
    const timer = setTimeout(() => controller.abort('timeout'), TIMEOUT_MS);

    try {
      const res = await fetch(backendUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text, language: el.lang.value }),
        signal: controller.signal,
      });

      let data = null;
      try { data = await res.json(); } catch (_) {}

      if (!res.ok) {
        throw new Error((data && (data.error || data.message)) || `Server responded with status ${res.status}.`);
      }
      if (!data || typeof data.reply !== 'string' || !data.reply.trim()) {
        throw new Error('The server replied, but the response had no "reply" field.');
      }

      addMessage('bot', data.reply);
      setStatus('', 'Online');
    } catch (err) {
      if (err.name === 'AbortError' && controller.signal.reason !== 'timeout') return; // cancelled by New Chat
      let msg;
      if (err.name === 'AbortError') msg = 'The request timed out. The assistant took too long to respond.';
      else if (err instanceof TypeError) msg = `Can't reach the backend at ${backendUrl}. Check that the Flask server is running and that CORS is enabled.`;
      else msg = err.message;
      addMessage('bot', msg, { error: true, retry: text });
      setStatus('err', 'Offline');
    } finally {
      clearTimeout(timer);
      busy = false;
      showTyping(false);
      updateSend();
      el.input.focus({ preventScroll: true });
    }
  }

  function newChat() {
    if (controller) controller.abort();
    busy = false;
    current = null;
    renderHistory();
    el.messages.innerHTML = '';
    el.welcome.hidden = false;
    showTyping(false);
    el.input.value = '';
    autoGrow();
    updateSend();
    setStatus('', 'Ready');
    el.chatArea.scrollTop = 0;
    setActive('home');
  }

  /* ---------- Sidebar / navigation ---------- */
  function setActive(section) {
    el.nav.querySelectorAll('.nav-item').forEach((b) => b.classList.toggle('active', b.dataset.section === section));
  }
  const openSidebar = (open) => {
    el.sidebar.classList.toggle('open', open);
    el.overlay.classList.toggle('show', open);
    el.menuBtn.setAttribute('aria-expanded', String(open));
  };

  el.nav.addEventListener('click', (e) => {
    const item = e.target.closest('.nav-item');
    if (!item) return;
    setActive(item.dataset.section);
    openSidebar(false);
    if (item.dataset.section === 'home') {
      if (!el.messages.children.length) el.welcome.hidden = false;
      el.chatArea.scrollTo({ top: 0 });
    } else if (item.dataset.query) {
      sendMessage(item.dataset.query);
    }
  });

  el.menuBtn.addEventListener('click', () => openSidebar(!el.sidebar.classList.contains('open')));
  el.overlay.addEventListener('click', () => openSidebar(false));
  el.newChat.addEventListener('click', () => { newChat(); openSidebar(false); });

  /* ---------- Suggested question cards ---------- */
  el.welcome.addEventListener('click', (e) => {
    const card = e.target.closest('.card');
    if (card) sendMessage(card.dataset.query);
  });

  /* ---------- Composer ---------- */
  el.form.addEventListener('submit', (e) => { e.preventDefault(); sendMessage(el.input.value); });
  el.input.addEventListener('input', () => { autoGrow(); updateSend(); });
  el.input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) {
      e.preventDefault();
      sendMessage(el.input.value);
    }
  });

  /* ---------- Landing ---------- */
  el.enter.addEventListener('click', () => {
    el.landing.classList.add('leave');
    el.app.hidden = false;
    setTimeout(() => { el.landing.hidden = true; el.input.focus({ preventScroll: true }); }, 700);
  });

  /* ---------- Sidebar tabs + history ---------- */
  document.querySelectorAll('.tab').forEach((t) => t.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach((x) => x.classList.toggle('active', x === t));
    el.nav.hidden = t.dataset.tab !== 'menu';
    el.historyPanel.hidden = t.dataset.tab !== 'history';
  }));

  function renderHistory() {
    el.historyList.innerHTML = '';
    el.historyEmpty.hidden = chats.length > 0;
    chats.forEach((c) => {
      const row = document.createElement('div');
      row.className = 'hist-item' + (current && c.id === current.id ? ' active' : '');
      const open = document.createElement('button');
      open.type = 'button'; open.className = 'hist-open'; open.textContent = c.title;
      open.addEventListener('click', () => loadChat(c.id));
      const del = document.createElement('button');
      del.type = 'button'; del.className = 'hist-del'; del.textContent = '✕';
      del.setAttribute('aria-label', 'Delete chat');
      del.addEventListener('click', () => deleteChat(c.id));
      row.append(open, del);
      el.historyList.appendChild(row);
    });
  }

  function loadChat(id) {
    const c = chats.find((x) => x.id === id);
    if (!c) return;
    if (controller) controller.abort();
    busy = false; showTyping(false); updateSend();
    el.messages.innerHTML = '';
    current = c;
    c.messages.forEach((m) => addMessage(m.role, m.content, { restore: true }));
    el.welcome.hidden = true;
    setStatus('', 'Ready');
    renderHistory();
    openSidebar(false);
  }

  function deleteChat(id) {
    chats = chats.filter((c) => c.id !== id);
    saveChats();
    if (current && current.id === id) newChat(); else renderHistory();
  }

  /* ---------- Login / logout (frontend only) ---------- */
  function updateAuthUI() {
    const name = user ? user.name : 'Guest';
    el.userName.textContent = name;
    el.userSub.textContent = user ? user.email : 'Log in to save your name';
    el.userAvatar.textContent = name.charAt(0).toUpperCase();
    el.accountName.textContent = name;
    el.accountSub.textContent = user ? user.email : 'Not logged in';
    el.loginOpenBtn.hidden = !!user;
    el.logoutBtn.hidden = !user;
  }

  function switchUser(u) {
    user = u;
    try { if (u) localStorage.setItem('src_user', JSON.stringify(u)); else localStorage.removeItem('src_user'); } catch (_) {}
    chats = loadChats();
    newChat();
    updateAuthUI();
  }

  function openLogin() {
    el.modal.hidden = true;
    el.loginError.textContent = '';
    el.loginModal.hidden = false;
    openSidebar(false);
    el.loginName.focus();
  }
  const closeLogin = () => { el.loginModal.hidden = true; };

  function submitLogin() {
    const name = el.loginName.value.trim();
    const email = el.loginEmail.value.trim();
    if (!name) { el.loginError.textContent = 'Enter your name.'; return; }
    if (!email || !el.loginEmail.checkValidity()) { el.loginError.textContent = 'Enter a valid email address.'; return; }
    switchUser({ name, email });
    el.loginName.value = ''; el.loginEmail.value = '';
    closeLogin();
  }

  el.userChip.addEventListener('click', () => { if (user) openSettings(); else openLogin(); });
  el.loginOpenBtn.addEventListener('click', openLogin);
  el.logoutBtn.addEventListener('click', () => { switchUser(null); el.modal.hidden = true; });
  el.loginSubmit.addEventListener('click', submitLogin);
  el.loginCancel.addEventListener('click', closeLogin);
  el.loginModal.addEventListener('click', (e) => { if (e.target === el.loginModal) closeLogin(); });
  [el.loginName, el.loginEmail].forEach((i) => i.addEventListener('keydown', (e) => { if (e.key === 'Enter') submitLogin(); }));
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && !el.loginModal.hidden) closeLogin(); });

  /* ---------- Settings ---------- */
  function openSettings() {
    el.backendUrl.value = backendUrl;
    el.modal.hidden = false;
    el.backendUrl.focus();
  }
  const closeSettings = () => { el.modal.hidden = true; setActive('home'); };

  el.settingsBtn.addEventListener('click', () => { setActive('settings'); openSidebar(false); openSettings(); });
  el.saveSettings.addEventListener('click', () => {
    backendUrl = el.backendUrl.value.trim() || DEFAULT_URL;
    try { localStorage.setItem('src_backend_url', backendUrl); } catch (_) {}
    closeSettings();
  });
  el.resetUrl.addEventListener('click', () => { el.backendUrl.value = DEFAULT_URL; });
  el.clearChat.addEventListener('click', () => { if (current) deleteChat(current.id); else newChat(); el.modal.hidden = true; });
  el.modal.addEventListener('click', (e) => { if (e.target === el.modal) closeSettings(); });
  document.addEventListener('keydown', (e) => {
    if (e.key !== 'Escape') return;
    if (!el.modal.hidden) closeSettings();
    else openSidebar(false);
  });

  updateSend();
  renderHistory();
  updateAuthUI();
})();
