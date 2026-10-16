/* MyGPT frontend — chat, feedback loop, teaching, growth and the
   CORTEX self-learning mind (facts, constitution, skills, goals, import). */

const $ = (id) => document.getElementById(id);
const chatEl = $("chat");

const MODE_LABELS = {
  memory: "recalled",
  guess: "guessing",
  curious: "curious",
  math: "computed",
  skill: "skill",
  fact: "fact recall",
  code: "code",
  cortex: "cortex llm",
  ollama: "ollama llm",
};

/* ---------------- helpers ---------------- */

async function api(path, body = null) {
  const opts = body === null
    ? {}
    : {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      };
  const res = await fetch(path, opts);
  return res.json();
}

/* /api/stats is read by the Growth and Mind panels and refreshed after every
   chat turn — dedupe concurrent callers onto one in-flight request with a
   short cache so the server isn't hammered for identical data. */
let _statsInFlight = null;
let _statsCache = { t: 0, data: null };
const STATS_TTL_MS = 2500;
function fetchStats(force = false) {
  const now = Date.now();
  if (!force && _statsCache.data && now - _statsCache.t < STATS_TTL_MS) {
    return Promise.resolve(_statsCache.data);
  }
  if (!_statsInFlight) {
    _statsInFlight = api("/api/stats")
      .then((d) => {
        _statsCache = { t: Date.now(), data: d };
        return d;
      })
      .finally(() => { _statsInFlight = null; });
  }
  return _statsInFlight;
}

function toast(text) {
  const t = $("toast");
  t.textContent = text;
  t.classList.add("show");
  clearTimeout(t._timer);
  t._timer = setTimeout(() => t.classList.remove("show"), 2600);
}

function scrollDown(force = false) {
  // don't yank the view away when the user is reading back up the log
  const nearBottom =
    chatEl.scrollHeight - chatEl.scrollTop - chatEl.clientHeight < 140;
  if (force || nearBottom) chatEl.scrollTop = chatEl.scrollHeight;
}

function fmtTime(ts) {
  const d = new Date(ts * 1000);
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

/* ---------------- theme + text size (v1.9) ---------------- */

const THEME_KEY = "mygpt.theme";
const ZOOM_KEY = "mygpt.zoom";

function applyTheme(mode) {
  // mode: "light" | "dark"; the button cycles dark ⇄ light
  document.documentElement.dataset.theme = mode;
  try { localStorage.setItem(THEME_KEY, mode); } catch (e) { /* private mode */ }
  const meta = document.querySelector('meta[name="theme-color"]');
  if (meta) meta.setAttribute("content", mode === "light" ? "#f4f6fb" : "#0b0e14");
}

function initTheme() {
  let saved = null;
  try { saved = localStorage.getItem(THEME_KEY); } catch (e) { /* ignore */ }
  if (saved === "light" || saved === "dark") return applyTheme(saved);
  const prefersLight = window.matchMedia &&
    window.matchMedia("(prefers-color-scheme: light)").matches;
  applyTheme(prefersLight ? "light" : "dark");
}

function toggleTheme() {
  applyTheme(document.documentElement.dataset.theme === "light" ? "dark" : "light");
  toast(document.documentElement.dataset.theme === "light"
    ? "☀️ light theme" : "🌙 dark theme");
}

const ZOOMS = [0.9, 1.0, 1.1, 1.25, 1.4];

function applyZoom(level) {
  const i = Math.max(0, Math.min(ZOOMS.length - 1, level));
  document.documentElement.style.fontSize = (15 * ZOOMS[i]) + "px";
  try { localStorage.setItem(ZOOM_KEY, String(i)); } catch (e) { /* ignore */ }
  return i;
}

function initZoom() {
  let i = 1;
  try { i = parseInt(localStorage.getItem(ZOOM_KEY) || "1", 10); } catch (e) { /* ignore */ }
  if (!Number.isFinite(i)) i = 1;
  applyZoom(i);
}

function bumpZoom(delta) {
  let i = 1;
  try { i = parseInt(localStorage.getItem(ZOOM_KEY) || "1", 10); } catch (e) { /* ignore */ }
  const next = applyZoom((Number.isFinite(i) ? i : 1) + delta);
  toast(`🔤 text size ${Math.round(ZOOMS[next] * 100)}%`);
}

/* ---------------- dependency-free Python syntax highlighting ----------
   Regex-based, HTML-escaped first, comment/string tokens masked so later
   passes can't colour inside them. Good enough for chat snippets. */

const PY_KEYWORDS = /\b(def|class|return|if|elif|else|for|while|import|from|as|with|try|except|finally|raise|yield|lambda|in|is|not|and|or|None|True|False|pass|break|continue|global|nonlocal|assert|del|async|await|match|case)\b/g;

function escapeHtml(s) {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;")
          .replace(/>/g, "&gt;");
}

function highlightPython(code) {
  const masks = [];
  const mask = (html) => {
    masks.push(html);
    return "\u0000" + (masks.length - 1) + "\u0000";
  };
  let out = escapeHtml(code);
  // order matters: triple-quoted → strings → comments
  out = out.replace(/("""[\s\S]*?"""|'''[\s\S]*?''')/g,
                    (m) => mask(`<span class="hl-str">${m}</span>`));
  out = out.replace(/(&quot;|")(?:[^"\\\n]|\\.)*\1|'(?:[^'\\\n]|\\.)*'/g,
                    (m) => mask(`<span class="hl-str">${m}</span>`));
  out = out.replace(/(#[^\n]*)/g, (m) => mask(`<span class="hl-com">${m}</span>`));
  out = out.replace(/\b(0x[0-9a-fA-F]+|\d+(?:\.\d+)?(?:e[+-]?\d+)?)\b/g,
                    '<span class="hl-num">$1</span>');
  out = out.replace(/@[A-Za-z_][\w.]*/g, '<span class="hl-dec">$&</span>');
  out = out.replace(PY_KEYWORDS, '<span class="hl-kw">$1</span>');
  return out.replace(/\u0000(\d+)\u0000/g, (_, i) => masks[+i]);
}

/* ---------------- chat rendering ---------------- */

let _lastMsgDay = null;
let _unread = 0;

function dayKey(d) {
  return `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`;
}

function dayLabel(d) {
  const now = new Date();
  const midnight = (x) => new Date(x.getFullYear(), x.getMonth(), x.getDate());
  const diff = Math.round((midnight(now) - midnight(d)) / 86400000);
  if (diff === 0) return "Today";
  if (diff === 1) return "Yesterday";
  return d.toLocaleDateString([], { day: "numeric", month: "short", year: "numeric" });
}

/* A subtle day divider whenever messages cross a date boundary. */
function maybeDateSeparator(opts = {}) {
  const d = opts.ts ? new Date(opts.ts * 1000) : new Date();
  const key = dayKey(d);
  if (key === _lastMsgDay) return;
  _lastMsgDay = key;
  const sep = document.createElement("div");
  sep.className = "date-sep";
  sep.textContent = dayLabel(d);
  chatEl.appendChild(sep);
}

function addMessage(role, text, opts = {}) {
  maybeDateSeparator(opts);
  const msg = document.createElement("div");
  msg.className = `msg ${role}`;
  const avatar = document.createElement("div");
  avatar.className = "avatar";
  avatar.textContent = role === "bot" ? "🤖" : "🧑";
  const wrap = document.createElement("div");
  wrap.className = "bubble-wrap";
  const bubble = document.createElement("div");
  bubble.className = "bubble";
  if (role === "bot" && text.includes("```")) renderFenced(bubble, text);
  else bubble.textContent = text;
  wrap.appendChild(bubble);
  wrap.title = new Date().toLocaleTimeString() +
    " — double-click to copy this message";
  wrap.addEventListener("dblclick", async () => {
    try {
      await navigator.clipboard.writeText(bubble.innerText);
      toast("Message copied ⧉");
    } catch (err) {
      toast("⚠️ clipboard unavailable");
    }
  });
  msg.append(avatar, wrap);
  chatEl.appendChild(msg);
  const wasAway =
    chatEl.scrollHeight - chatEl.scrollTop - chatEl.clientHeight > 200;
  scrollDown(!!opts.force);
  updateScrollButton();
  if (opts.force && wasAway && !opts.quiet) {
    _unread += 1;
    const btn = $("scroll-bottom");
    if (btn) {
      btn.classList.add("pulse");
      btn.textContent = `⌄ ${_unread} new`;
    }
  }
  return wrap;
}

/* ---------------- composer: textarea behaviour, drafts, scroll button ---- */

const DRAFT_KEY = "mygpt.draft";
const inputEl = () => $("input");

function autoGrow() {
  const el = inputEl();
  el.style.height = "auto";
  el.style.height = Math.min(el.scrollHeight, 150) + "px";
}

function saveDraft() {
  try { localStorage.setItem(DRAFT_KEY, inputEl().value); } catch (e) { /* private mode */ }
}

function restoreDraft() {
  try {
    const d = localStorage.getItem(DRAFT_KEY);
    if (d) { inputEl().value = d; autoGrow(); }
  } catch (e) { /* ignore */ }
}

function updateScrollButton() {
  const btn = $("scroll-bottom");
  if (!btn) return;
  const away =
    chatEl.scrollHeight - chatEl.scrollTop - chatEl.clientHeight > 200;
  btn.classList.toggle("hidden", !away);
  if (!away) {                       // back at the bottom → clear the badge
    _unread = 0;
    btn.classList.remove("pulse");
    btn.textContent = "⌄";
  }
}

function updateOnlineStatus() {
  const dot = $("status-dot"), txt = $("status-text");
  if (!dot || !txt) return;
  if (navigator.onLine) {
    dot.classList.remove("off");
    txt.textContent = "online & learning";
  } else {
    dot.classList.add("off");
    txt.textContent = "offline — reconnecting…";
  }
}
window.addEventListener("online", updateOnlineStatus);
window.addEventListener("offline", updateOnlineStatus);

/* Render plain text segments plus ``` fenced blocks as real <pre><code>. */
function renderFenced(bubble, text) {
  const re = /```(\w*)\n([\s\S]*?)```/g;
  let last = 0, m;
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) {
      const span = document.createElement("span");
      span.textContent = text.slice(last, m.index);
      bubble.appendChild(span);
    }
    const lang = m[1] || "python";
    const code = m[2].replace(/\n+$/, "");
    const box = document.createElement("div");
    box.className = "code-box";
    const head = document.createElement("div");
    head.className = "code-head";
    const label = document.createElement("span");
    label.className = "code-lang";
    label.textContent = lang;
    const copy = document.createElement("button");
    copy.type = "button";
    copy.className = "code-copy";
    copy.textContent = "⧉ copy";
    copy.title = "Copy just this code block";
    copy.onclick = async () => {
      try {
        await navigator.clipboard.writeText(code);
        copy.textContent = "✓ copied";
        setTimeout(() => { copy.textContent = "⧉ copy"; }, 1400);
      } catch (err) {
        toast("⚠️ clipboard unavailable");
      }
    };
    head.append(label, copy);
    const pre = document.createElement("pre");
    const codeEl = document.createElement("code");
    if (lang === "python" || lang === "py") {
      codeEl.innerHTML = highlightPython(code);   // escaped inside
    } else {
      codeEl.textContent = code;
    }
    pre.appendChild(codeEl);
    box.append(head, pre);
    bubble.appendChild(box);
    last = m.index + m[0].length;
  }
  if (last < text.length) {
    const span = document.createElement("span");
    span.textContent = text.slice(last);
    bubble.appendChild(span);
  }
}

function addChain(chain, wrap) {
  if (!chain || !chain.steps || chain.steps.length < 2) return;
  const det = document.createElement("details");
  det.className = "chain";
  const sum = document.createElement("summary");
  sum.textContent =
    `💭 ${chain.system === 2 ? "System-2 thinking" : "Thinking"} · ` +
    `${chain.strategy} · conf ${Math.round(chain.confidence * 100)}%`;
  det.appendChild(sum);
  const ol = document.createElement("ol");
  for (const s of chain.steps) {
    const li = document.createElement("li");
    const b = document.createElement("b");
    b.textContent = s.kind;
    li.append(b, document.createTextNode(" " + s.text));
    ol.appendChild(li);
  }
  det.appendChild(ol);
  if (chain.hypotheses && chain.hypotheses.length > 1 && chain.system === 2) {
    const hyp = document.createElement("div");
    hyp.className = "hyp";
    hyp.append(document.createTextNode("Candidates: "));
    chain.hypotheses.forEach((h, i) => {
      const em = document.createElement("em");
      em.textContent = `${h.label} ${Math.round(h.score * 100)}%`;
      hyp.appendChild(em);
      if (i < chain.hypotheses.length - 1) hyp.append(document.createTextNode(" · "));
    });
    det.appendChild(hyp);
  }
  wrap.appendChild(det);
}

function addBotReply(data, elapsedMs) {
  if (document.hidden) flashTitle(1);
  const wrap = addMessage("bot", data.reply);
  addMessageActions(wrap, data.reply);
  addChain(data.chain, wrap);

  const meta = document.createElement("div");
  meta.className = "meta-row";
  const tag = document.createElement("span");
  tag.className = "mode-tag" + (data.mode === "skill" ? " skill" : "");
  tag.textContent = data.mode === "skill" && data.skill
    ? `skill: ${data.skill}` : (MODE_LABELS[data.mode] || data.mode);
  meta.appendChild(tag);
  if (elapsedMs != null) {
    const ms = document.createElement("span");
    ms.className = "mode-tag";
    ms.title = "end-to-end reply time";
    ms.textContent = `⏱ ${elapsedMs} ms`;
    meta.appendChild(ms);
  }

  if (data.teach_prompt) {
    const chip = document.createElement("button");
    chip.className = "teach-chip";
    chip.textContent = "✏️ Teach me this";
    chip.onclick = () => {
      $("teach-q").value = lastUserText;
      switchTab("learn");
      $("teach-a").focus();
    };
    wrap.appendChild(chip);
  }

  const copy = document.createElement("button");
  copy.className = "copy-btn";
  copy.textContent = "⧉";
  copy.title = "Copy reply";
  copy.onclick = async () => {
    try {
      await navigator.clipboard.writeText(data.reply);
      toast("Reply copied to clipboard ⧉");
    } catch (err) {
      toast("⚠️ clipboard unavailable");
    }
  };
  meta.appendChild(copy);

  if (data.id && data.mode !== "curious") {
    const fb = document.createElement("div");
    fb.className = "fb";
    const up = document.createElement("button");
    up.textContent = "👍";
    up.title = "Good answer — reinforce it";
    const down = document.createElement("button");
    down.textContent = "👎";
    down.title = "Bad answer — correct me";
    up.onclick = () => sendFeedback(data.id, "up", null, up, down, fb);
    down.onclick = () => openCorrection(data.id, down, up, fb);
    fb.append(up, down);
    meta.appendChild(fb);
  }
  wrap.appendChild(meta);
  scrollDown();
}

let lastUserText = "";
let busy = false;

/* Streaming chat: consume /api/chat/stream (SSE) and type the reply in.
   Returns the final result object, or throws so send() can fall back. */
async function streamChat(text, bubble) {
  const res = await fetch("/api/chat/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message: text }),
  });
  if (!res.ok || !res.body) throw new Error("stream unavailable");
  const reader = res.body.getReader();
  const dec = new TextDecoder();
  let buf = "";
  let typed = "";
  let final = null;
  let firstToken = true;
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    let idx;
    while ((idx = buf.indexOf("\n\n")) !== -1) {
      const block = buf.slice(0, idx);
      buf = buf.slice(idx + 2);
      let event = "message";
      const dataLines = [];
      for (const line of block.split("\n")) {
        if (line.startsWith("event:")) event = line.slice(6).trim();
        else if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
      }
      let payload = null;
      try { payload = JSON.parse(dataLines.join("\n")); } catch (e) { continue; }
      if (event === "token" && payload && payload.t) {
        if (firstToken) { bubble.textContent = ""; firstToken = false; }
        typed += payload.t;
        bubble.textContent = typed;                 // typewriter effect
        scrollDown();
      } else if (event === "done" && payload) {
        final = payload;
      }
    }
  }
  if (!final) throw new Error("stream ended early");
  return { ok: true, ...final };
}

async function send() {
  const input = $("input");
  const text = input.value.trim();
  if (!text || busy) return;
  if (!navigator.onLine) {
    queueMessage(text);
    input.value = "";
    autoGrow();
    updateCharCount();
    saveDraft();
    toast("📴 queued — it will send when you're back online");
    return;
  }
  busy = true;
  chatEl.setAttribute("aria-busy", "true");   // screen readers: reply pending
  lastUserText = text;
  input.value = "";
  input.style.height = "auto";
  saveDraft();
  $("send").disabled = true;

  const userWrap = addMessage("user", text, { force: true });
  addMessageActions(userWrap, text);
  const typingWrap = addMessage("bot", "", { force: true });
  typingWrap.querySelector(".bubble").innerHTML =
    '<span class="typing"><span></span><span></span><span></span></span>';

  const t0 = Date.now();
  let data;
  const bubble = typingWrap.querySelector(".bubble");
  try {
    data = await streamChat(text, bubble);       // typewriter via SSE
  } catch (err) {
    try {                                        // graceful fallback
      data = await api("/api/chat", { message: text });
    } catch (err2) {
      data = { ok: false, error: String(err2) };
    }
  }
  if (data && data.ok) {
    const wait = 240 - (Date.now() - t0);
    if (wait > 0) await new Promise((r) => setTimeout(r, wait));
  } else {
    const wait = 420 - (Date.now() - t0);
    if (wait > 0) await new Promise((r) => setTimeout(r, wait));
  }

  typingWrap.closest(".msg").remove();
  const elapsed = Date.now() - t0;
  if (data.ok) {
    if (prefs.sound === "on") chime();
    maybeNotify(data.reply || "");
    addBotReply(data, elapsed);
  } else {
    const wrap = addMessage("bot", "⚠️ " + (data.error || "something went wrong"));
    const retry = document.createElement("button");
    retry.className = "teach-chip";
    retry.textContent = "↻ Retry";
    retry.onclick = () => { wrap.closest(".msg").remove(); input.value = text; send(); };
    wrap.appendChild(retry);
  }

  busy = false;
  chatEl.removeAttribute("aria-busy");
  $("send").disabled = false;
  input.focus();
  refreshSidebars();
}

/* ---------------- feedback ---------------- */

async function sendFeedback(msgId, verdict, correction, upBtn, downBtn, fbRow) {
  const data = await api("/api/feedback", { msg_id: msgId, verdict, correction });
  if (!data.ok) return toast(data.error || "feedback failed");
  if (upBtn) upBtn.classList.add("active-up");
  if (downBtn) downBtn.classList.add("active-down");
  fbRow.querySelectorAll("button").forEach((b) => (b.disabled = true));
  const note = document.createElement("span");
  note.className = "fb-note";
  note.textContent = data.message;
  fbRow.appendChild(note);
  toast(verdict === "up" ? "Thanks! Answer reinforced." : "Feedback logged.");
  refreshSidebars();
}

function openCorrection(msgId, downBtn, upBtn, fbRow) {
  if (fbRow.querySelector(".corr")) return;
  const box = document.createElement("div");
  box.className = "corr";
  box.style.cssText = "display:flex;gap:6px;margin-top:6px;";
  const inp = document.createElement("input");
  inp.type = "text";
  inp.placeholder = "What should I have said?";
  inp.style.cssText =
    "flex:1;background:var(--panel);border:1px solid var(--border);" +
    "color:var(--text);border-radius:8px;padding:7px 10px;font-size:.8rem;outline:none;min-width:180px;";
  const ok = document.createElement("button");
  ok.textContent = "Learn it";
  ok.style.cssText =
    "background:var(--user-bubble);border:none;color:#fff;border-radius:8px;" +
    "padding:7px 12px;cursor:pointer;font-size:.78rem;";
  ok.onclick = async () => {
    const correction = inp.value.trim();
    if (!correction) return inp.focus();
    await sendFeedback(msgId, "down", correction, upBtn, downBtn, fbRow);
    box.remove();
  };
  inp.addEventListener("keydown", (e) => e.key === "Enter" && ok.click());
  box.append(inp, ok);
  fbRow.closest(".bubble-wrap").appendChild(box);
  inp.focus();
}

/* ---------------- sidebar ---------------- */

function switchTab(name) {
  document.querySelectorAll(".tab").forEach((t) =>
    t.classList.toggle("active", t.dataset.tab === name));
  $("panel-learn").classList.toggle("hidden", name !== "learn");
  $("panel-growth").classList.toggle("hidden", name !== "growth");
  $("panel-mind").classList.toggle("hidden", name !== "mind");
  $("panel-model").classList.toggle("hidden", name !== "model");
  if (name === "growth") refreshStats();
  if (name === "model") refreshModelTab();
  if (name === "mind") {
    refreshMind();
    refreshCortex();
    refreshOllama();
    refreshBackends();
  }
}

/* ---------------- Cortex LLMHoster backend ---------------- */

function renderCortexStatus(c) {
  const pill = $("cx-pill");
  const status = $("cx-status");
  const models = $("cx-models");
  pill.className = "pill";
  if (!c.enabled) {
    pill.textContent = "off";
    pill.classList.add("cx-off");
  } else if (c.reachable) {
    pill.textContent = "connected";
    pill.classList.add("cx-on");
  } else {
    pill.textContent = "unreachable";
    pill.classList.add("cx-bad");
  }
  const bits = [];
  if (!c.enabled) bits.push("Backend disabled — MyGPT answers with its self-trained brain.");
  else if (c.reachable) bits.push(`Connected at ${c.base_url}${c.api_base}.`);
  else bits.push(`Can't reach ${c.base_url} — MyGPT falls back to its self-trained brain.`);
  if (c.answers) bits.push(`${c.answers} open question${c.answers === 1 ? "" : "s"} answered by the hosted model so far.`);
  if (c.reason) bits.push(c.reason);
  status.textContent = bits.join(" ");
  status.className = "cx-status " + (c.reachable ? "good" : (c.enabled ? "warn" : ""));

  models.innerHTML = "";
  for (const m of c.models || []) {
    const li = document.createElement("li");
    const caps = (m.capabilities || []).join(", ");
    li.textContent = `🧠 ${m.id}` + (m.runtime ? ` · ${m.runtime}` : "") + (caps ? ` · ${caps}` : "");
    models.appendChild(li);
  }
  if (c.reachable && !(c.models || []).length) {
    const li = document.createElement("li");
    li.className = "empty";
    li.textContent = "No models configured in Cortex yet — add one in the Cortex dashboard.";
    models.appendChild(li);
  }
}

async function refreshCortex() {
  const c = await api("/api/cortex");
  $("cx-url").value = c.base_url || "";
  $("cx-apibase").value = c.api_base || "";
  $("cx-model").value = c.model || "";
  $("cx-enabled").checked = !!c.enabled;
  $("cx-learn").checked = !!c.learn;
  renderCortexStatus(c);
}

/* ---------------- Ollama backend ---------------- */

function renderOllamaStatus(c) {
  const pill = $("ol-pill");
  const status = $("ol-status");
  const models = $("ol-models");
  pill.className = "pill";
  if (!c.enabled) {
    pill.textContent = "off";
    pill.classList.add("cx-off");
  } else if (c.reachable) {
    pill.textContent = "connected";
    pill.classList.add("cx-on");
  } else {
    pill.textContent = "unreachable";
    pill.classList.add("cx-bad");
  }
  const bits = [];
  if (!c.enabled) bits.push("Backend disabled — MyGPT answers with its self-trained brain.");
  else if (c.reachable) bits.push(`Connected at ${c.base_url}.`);
  else bits.push(`Can't reach ${c.base_url} — MyGPT falls back to its self-trained brain.`);
  if (c.answers) bits.push(`${c.answers} open question${c.answers === 1 ? "" : "s"} answered by Ollama so far.`);
  if (c.reason) bits.push(c.reason);
  status.textContent = bits.join(" ");
  status.className = "cx-status " + (c.reachable ? "good" : (c.enabled ? "warn" : ""));

  models.innerHTML = "";
  for (const m of c.models || []) {
    const li = document.createElement("li");
    const size = m.size ? ` · ${(m.size / 1e9).toFixed(1)} GB` : "";
    li.textContent = `🦙 ${m.id}` + (m.family ? ` · ${m.family}` : "") + size;
    models.appendChild(li);
  }
  if (c.reachable && !(c.models || []).length) {
    const li = document.createElement("li");
    li.className = "empty";
    li.textContent = "No models pulled yet — run `ollama pull <model>` in a terminal.";
    models.appendChild(li);
  }
}

async function refreshOllama() {
  const c = await api("/api/ollama");
  $("ol-url").value = c.base_url || "";
  $("ol-model").value = c.model || "";
  $("ol-enabled").checked = !!c.enabled;
  $("ol-learn").checked = !!c.learn;
  renderOllamaStatus(c);
}

/* ---------------- model picker + checkpoints ---------------- */

function backendValue(b) {
  return b.chat_model ? `${b.chat_backend}:${b.chat_model}` : b.chat_backend;
}

function renderBackendPicker(b) {
  const sel = $("backend-select");
  const pill = $("backend-pill");
  const cx = (b.options && b.options.cortex) || {};
  const ol = (b.options && b.options.ollama) || {};
  const current = backendValue(b);
  const seen = new Set(["auto", "brain", "cortex", "ollama"]);
  sel.innerHTML = "";

  const add = (value, label, disabled) => {
    const opt = document.createElement("option");
    opt.value = value;
    opt.textContent = label;
    opt.disabled = !!disabled;
    sel.appendChild(opt);
    seen.add(value);
  };
  add("auto", "⚡ Auto (brain → Cortex → Ollama)");
  add("brain", "🧠 MyGPT self-trained brain");
  if (cx.enabled && cx.reachable) {
    add("cortex", "🖥️ Cortex · default model");
    for (const m of cx.models || []) add(`cortex:${m.id}`, `🖥️ Cortex · ${m.id}`);
  }
  if (ol.enabled && ol.reachable) {
    add("ollama", "🦙 Ollama · default model");
    for (const m of ol.models || []) add(`ollama:${m.id}`, `🦙 Ollama · ${m.id}`);
  }
  // keep a manually configured model selectable even if not listed
  if (b.chat_model && !seen.has(current)) add(current, `${b.chat_backend} · ${b.chat_model}`);

  sel.value = current;
  if (sel.value !== current) sel.value = b.chat_backend || "auto";

  pill.className = "mb-pill";
  if (b.chat_backend === "brain") {
    pill.textContent = "self-trained brain";
    pill.classList.add("mb-brain");
    pill.title = "Open questions answered by MyGPT's own NumPy brain";
  } else if (b.chat_backend === "auto") {
    pill.textContent = "auto routing";
    pill.classList.add("mb-auto");
    pill.title = "Brain first, then Cortex LLMHoster, then Ollama";
  } else {
    pill.textContent = b.chat_model || `${b.chat_backend} default`;
    pill.classList.add("mb-hosted");
    pill.title = `Open questions answered by ${b.chat_backend}`;
  }
}

function renderCheckpoints(list) {
  $("ckpt-pill").textContent = (list || []).length;
  const ul = $("ckpt-list");
  ul.innerHTML = "";
  if (!(list || []).length) {
    ul.innerHTML = '<li class="empty">No checkpoints yet — save one above, or tell me in chat to checkpoint the model.</li>';
    return;
  }
  for (const c of list) {
    const li = document.createElement("li");
    const info = document.createElement("div");
    info.className = "ck-info";
    const name = document.createElement("b");
    name.textContent = c.name;
    const when = new Date(c.created * 1000).toLocaleString();
    const meta = document.createElement("span");
    meta.className = "ck-meta";
    meta.textContent = `${when} · vocab ${c.vocab ?? "?"}` +
      (c.loss != null ? ` · loss ${Number(c.loss).toFixed(3)}` : "") +
      (c.note ? ` · “${c.note}”` : "");
    info.append(name, meta);
    const btns = document.createElement("div");
    btns.className = "ck-btns";
    const load = document.createElement("button");
    load.className = "mini primary-mini";
    load.textContent = "Load";
    load.title = "Load these weights as the active brain";
    load.onclick = async () => {
      load.disabled = true;
      const d = await api("/api/checkpoint/load", { name: c.name });
      load.disabled = false;
      if (!d.ok) return toast(d.error || "load failed");
      // the loaded weights ARE the brain — make sure it's the active engine
      await api("/api/backends/select", { backend: "brain", model: "" });
      toast(`Checkpoint ${c.name} is now the active brain 🧠`);
      refreshBackends();
    };
    const dl = document.createElement("button");
    dl.className = "mini ghost-mini";
    dl.textContent = "⬇";
    dl.title = "download checkpoint (weights + meta) as zip";
    dl.onclick = () => {
      window.location.href =
        "/api/checkpoint/download?name=" + encodeURIComponent(c.name);
    };
    const del = document.createElement("button");
    del.className = "mini ghost-mini";
    del.textContent = "✕";
    del.title = "delete this checkpoint";
    del.onclick = async () => {
      if (!confirm(`Delete checkpoint ${c.name} from _model_trained/?`)) return;
      const d = await api("/api/checkpoint/delete", { name: c.name });
      if (!d.ok) return toast(d.error || "delete failed");
      toast("Checkpoint deleted.");
      refreshBackends();
    };
    btns.append(load, dl, del);
    li.append(info, btns);
    ul.appendChild(li);
  }
}

function renderProbePill(b) {
  const pill = $("probe-pill");
  if (!pill) return;
  const ap = b.auto_probe || {};
  const cxUp = !!(b.options.cortex || {}).reachable;
  const olUp = !!(b.options.ollama || {}).reachable;
  const found = [];
  if (cxUp) found.push("Cortex");
  if (olUp) found.push("Ollama");
  if (found.length) {
    pill.textContent = `🔎 ${found.join(" + ")} detected`;
    pill.className = "mb-probe on";
  } else {
    pill.textContent = "🔎 auto-probing for local LLMs…";
    pill.className = "mb-probe";
  }
  if (ap.last_check) {
    pill.title = `Auto-probe every ${ap.interval_s || 20}s · last check ` +
      new Date(ap.last_check * 1000).toLocaleTimeString();
  }
}

function renderInstallHint(b) {
  const box = $("install-hint");
  const text = $("install-hint-text");
  const hint = b.install_hint;
  if (!hint || sessionStorage.getItem("installHintDismissed")) {
    box.classList.add("hidden");
    return;
  }
  text.innerHTML = "";
  const lead = document.createElement("span");
  lead.innerHTML = `<b>${hint.title}.</b> ${hint.message} Try: `;
  text.appendChild(lead);
  (hint.options || []).forEach((opt, i) => {
    const a = document.createElement("a");
    a.href = opt.repo || opt.url;
    a.target = "_blank";
    a.rel = "noopener";
    a.innerHTML = `<b>${opt.name}</b>` +
      (opt.author ? ` <em>by ${opt.author}</em>` : "");
    a.title = opt.hint || "";
    text.appendChild(a);
    if (i < hint.options.length - 1) text.append(document.createTextNode(" · "));
  });
  const note = document.createElement("span");
  note.className = "ih-note";
  note.textContent = " MyGPT auto-probes every 20 s and picks them up " +
    "automatically once one is running.";
  text.appendChild(note);
  box.classList.remove("hidden");
}

let backendsInFlight = null;
function refreshBackends() {
  if (!backendsInFlight) {
    backendsInFlight = api("/api/backends")
      .then((b) => {
        if (b.ok) {
          renderBackendPicker(b);
          renderCheckpoints(b.checkpoints || []);
          renderProbePill(b);
          renderInstallHint(b);
        }
      })
      .finally(() => { backendsInFlight = null; });
  }
  return backendsInFlight;
}
// follow the server-side auto-probe so the UI notices new local LLMs on its own
setInterval(() => { refreshBackends(); }, 15000);

async function refreshMemory() {
  const data = await api("/api/memory");
  const list = $("memory-list");
  list.innerHTML = "";
  $("pair-count").textContent = data.pairs ? data.pairs.length : 0;
  if (!data.pairs || !data.pairs.length) {
    list.innerHTML = '<li class="empty">Nothing learned yet.</li>';
    return;
  }
  for (const p of data.pairs) {
    const li = document.createElement("li");
    const w = document.createElement("span");
    w.className = "w";
    w.textContent = `w ${p.w} · ${p.hits}✓`;
    const q = document.createElement("div");
    q.className = "q";
    q.textContent = p.q;
    const a = document.createElement("div");
    a.className = "a";
    a.textContent = p.a.length > 90 ? p.a.slice(0, 90) + "…" : p.a;
    li.append(w, q, a);
    list.appendChild(li);
  }
}

async function refreshStats(force = false) {
  const data = await fetchStats(force);
  $("st-pairs").textContent = data.pairs;
  $("st-msgs").textContent = data.counters.messages;
  $("st-up").textContent = data.counters.up;
  $("st-corr").textContent = data.counters.corrections;
  $("st-vocab").textContent = data.vocab_size;
  $("st-rounds").textContent = data.counters.train_rounds;
  if (data.version) $("up-version").textContent = "v" + data.version;

  drawChart(data.loss_history);

  const ev = $("events");
  ev.innerHTML = "";
  if (!data.events.length) ev.innerHTML = '<li class="empty">No activity yet.</li>';
  for (const e of data.events) {
    const li = document.createElement("li");
    const time = document.createElement("span");
    time.className = "time";
    time.textContent = fmtTime(e.t);
    li.append(time, document.createTextNode(e.text));
    ev.appendChild(li);
  }
}

function refreshSidebars(force = true) {
  refreshMemory();
  if (!$("panel-growth").classList.contains("hidden")) refreshStats(force);
  if (!$("panel-mind").classList.contains("hidden")) refreshMind(force);
}

/* ---------------- loss chart ---------------- */

function drawChart(history) {
  const canvas = $("loss-chart");
  const ctx = canvas.getContext("2d");
  const W = canvas.width, H = canvas.height, pad = 26;
  ctx.clearRect(0, 0, W, H);

  if (!history || history.length < 2) {
    $("chart-caption").textContent =
      "Not enough training rounds yet — chat, give feedback or press Train now.";
    ctx.strokeStyle = "#232d42";
    ctx.strokeRect(pad, pad / 2, W - pad * 1.5, H - pad * 1.5);
    return;
  }

  const losses = history.map((h) => h.loss);
  const max = Math.max(...losses), min = Math.min(...losses);
  const span = max - min || 1;
  const x = (i) => pad + (i / (losses.length - 1)) * (W - pad * 1.8);
  const y = (v) => pad / 2 + (1 - (v - min) / span) * (H - pad * 1.6);

  ctx.strokeStyle = "#232d42";
  ctx.lineWidth = 1;
  for (let g = 0; g <= 3; g++) {
    const gy = pad / 2 + (g / 3) * (H - pad * 1.6);
    ctx.beginPath(); ctx.moveTo(pad, gy); ctx.lineTo(W - pad * 0.8, gy); ctx.stroke();
  }

  const grad = ctx.createLinearGradient(0, 0, 0, H);
  grad.addColorStop(0, "rgba(124,92,255,.35)");
  grad.addColorStop(1, "rgba(124,92,255,0)");
  ctx.beginPath();
  losses.forEach((v, i) => (i ? ctx.lineTo(x(i), y(v)) : ctx.moveTo(x(i), y(v))));
  ctx.lineTo(x(losses.length - 1), H - pad);
  ctx.lineTo(x(0), H - pad);
  ctx.closePath();
  ctx.fillStyle = grad;
  ctx.fill();

  ctx.beginPath();
  losses.forEach((v, i) => (i ? ctx.lineTo(x(i), y(v)) : ctx.moveTo(x(i), y(v))));
  const lineGrad = ctx.createLinearGradient(pad, 0, W, 0);
  lineGrad.addColorStop(0, "#7c5cff");
  lineGrad.addColorStop(1, "#00d4c8");
  ctx.strokeStyle = lineGrad;
  ctx.lineWidth = 2.5;
  ctx.stroke();

  const lx = x(losses.length - 1), ly = y(losses[losses.length - 1]);
  ctx.beginPath(); ctx.arc(lx, ly, 4, 0, Math.PI * 2);
  ctx.fillStyle = "#00d4c8"; ctx.fill();

  ctx.fillStyle = "#8b95ab";
  ctx.font = "11px Inter, sans-serif";
  ctx.fillText(max.toFixed(2), 2, pad / 2 + 8);
  ctx.fillText(min.toFixed(2), 2, H - pad * 1.2);

  const drop = (((max - losses[losses.length - 1]) / (max || 1)) * 100).toFixed(0);
  $("chart-caption").textContent =
    `${history.length} training rounds · loss ${max.toFixed(2)} → ` +
    `${losses[losses.length - 1].toFixed(2)} (${drop}% improvement)`;
}

/* ---------------- mind tab (self-learning loop) ---------------- */

async function refreshMind(force = false) {
  const data = await fetchStats(force);
  const mind = data.mind || {};
  const tr = mind.trainer || {};

  $("mn-status").textContent = tr.busy ? "training…" : (tr.queue ? `queue ${tr.queue}` : "idle");
  $("mn-steps").textContent = tr.done_steps || 0;
  $("mn-loss").textContent = tr.last_loss || "–";
  const evals = mind.self_eval || [];
  $("mn-eval").textContent = evals.length ? `${Math.round(evals[evals.length - 1].v * 100)}%` : "–";
  $("mn-cycles").textContent = data.counters.cycles || 0;
  $("mn-constit").textContent = `v${data.constitution_version}`;
  $("mn-constit-pill").textContent = `v${data.constitution_version}`;
  $("mn-episodes").textContent = data.episodes || 0;
  $("mn-imports").textContent = data.imports || 0;

  // constitution
  const pr = $("principles");
  pr.innerHTML = "";
  for (const p of mind.principles || []) {
    const li = document.createElement("li");
    li.textContent = p;
    pr.appendChild(li);
  }

  // facts (with forget buttons)
  $("mn-facts-pill").textContent = (mind.facts || []).length;
  const fl = $("facts-list");
  fl.innerHTML = "";
  if (!(mind.facts || []).length)
    fl.innerHTML = '<li class="empty">No facts yet — say “my name is …” or “note: …”.</li>';
  for (const f of mind.facts || []) {
    const li = document.createElement("li");
    const triple = document.createElement("span");
    triple.className = "triple";
    const b = document.createElement("b");
    b.textContent = `${f.subject} ${f.predicate}`;
    triple.append(b, document.createTextNode(` ${f.object}`));
    const conf = document.createElement("span");
    conf.className = "conf";
    conf.textContent = `${Math.round(f.confidence * 100)}%`;
    const x = document.createElement("button");
    x.className = "forget";
    x.textContent = "✕";
    x.title = "forget this fact";
    x.onclick = async () => {
      await api("/api/forget", { q: `${f.subject} ${f.predicate} ${f.object}` });
      toast("Fact forgotten.");
      refreshMind();
    };
    li.append(triple, conf, x);
    fl.appendChild(li);
  }

  // lessons
  $("mn-lessons-pill").textContent = (mind.lessons || []).length;
  const ll = $("lessons-list");
  ll.innerHTML = "";
  if (!(mind.lessons || []).length)
    ll.innerHTML = '<li class="empty">No self-critique lessons yet.</li>';
  for (const l of mind.lessons || []) {
    const li = document.createElement("li");
    li.textContent = l;
    ll.appendChild(li);
  }

  // skills
  $("mn-skills-pill").textContent = (mind.skills || []).length;
  const sl = $("skills-list");
  sl.innerHTML = "";
  for (const s of mind.skills || []) {
    const li = document.createElement("li");
    const nm = document.createElement("span");
    nm.className = "sname";
    nm.textContent = `${s.name} · ${s.path}`;
    const ds = document.createElement("span");
    ds.textContent = s.description;
    li.append(nm, ds);
    sl.appendChild(li);
  }

  // goals
  const gl = $("goals-list");
  gl.innerHTML = "";
  for (const g of data.goals || []) {
    const li = document.createElement("li");
    const title = document.createElement("div");
    title.className = "gtitle";
    const name = document.createElement("span");
    name.textContent = g.title;
    const pct = document.createElement("span");
    pct.textContent = `${Math.round((g.progress || 0) * 100)}%`;
    title.append(name, pct);
    const bar = document.createElement("div");
    bar.className = "gbar";
    const fill = document.createElement("div");
    fill.className = "gfill";
    fill.style.width = `${Math.round((g.progress || 0) * 100)}%`;
    bar.appendChild(fill);
    const why = document.createElement("div");
    why.className = "gwhy";
    why.textContent = g.why || "";
    li.append(title, bar, why);
    gl.appendChild(li);
  }

  // recent improvement events
  const ev = $("improve-events");
  ev.innerHTML = "";
  const events = mind.events || [];
  if (!events.length) ev.innerHTML = '<li class="empty">No improvement events yet.</li>';
  for (const e of events.slice(0, 12)) {
    const li = document.createElement("li");
    const kind = document.createElement("span");
    kind.className = "kind";
    kind.textContent = e.kind;
    const time = document.createElement("span");
    time.className = "time";
    time.textContent = fmtTime(e.t);
    const text = e.payload && e.payload.text ? e.payload.text
      : e.payload && e.payload.object ? `${e.payload.subject} ${e.payload.predicate} ${e.payload.object}`
      : e.payload && e.payload.score !== undefined ? `score ${Math.round(e.payload.score * 100)}%`
      : JSON.stringify(e.payload);
    li.append(kind, time, document.createTextNode(text));
    ev.appendChild(li);
  }
}

/* ---------------- actions ---------------- */

$("composer").addEventListener("submit", (e) => {
  e.preventDefault();
  send();
});

/* textarea: Enter sends, Shift+Enter inserts a newline */
$("input").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    send();
  }
  if (e.key === "Escape") {
    $("input").value = "";
    saveDraft();
    autoGrow();
  }
});
$("input").addEventListener("input", () => {
  autoGrow();
  saveDraft();
  updateCharCount();
});
chatEl.addEventListener("scroll", updateScrollButton);
$("scroll-bottom").addEventListener("click", () => {
  scrollDown(true);
  updateScrollButton();
});

/* "/" focuses the composer (vim/chat style), unless you're already typing */
document.addEventListener("keydown", (e) => {
  if (e.key === "/" && !["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement.tagName)) {
    e.preventDefault();
    $("input").focus();
  }
});

document.querySelectorAll(".tab").forEach((t) =>
  t.addEventListener("click", () => switchTab(t.dataset.tab)));

$("teach-btn").addEventListener("click", async () => {
  const q = $("teach-q").value.trim();
  const a = $("teach-a").value.trim();
  if (!q || !a) return toast("Fill in both question and answer.");
  $("teach-btn").disabled = true;
  const data = await api("/api/teach", { question: q, answer: a });
  $("teach-btn").disabled = false;
  if (!data.ok) return toast(data.error || "teaching failed");
  $("teach-q").value = "";
  $("teach-a").value = "";
  toast("Learned! That's part of me now. 🧠");
  refreshSidebars();
});

/* Ctrl/Cmd+Enter in the teach form submits it */
["teach-q", "teach-a"].forEach((id) =>
  $(id).addEventListener("keydown", (e) => {
    if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) $("teach-btn").click();
  }));

$("train-btn").addEventListener("click", async () => {
  const btn = $("train-btn");
  btn.disabled = true;
  btn.textContent = "Training…";
  const data = await api("/api/train", { epochs: parseInt($("epochs").value, 10) });
  btn.disabled = false;
  btn.textContent = "🏋️ Train now";
  if (data.ok) toast(`Training done — loss ${data.loss} in ${data.took_ms} ms.`);
  refreshStats();
});

$("dream-btn").addEventListener("click", async () => {
  const box = $("dream-box");
  box.classList.remove("hidden");
  box.textContent = "dreaming…";
  const data = await api("/api/dream");
  box.textContent = "💭 “" + data.text + "”";
});

$("improve-btn").addEventListener("click", async () => {
  const btn = $("improve-btn");
  btn.disabled = true;
  btn.textContent = "Improving…";
  const data = await api("/api/improve", {});
  btn.disabled = false;
  btn.textContent = "🔁 Run improvement cycle";
  if (data.ok) {
    const n = (data.events || []).length;
    toast(`Improvement cycle done — ${n} event${n === 1 ? "" : "s"}.`);
  }
  refreshMind();
});

$("eval-btn").addEventListener("click", async () => {
  const btn = $("eval-btn");
  const box = $("eval-box");
  btn.disabled = true;
  btn.textContent = "Evaluating…";
  box.classList.remove("hidden");
  box.textContent = "Running the self-evaluation battery…";
  const d = await api("/api/eval", {});
  btn.disabled = false;
  btn.textContent = "🧪 Self-eval";
  if (!d.ok) {
    box.textContent = "⚠️ " + (d.error || "self-eval failed");
    return;
  }
  box.innerHTML = "";
  const head = document.createElement("div");
  head.className = "eval-head";
  head.innerHTML = `Score: <b>${d.hits}/${d.total}</b> ` +
    `(${Math.round(d.score * 100)}%)`;
  box.appendChild(head);
  for (const r of d.results || []) {
    const row = document.createElement("div");
    row.className = "eval-row" + (r.passed ? " pass" : " fail");
    row.textContent = `${r.passed ? "✅" : "❌"} ${r.q}`;
    row.title = r.answer || "";
    box.appendChild(row);
  }
  toast(`Self-eval: ${Math.round(d.score * 100)}%`);
});

$("export-btn").addEventListener("click", async () => {
  const btn = $("export-btn");
  btn.disabled = true;
  try {
    const res = await fetch("/api/export");
    if (!res.ok) throw new Error("export failed");
    const blob = await res.blob();
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    const disp = res.headers.get("Content-Disposition") || "";
    const m = disp.match(/filename="([^"]+)"/);
    a.download = m ? m[1] : "mygpt-transcript.md";
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(a.href);
    toast("Conversation exported as Markdown ⬇️");
  } catch (err) {
    toast("⚠️ " + err);
  }
  btn.disabled = false;
});

$("cx-save").addEventListener("click", async () => {
  const btn = $("cx-save");
  btn.disabled = true;
  btn.textContent = "Testing…";
  const body = {
    enabled: $("cx-enabled").checked,
    learn: $("cx-learn").checked,
    base_url: $("cx-url").value.trim(),
    api_base: $("cx-apibase").value.trim() || "/v1",
    model: $("cx-model").value.trim(),
  };
  const key = $("cx-key").value;
  if (key) body.api_key = key;   // empty = keep whatever is stored
  const c = await api("/api/cortex", body);
  $("cx-key").value = "";
  renderCortexStatus(c);
  btn.disabled = false;
  btn.textContent = "💾 Save & test connection";
  if (c.reachable) toast("Cortex LLMHoster connected ✅");
  else if (c.enabled) toast("Settings saved — Cortex not reachable yet");
  else toast("Cortex backend disabled");
  refreshMind();
});

$("ol-save").addEventListener("click", async () => {
  const btn = $("ol-save");
  btn.disabled = true;
  btn.textContent = "Testing…";
  const c = await api("/api/ollama", {
    enabled: $("ol-enabled").checked,
    learn: $("ol-learn").checked,
    base_url: $("ol-url").value.trim(),
    model: $("ol-model").value.trim(),
  });
  renderOllamaStatus(c);
  btn.disabled = false;
  btn.textContent = "💾 Save & test connection";
  if (c.reachable) toast("Ollama connected ✅");
  else if (c.enabled) toast("Settings saved — Ollama not reachable yet");
  else toast("Ollama backend disabled");
  refreshBackends();
});

$("install-hint-x").addEventListener("click", () => {
  sessionStorage.setItem("installHintDismissed", "1");
  $("install-hint").classList.add("hidden");
});

$("backend-select").addEventListener("change", async () => {
  const sel = $("backend-select");
  const val = sel.value;
  let backend, model = "";
  const idx = val.indexOf(":");
  if (idx > 0) {
    backend = val.slice(0, idx);
    model = val.slice(idx + 1);
  } else {
    backend = val;
  }
  const d = await api("/api/backends/select", { backend, model });
  if (!d.ok) return toast(d.error || "selection failed");
  const label = model ? `${backend} · ${model}` : backend;
  toast(`Open questions now answered by ${label}.`);
  refreshBackends();
});

$("ckpt-save").addEventListener("click", async () => {
  const btn = $("ckpt-save");
  const status = $("ckpt-status");
  btn.disabled = true;
  btn.textContent = "Saving…";
  status.textContent = "Snapshotting the trained weights to _model_trained/…";
  status.className = "cx-status";
  const d = await api("/api/checkpoint", {
    label: $("ckpt-label").value.trim(),
    train: $("ckpt-train").checked,
  });
  btn.disabled = false;
  btn.textContent = "📸 Checkpoint model";
  if (!d.ok) {
    status.textContent = "⚠️ " + (d.error || "checkpoint failed");
    status.className = "cx-status warn";
    return;
  }
  const c = d.checkpoint;
  const trained = d.train ? ` Trained ${d.train.epochs ?? "?"} epochs first (loss ${d.train.loss}).` : "";
  status.textContent = `✅ Saved ${c.name} — vocab ${c.vocab ?? "?"}` +
    (c.loss != null ? `, loss ${Number(c.loss).toFixed(3)}` : "") + `.${trained}`;
  status.className = "cx-status good";
  $("ckpt-label").value = "";
  toast(`Checkpoint saved to _model_trained/${c.name}/ 📸`);
  refreshBackends();
});

/* ---------------- software updates ---------------- */

let pendingUpdate = null;   // UpdateInfo from the last successful check

function setUpStatus(text, kind) {
  const el = $("up-status");
  el.textContent = text;
  el.className = "up-status " + (kind || "");
}

async function checkUpdate() {
  const btn = $("up-check");
  btn.disabled = true;
  $("up-install").disabled = true;
  pendingUpdate = null;
  setUpStatus("Checking the codero-sus/MyGPT branch on GitHub…");
  try {
    const res = await fetch("/api/update/check");
    const d = await res.json();
    if (!d.ok) {
      setUpStatus("⚠️ " + (d.error || "update check failed"), "warn");
      return;
    }
    pendingUpdate = d;
    const short = d.commit_sha.slice(0, 7);
    if (d.update_available) {
      setUpStatus(
        `Update available: v${d.current_version} → v${d.latest_version} ` +
        `(branch ${d.source_ref}, commit ${short}). Confirm to install.`, "good");
      $("up-install").disabled = false;
    } else {
      setUpStatus(
        `You're on the latest branch version (v${d.latest_version}, ` +
        `commit ${short}). No update needed.`, "good");
    }
  } catch (err) {
    setUpStatus("⚠️ " + err, "warn");
  } finally {
    btn.disabled = false;
  }
}

async function installUpdate() {
  if (!pendingUpdate) return;
  const short = pendingUpdate.commit_sha.slice(0, 7);
  const ok = confirm(
    `Install MyGPT update from commit ${short} ` +
    `(v${pendingUpdate.latest_version})?\n\n` +
    `Your learned data/ is preserved. You must restart the server afterwards.`);
  if (!ok) return;
  const btn = $("up-install");
  btn.disabled = true;
  $("up-check").disabled = true;
  setUpStatus("Downloading and installing the pinned update…");
  try {
    const res = await fetch("/api/update/install", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ commit_sha: pendingUpdate.commit_sha }),
    });
    const d = await res.json();
    if (!d.ok) {
      setUpStatus("⚠️ " + (d.error || "install failed"), "warn");
      return;
    }
    setUpStatus(
      `✅ Installed v${d.installed_version} (commit ${d.commit_sha.slice(0, 7)}). ` +
      `Preserved: ${d.preserved.join(", ")}. ` +
      `Restart the server to load the new version.`, "good");
    toast("Update installed — restart MyGPT to finish.");
  } catch (err) {
    setUpStatus("⚠️ " + err, "warn");
  } finally {
    $("up-check").disabled = false;
    pendingUpdate = null;
  }
}

$("up-check").addEventListener("click", checkUpdate);
$("up-install").addEventListener("click", installUpdate);

$("import-btn").addEventListener("click", async () => {
  const fileInput = $("import-file");
  const out = $("import-result");
  if (!fileInput.files.length) return toast("Choose a chat export file first.");
  const btn = $("import-btn");
  btn.disabled = true;
  btn.textContent = "Importing…";
  out.textContent = "";
  const form = new FormData();
  form.append("file", fileInput.files[0]);
  try {
    const res = await fetch("/api/import", { method: "POST", body: form });
    const data = await res.json();
    if (data.ok) {
      out.textContent =
        `✅ ${data.filename}: ${data.source.join(", ")} · ${data.threads} thread(s), ` +
        `${data.turns} turns → ${data.remembered} episodes remembered, ` +
        `${data.trained} training snips queued. The core is learning them now.`;
      toast("Chat history absorbed into the mind.");
      fileInput.value = "";
    } else {
      out.textContent = "⚠️ " + (data.error || "import failed");
    }
  } catch (err) {
    out.textContent = "⚠️ " + err;
  }
  btn.disabled = false;
  btn.textContent = "📥 Import";
  refreshMind();
});

/* ---------------- chat search (Ctrl+K) ---------------- */

function applyChatFilter(term) {
  const q = term.trim().toLowerCase();
  let shown = 0;
  chatEl.querySelectorAll(".msg").forEach((m) => {
    const hit = !q || m.innerText.toLowerCase().includes(q);
    m.classList.toggle("filtered-out", !hit);
    if (hit) shown += 1;
  });
  if (q && shown === 0) {
    toast("No messages match “" + term.trim() + "”");
  }
}

$("chat-search").addEventListener("input", (e) => applyChatFilter(e.target.value));
$("chat-search").addEventListener("keydown", (e) => {
  if (e.key === "Escape") {
    e.target.value = "";
    applyChatFilter("");
    e.target.blur();
  }
});

/* ---------------- clear transcript ---------------- */

async function clearChat() {
  const msgs = chatEl.querySelectorAll(".msg").length;
  if (!msgs) return toast("Nothing to clear.");
  if (!window.confirm("Clear the visible transcript and its saved copy?\n" +
                      "Your learned memories and facts are kept.")) return;
  let data = { ok: true };
  try {
    data = await api("/api/clear", {});
  } catch (err) {
    toast("⚠️ could not reach the server");
    return;
  }
  if (!data.ok) return toast("⚠️ " + (data.error || "clear failed"));
  chatEl.innerHTML = "";
  _lastMsgDay = null;
  _unread = 0;
  addMessage("bot", GREETING);
  addChips();
  toast(`🧹 transcript cleared (${data.cleared} message(s) forgotten)`);
  refreshSidebars();
}

$("clear-btn").addEventListener("click", clearChat);

/* ---------------- drag & drop a chat export ---------------- */

function initDragDrop() {
  const panel = document.querySelector(".chat-panel");
  if (!panel) return;
  ["dragenter", "dragover"].forEach((ev) =>
    panel.addEventListener(ev, (e) => {
      e.preventDefault();
      panel.classList.add("dropping");
    }));
  ["dragleave", "drop"].forEach((ev) =>
    panel.addEventListener(ev, (e) => {
      e.preventDefault();
      if (ev === "dragleave" && panel.contains(e.relatedTarget)) return;
      panel.classList.remove("dropping");
    }));
  panel.addEventListener("drop", async (e) => {
    const file = e.dataTransfer && e.dataTransfer.files[0];
    if (!file) return;
    const form = new FormData();
    form.append("file", file);
    toast("📥 importing " + file.name + " …");
    try {
      const res = await fetch("/api/import", { method: "POST", body: form });
      const data = await res.json();
      if (data.ok) {
        toast(`✅ ${data.turns} turns → ${data.remembered} episodes remembered`);
        refreshSidebars();
      } else {
        toast("⚠️ " + (data.error || "import failed"));
      }
    } catch (err) {
      toast("⚠️ " + err);
    }
  });
}

/* ---------------- bulk teach ---------------- */

$("bulk-btn").addEventListener("click", async () => {
  const raw = $("bulk-text").value;
  const pairs = raw.split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const i = line.indexOf("::");
      if (i === -1) return { question: line, answer: "" };   // reported as error
      return { question: line.slice(0, i).trim(), answer: line.slice(i + 2).trim() };
    });
  const note = $("bulk-note");
  if (!pairs.length) { note.textContent = "⚠️ nothing to teach — one pair per line."; return; }
  if (pairs.length > 100) {
    note.textContent = `⚠️ ${pairs.length} pairs — the server caps a batch at 100.`;
    return;
  }
  const btn = $("bulk-btn");
  btn.disabled = true;
  btn.textContent = "Teaching…";
  try {
    const data = await api("/api/teach/bulk", { pairs });
    if (data.stored) {
      note.textContent = `✅ stored ${data.stored} pair(s)` +
        (data.failed ? ` · ${data.failed} skipped` : "");
      if (!data.failed) $("bulk-text").value = "";
      toast(`📚 learned ${data.stored} new pair(s)`);
    } else {
      note.textContent = "⚠️ " + (data.errors?.[0]?.error || data.error || "nothing stored");
    }
  } catch (err) {
    note.textContent = "⚠️ " + err;
  }
  btn.disabled = false;
  btn.textContent = "Teach all";
  refreshSidebars();
});

/* ---------------- memory search panel ---------------- */

let _memSearchTimer = null;
$("mem-search").addEventListener("input", (e) => {
  const q = e.target.value.trim();
  clearTimeout(_memSearchTimer);
  const list = $("mem-search-results");
  if (!q) { list.innerHTML = ""; return; }
  _memSearchTimer = setTimeout(async () => {
    try {
      const res = await fetch("/api/memory/search?q=" + encodeURIComponent(q) +
                              "&k=5");
      const data = await res.json();
      list.innerHTML = "";
      if (!data.hits || !data.hits.length) {
        const li = document.createElement("li");
        li.className = "memory-empty";
        li.textContent = "no matches — teach me this!";
        list.appendChild(li);
        return;
      }
      data.hits.forEach((h) => {
        const li = document.createElement("li");
        const bq = document.createElement("b");
        bq.textContent = h.q;
        const sp = document.createElement("span");
        sp.className = "mem-score";
        sp.textContent = " " + Math.round(h.score * 100) + "%";
        const br = document.createElement("div");
        br.className = "memory-a";
        br.textContent = h.a;
        li.append(bq, sp, br);
        list.appendChild(li);
      });
    } catch (err) { /* ignore transient errors */ }
  }, 220);
});

/* ---------------- global keyboard shortcuts ---------------- */

document.addEventListener("keydown", (e) => {
  const mod = e.ctrlKey || e.metaKey;
  if (mod && e.shiftKey && e.key.toLowerCase() === "e") {
    e.preventDefault();
    $("export-btn").click();
  } else if (mod && e.shiftKey && e.key.toLowerCase() === "l") {
    e.preventDefault();
    clearChat();
  } else if (mod && e.key.toLowerCase() === "k") {
    e.preventDefault();
    $("chat-search").focus();
    $("chat-search").select();
  } else if (e.altKey && ["1", "2", "3", "4"].includes(e.key)) {
    e.preventDefault();
    switchTab({ "1": "learn", "2": "growth", "3": "mind", "4": "model" }[e.key]);
  } else if (e.target === $("input") && (mod || e.ctrlKey) && e.key === "Enter") {
    e.preventDefault();
    send();
  } else if (e.target === $("input") && e.key === "ArrowUp" &&
             !$("input").value && lastUserText) {
    e.preventDefault();
    $("input").value = lastUserText;          // recall the last message
    autoGrow();
    $("input").setSelectionRange(lastUserText.length, lastUserText.length);
  }
});

/* ---------------- composer character counter ---------------- */

function updateCharCount() {
  const el = $("char-count");
  if (!el) return;
  const n = $("input").value.length;
  if (n > 3000) {
    el.textContent = `${n} / 4000`;
    el.classList.toggle("near-limit", n > 3800);
    el.classList.remove("hidden");
  } else {
    el.classList.add("hidden");
  }
}


/* ======================================================================
   v1.10 UI pack — density, contrast, motion, sidebar, sound, pins,
   share/print/help/about, first/copy-all/edit-last, idle pause, offline
   queue, chat-batch helpers, notification + title badge.
   ====================================================================== */

/* ===== v1.11 Model tab: architecture, engines, generation ================= */

async function refreshModel(force = false) {
  let data;
  try {
    data = await (await fetch("/api/model")).json();
  } catch (e) {
    return;
  }
  const num = (n) => (n ?? 0).toLocaleString();
  const set = (id, v) => { const el = $(id); if (el) el.textContent = v; };
  set("md-arch", data.arch === "transformer" ? "transformer" : "MLP");
  set("md-params", num(data.params));
  set("md-blocks", data.blocks ?? "–");
  set("md-heads", data.heads ?? "–");
  set("md-dim", data.dim ?? "–");
  set("md-ctx", data.context ?? "–");
  set("md-steps", num(data.training_steps));
  set("md-vocab", num(data.vocab));
  set("md-loss", data.last_loss == null ? "–" : Number(data.last_loss).toFixed(3));
  const vision = $("md-vision");
  if (vision) {
    vision.textContent = data.vision || "feed-forward network (classic NeuralLM)";
  }
  const meta = $("md-meta");
  if (meta && data.training) {
    meta.innerHTML = `<span class="tag">${escapeHtml(data.training)}</span>` +
      `<span class="tag">${num(data.tokens_trained)} tokens trained</span>` +
      `<span class="tag">${num(data.corpus_lines)} corpus lines</span>` +
      `<span class="tag">${num(data.checkpoints)} checkpoints</span>`;
  }
  const pill = $("md-engine-pill");
  if (pill) pill.textContent = (data.backends && data.backends.brain)
    ? (data.backends.brain.arch || "brain") : "brain";
}

function engineBadge(info) {
  if (info.available) return '<span class="badge ok">ready</span>';
  if (info.enabled === false) return '<span class="badge off">disabled</span>';
  return '<span class="badge warn">not set up</span>';
}

function renderEngines(engines) {
  const list = $("engine-list");
  if (!list) return;
  const order = ["brain", "cortex", "ollama", "llamacpp", "hf"];
  const labels = {
    brain: "MyGPT self-trained brain", cortex: "Cortex LLMHoster",
    ollama: "Ollama", llamacpp: "llama.cpp (GGUF)", hf: "🤗 transformers",
  };
  list.innerHTML = "";
  order.forEach((key) => {
    const info = engines[key];
    if (!info) return;
    const li = document.createElement("li");
    li.className = "engine" + (info.available ? " ready" : "");
    const detail = [];
    if (key === "brain") detail.push(`arch: ${info.arch || "mlp"}`);
    if (info.model) detail.push(`model: ${info.model}`);
    if (info.package_version) detail.push(`v${info.package_version}`);
    if (info.torch_version) detail.push(`torch ${info.torch_version}`);
    if (info.model_path && info.available) detail.push(info.model_path);
    if (info.answers) detail.push(`${info.answers} answers`);
    if (info.reason) detail.push(info.reason);
    li.innerHTML =
      `<div class="engine-head"><b>${labels[key] || key}</b>${engineBadge(info)}</div>` +
      (detail.length ? `<div class="engine-detail">${escapeHtml(detail.join(" · "))}</div>` : "") +
      (info.install && !info.available
        ? `<code class="engine-install">${escapeHtml(info.install)}</code>` : "");
    list.appendChild(li);
  });
}

async function refreshEngines(force = false) {
  let data;
  try {
    data = await (await fetch("/api/engines")).json();
  } catch (e) {
    return;
  }
  renderEngines(data.engines || {});
  const pill = $("md-engine-pill");
  if (pill) pill.textContent = data.selected || "auto";
}

function sliderLabels() {
  const pairs = [["gen-tokens", "gen-tokens-v", (v) => v],
                 ["gen-temp", "gen-temp-v", (v) => (v / 100).toFixed(2)],
                 ["gen-topk", "gen-topk-v", (v) => v],
                 ["gen-topp", "gen-topp-v", (v) => (v / 100).toFixed(2)],
                 ["gen-pen", "gen-pen-v", (v) => (v / 100).toFixed(2)]];
  pairs.forEach(([input, out, fmt]) => {
    const el = $(input), span = $(out);
    if (!el || !span) return;
    const sync = () => { span.textContent = fmt(Number(el.value)); };
    el.addEventListener("input", sync);
    sync();
  });
}

async function runGenerate() {
  const out = $("gen-out");
  const btn = $("gen-btn");
  if (!out) return;
  btn.disabled = true;
  out.classList.remove("hidden");
  out.innerHTML = '<span class="muted">sampling…</span>';
  const body = {
    prompt: $("gen-prompt").value,
    tokens: Number($("gen-tokens").value),
    temperature: Number($("gen-temp").value) / 100,
    top_k: Number($("gen-topk").value),
    top_p: Number($("gen-topp").value) / 100,
    repetition_penalty: Number($("gen-pen").value) / 100,
    engine: $("gen-engine").value,
  };
  try {
    const r = await fetch("/api/generate", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await r.json();
    if (!data.ok) {
      out.innerHTML = `<span class="muted">${escapeHtml(data.error || "nothing came back")}</span>`;
    } else {
      out.innerHTML =
        `<div class="gen-text">${escapeHtml(data.text)}</div>` +
        `<div class="gen-meta">${data.engine} · ${data.arch || "brain"} · ${data.ms} ms</div>`;
    }
  } catch (e) {
    out.innerHTML = '<span class="muted">generation failed</span>';
  }
  btn.disabled = false;
}

async function runNextTokens() {
  const q = $("next-q").value.trim();
  const box = $("next-bars");
  if (!box) return;
  if (!q) { box.innerHTML = ""; return; }
  try {
    const data = await (await fetch(`/api/model/topnext?q=${encodeURIComponent(q)}`)).json();
    if (!data.ok) { box.innerHTML = `<div class="muted">${escapeHtml(data.error)}</div>`; return; }
    const top = data.predictions || [];
    const max = Math.max(...top.map((p) => p.probability), 1e-9);
    box.innerHTML = top.map((p) =>
      `<div class="next-row"><span class="next-token">${escapeHtml(p.token)}</span>` +
      `<span class="next-track"><i style="width:${Math.max(2, (p.probability / max) * 100).toFixed(1)}%"></i></span>` +
      `<span class="next-p">${(p.probability * 100).toFixed(1)}%</span></div>`).join("");
  } catch (e) { /* ignore */ }
}

async function refreshModelTab() {
  await Promise.all([refreshModel(), refreshEngines()]);
}

const PREFS_KEY = "mygpt.prefs";
const prefs = {
  density: "comfortable", contrast: "normal", motion: "full",
  sidebar: "open", sound: "off", notify: "off", pins: [],
};

function loadPrefs() {
  try {
    const saved = JSON.parse(localStorage.getItem(PREFS_KEY) || "{}");
    Object.assign(prefs, saved);
    if (!Array.isArray(prefs.pins)) prefs.pins = [];
  } catch (e) { /* ignore */ }
}

function savePrefs() {
  try { localStorage.setItem(PREFS_KEY, JSON.stringify(prefs)); } catch (e) { /* ignore */ }
}

function applyPrefs() {
  document.documentElement.dataset.density = prefs.density;
  document.documentElement.dataset.contrast = prefs.contrast;
  document.documentElement.dataset.motion = prefs.motion;
  document.body.classList.toggle("sidebar-collapsed", prefs.sidebar === "closed");
  $("density-btn").classList.toggle("on", prefs.density === "compact");
  $("contrast-btn").classList.toggle("on", prefs.contrast === "high");
  $("motion-btn").classList.toggle("on", prefs.motion === "reduced");
  $("sidebar-btn").classList.toggle("on", prefs.sidebar === "closed");
  $("sound-btn").classList.toggle("on", prefs.sound === "on");
  $("notify-btn").classList.toggle("on", prefs.notify === "on");
  renderPins();
}

/* ---- audible chime (WebAudio, no asset files) ---- */
function chime() {
  try {
    const Ctx = window.AudioContext || window.webkitAudioContext;
    if (!Ctx) return;
    const ctx = new Ctx();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = "sine";
    osc.frequency.value = 880;
    gain.gain.setValueAtTime(0.0001, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.06, ctx.currentTime + 0.02);
    gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + 0.25);
    osc.connect(gain).connect(ctx.destination);
    osc.start();
    osc.stop(ctx.currentTime + 0.26);
    setTimeout(() => ctx.close(), 500);
  } catch (e) { /* audio unavailable */ }
}

/* ---- desktop notification + title badge when the tab is hidden ---- */
let _titleTimer = null;

function flashTitle(count) {
  if (!document.hidden) return;
  const base = document.title.replace(/^\(\d+\)\s*/, "");
  document.title = `(${count}) ${base}`;
  clearInterval(_titleTimer);
  let on = false;
  _titleTimer = setInterval(() => {
    on = !on;
    document.title = on ? `🔔 ${base}` : `(${count}) ${base}`;
    if (!document.hidden) {
      clearInterval(_titleTimer);
      document.title = base;
    }
  }, 900);
}

function maybeNotify(text) {
  if (prefs.notify !== "on" || !document.hidden) return;
  if (!("Notification" in window)) return;
  if (Notification.permission === "granted") {
    try { new Notification("MyGPT", { body: text.slice(0, 120) }); } catch (e) { /* ignore */ }
  } else if (Notification.permission !== "denied") {
    Notification.requestPermission();
  }
}

/* ---- pinned messages strip ---- */
function renderPins() {
  const bar = $("pins-bar");
  if (!bar) return;
  bar.innerHTML = "";
  bar.classList.toggle("hidden", !prefs.pins.length);
  prefs.pins.forEach((pin, i) => {
    const chip = document.createElement("button");
    chip.type = "button";
    chip.className = "pin-chip";
    chip.title = "Click to copy · right-click to unpin";
    chip.textContent = "📌 " + pin.slice(0, 34) + (pin.length > 34 ? "…" : "");
    chip.onclick = async () => {
      try { await navigator.clipboard.writeText(pin); toast("Pinned text copied ⧉"); }
      catch (e) { toast("⚠️ clipboard unavailable"); }
    };
    chip.oncontextmenu = (e) => {
      e.preventDefault();
      prefs.pins.splice(i, 1);
      savePrefs();
      renderPins();
      toast("Unpinned");
    };
    bar.appendChild(chip);
  });
}

function pinText(text) {
  const clean = text.trim().slice(0, 200);
  if (!clean) return;
  if (prefs.pins.includes(clean)) return toast("Already pinned");
  if (prefs.pins.length >= 8) prefs.pins.shift();
  prefs.pins.push(clean);
  savePrefs();
  renderPins();
  toast("📌 Pinned");
}

/* ---- offline queue: messages typed while disconnected ---- */
const QUEUE_KEY = "mygpt.queue";

function queueMessage(text) {
  try {
    const q = JSON.parse(localStorage.getItem(QUEUE_KEY) || "[]");
    q.push(text);
    localStorage.setItem(QUEUE_KEY, JSON.stringify(q.slice(-20)));
  } catch (e) { /* ignore */ }
}

async function flushQueue() {
  let q = [];
  try { q = JSON.parse(localStorage.getItem(QUEUE_KEY) || "[]"); } catch (e) { return; }
  if (!q.length) return;
  localStorage.setItem(QUEUE_KEY, "[]");
  toast(`📤 sending ${q.length} queued message(s)`);
  for (const text of q) {
    $("input").value = text;
    await send();
  }
}

window.addEventListener("online", () => {
  updateOnlineStatus();
  toast("🌐 back online");
  flushQueue();
});
window.addEventListener("offline", () => {
  updateOnlineStatus();
  toast("📴 offline — messages will queue");
});

/* ---- idle detection: pause polling after 5 quiet minutes ---- */
let _lastActivity = Date.now();
let _idle = false;
["pointerdown", "keydown", "wheel"].forEach((ev) =>
  window.addEventListener(ev, () => {
    _lastActivity = Date.now();
    if (_idle) { _idle = false; toast("👋 welcome back"); }
  }, { passive: true }));
setInterval(() => {
  _idle = Date.now() - _lastActivity > 5 * 60 * 1000;
}, 30000);

/* ---- actions bar: first message, copy all, edit last ---- */
$("first-btn").addEventListener("click", () => {
  const first = chatEl.querySelector(".msg");
  if (!first) return toast("Nothing here yet.");
  first.scrollIntoView({ behavior: "smooth", block: "start" });
  first.classList.add("flash");
  setTimeout(() => first.classList.remove("flash"), 900);
});

$("copy-all-btn").addEventListener("click", async () => {
  const lines = [];
  chatEl.querySelectorAll(".msg").forEach((m) => {
    const who = m.classList.contains("user") ? "You" : "MyGPT";
    const bubble = m.querySelector(".bubble");
    if (bubble && bubble.innerText.trim()) lines.push(`${who}: ${bubble.innerText.trim()}`);
  });
  if (!lines.length) return toast("Nothing to copy yet.");
  const text = `MyGPT transcript — ${new Date().toLocaleString()}\n\n` + lines.join("\n\n");
  try {
    await navigator.clipboard.writeText(text);
    toast(`⧉ copied ${lines.length} message(s)`);
  } catch (e) { toast("⚠️ clipboard unavailable"); }
});

$("edit-last-btn").addEventListener("click", () => {
  if (!lastUserText) return toast("Nothing to edit yet.");
  $("input").value = lastUserText;
  autoGrow();
  updateCharCount();
  $("input").focus();
  toast("✏️ last message loaded");
});

/* ---- header toggles ---- */
$("density-btn").addEventListener("click", () => {
  prefs.density = prefs.density === "compact" ? "comfortable" : "compact";
  savePrefs();
  applyPrefs();
  toast(prefs.density === "compact" ? "📐 compact" : "📐 comfortable");
});

$("contrast-btn").addEventListener("click", () => {
  prefs.contrast = prefs.contrast === "high" ? "normal" : "high";
  savePrefs();
  applyPrefs();
  toast(prefs.contrast === "high" ? "◐ high contrast" : "◐ normal contrast");
});

$("motion-btn").addEventListener("click", () => {
  prefs.motion = prefs.motion === "reduced" ? "full" : "reduced";
  savePrefs();
  applyPrefs();
  toast(prefs.motion === "reduced" ? "🎞 animations reduced" : "🎞 animations on");
});

$("sidebar-btn").addEventListener("click", toggleSidebar);

function toggleSidebar() {
  prefs.sidebar = prefs.sidebar === "closed" ? "open" : "closed";
  savePrefs();
  applyPrefs();
}

$("sound-btn").addEventListener("click", () => {
  prefs.sound = prefs.sound === "on" ? "off" : "on";
  savePrefs();
  applyPrefs();
  if (prefs.sound === "on") { chime(); toast("🔔 chime on"); }
  else toast("🔔 chime off");
});

$("notify-btn").addEventListener("click", async () => {
  prefs.notify = prefs.notify === "on" ? "off" : "on";
  savePrefs();
  applyPrefs();
  if (prefs.notify === "on" && "Notification" in window &&
      Notification.permission !== "granted") {
    try { await Notification.requestPermission(); } catch (e) { /* ignore */ }
  }
  toast(prefs.notify === "on" ? "🖥 notifications on" : "🖥 notifications off");
});

$("share-btn").addEventListener("click", async () => {
  const lines = [];
  chatEl.querySelectorAll(".msg").forEach((m) => {
    const bubble = m.querySelector(".bubble");
    if (bubble && bubble.innerText.trim()) {
      lines.push((m.classList.contains("user") ? "You: " : "MyGPT: ") + bubble.innerText.trim());
    }
  });
  const text = lines.join("\n\n") || "MyGPT — self-training chatbot by codero-sus";
  if (navigator.share) {
    try { await navigator.share({ title: "MyGPT conversation", text }); return; }
    catch (e) { /* fall through to clipboard */ }
  }
  try {
    await navigator.clipboard.writeText(text);
    toast("🔗 conversation copied — paste it anywhere");
  } catch (e) { toast("⚠️ sharing unavailable"); }
});

$("print-btn").addEventListener("click", () => window.print());

$("help-btn").addEventListener("click", () => $("help-modal").showModal());

document.addEventListener("keydown", (e) => {
  if (e.key === "?" && !["INPUT", "TEXTAREA"].includes(document.activeElement.tagName)) {
    e.preventDefault();
    $("help-modal").showModal();
  }
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "b") {
    e.preventDefault();
    toggleSidebar();
  }
});

/* About dialog gets live version info */
(async function fillAbout() {
  try {
    const v = await api("/api/version");
    $("about-version").textContent =
      `version ${v.version} · ${(await api("/api/endpoints")).count} endpoints`;
  } catch (e) { /* offline is fine */ }
})();

/* ---- message action bar (copy / pin / quote) ---- */
function addMessageActions(wrap, text) {
  const row = document.createElement("div");
  row.className = "msg-actions";
  const copy = document.createElement("button");
  copy.type = "button";
  copy.textContent = "⧉";
  copy.title = "Copy this message";
  copy.onclick = async () => {
    try { await navigator.clipboard.writeText(text); toast("Copied ⧉"); }
    catch (e) { toast("⚠️ clipboard unavailable"); }
  };
  const pin = document.createElement("button");
  pin.type = "button";
  pin.textContent = "📌";
  pin.title = "Pin this message";
  pin.onclick = () => pinText(text);
  const quote = document.createElement("button");
  quote.type = "button";
  quote.textContent = "❝";
  quote.title = "Quote in the composer";
  quote.onclick = () => {
    const snippet = text.split("\n")[0].slice(0, 80);
    $("input").value = `> ${snippet}\n` + $("input").value;
    autoGrow();
    updateCharCount();
    $("input").focus();
  };
  row.append(copy, pin, quote);
  wrap.appendChild(row);
  return row;
}

/* ---- connection quality (ping latency in the status text) ---- */
async function measurePing() {
  const t0 = Date.now();
  try {
    await fetch("/api/ping", { cache: "no-store" });
    return Date.now() - t0;
  } catch (e) {
    return null;
  }
}

setInterval(async () => {
  if (_idle || document.hidden) return;
  const ms = await measurePing();
  const el = $("status-text");
  if (!el) return;
  const quality = ms == null ? "offline" :
    ms < 60 ? "fast" : ms < 250 ? "steady" : "slow";
  el.dataset.ping = ms == null ? "" : String(ms);
  el.title = ms == null ? "no connection" : `round-trip ${ms} ms (${quality})`;
}, 45000);

/* ---------------- boot ---------------- */

const GREETING =
  "Hi! I'm MyGPT — a tiny chatbot that trains itself on our conversation.\n" +
  "Ask me things (hard questions get a System-2 chain of thought 💭), rate my " +
  "answers with 👍/👎, teach me facts in the Learn tab — or ask for code " +
  "(e.g. “write code for the first 15 primes”) and I'll answer with a code " +
  "block right here in chat.\n\n" +
  "Made with ❤️ by codero-sus, built on the self-learning ideas from " +
  "codero-sus/agi — GitHub: github.com/codero-sus · " +
  "Website: the-codero.web.app";

function initModelTab() {
  const pairs = [["gen-btn", runGenerate], ["next-btn", runNextTokens],
                 ["engine-refresh", () => refreshEngines(true)]];
  pairs.forEach(([id, fn]) => { const el = $(id); if (el) el.addEventListener("click", fn); });
  const q = $("next-q");
  if (q) q.addEventListener("keydown", (e) => {
    if (e.key === "Enter") { e.preventDefault(); runNextTokens(); }
  });
  sliderLabels();
}

function addChips() {
  const chips = document.createElement("div");
  chips.className = "chips";
  ["who are you?", "23*47", "write code for the first 15 primes",
   "checkpoint the model"].forEach((label) => {
    const b = document.createElement("button");
    b.type = "button";
    b.textContent = label;
    b.onclick = () => {
      $("input").value = label;
      send();
    };
    chips.appendChild(b);
  });
  chatEl.appendChild(chips);
  const strip = () => { chips.remove(); $("input").removeEventListener("keydown", strip); };
  $("input").addEventListener("keydown", strip, { once: true });
}

/* Restore the recent conversation after a page reload; fresh sessions get
   the greeting + suggestion chips instead. */
async function restoreHistory() {
  try {
    const d = await api("/api/history?limit=30");
    const eps = d.episodes || [];
    if (!eps.length) return false;
    for (const e of eps) {
      const role = e.role === "user" ? "user" : "bot";
      addMessage(role, e.content);
    }
    scrollDown(true);
    return true;
  } catch (err) {
    return false;
  }
}

(async function boot() {
  loadPrefs();
  initTheme();
  initZoom();
  applyPrefs();
  updateOnlineStatus();
  const hadHistory = await restoreHistory();
  if (!hadHistory) {
    addMessage("bot", GREETING);
    addChips();
  }
  restoreDraft();
  updateCharCount();
  initDragDrop();
  initModelTab();
  refreshModel();
  $("theme-btn").addEventListener("click", toggleTheme);
  $("font-inc").addEventListener("click", () => bumpZoom(1));
  $("font-dec").addEventListener("click", () => bumpZoom(-1));
  refreshSidebars();
  refreshBackends();
  measurePing().then((ms) => {
    if (ms != null) $("status-text").title = `round-trip ${ms} ms`;
  });
  if (localStorage.getItem("mygpt.queue")) flushQueue();
  $("input").focus();
})();
