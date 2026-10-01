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

function toast(text) {
  const t = $("toast");
  t.textContent = text;
  t.classList.add("show");
  clearTimeout(t._timer);
  t._timer = setTimeout(() => t.classList.remove("show"), 2600);
}

function scrollDown() {
  chatEl.scrollTop = chatEl.scrollHeight;
}

function fmtTime(ts) {
  const d = new Date(ts * 1000);
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

/* ---------------- chat rendering ---------------- */

function addMessage(role, text) {
  const msg = document.createElement("div");
  msg.className = `msg ${role}`;
  const avatar = document.createElement("div");
  avatar.className = "avatar";
  avatar.textContent = role === "bot" ? "🤖" : "🧑";
  const wrap = document.createElement("div");
  wrap.className = "bubble-wrap";
  const bubble = document.createElement("div");
  bubble.className = "bubble";
  bubble.textContent = text;
  wrap.appendChild(bubble);
  msg.append(avatar, wrap);
  chatEl.appendChild(msg);
  scrollDown();
  return wrap;
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

function addBotReply(data) {
  const wrap = addMessage("bot", data.reply);
  addChain(data.chain, wrap);

  const meta = document.createElement("div");
  meta.className = "meta-row";
  const tag = document.createElement("span");
  tag.className = "mode-tag" + (data.mode === "skill" ? " skill" : "");
  tag.textContent = data.mode === "skill" && data.skill
    ? `skill: ${data.skill}` : (MODE_LABELS[data.mode] || data.mode);
  meta.appendChild(tag);

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

async function send() {
  const input = $("input");
  const text = input.value.trim();
  if (!text || busy) return;
  busy = true;
  lastUserText = text;
  input.value = "";
  $("send").disabled = true;

  addMessage("user", text);
  const typingWrap = addMessage("bot", "");
  typingWrap.querySelector(".bubble").innerHTML =
    '<span class="typing"><span></span><span></span><span></span></span>';

  const t0 = Date.now();
  const data = await api("/api/chat", { message: text });
  const wait = 420 - (Date.now() - t0);
  if (wait > 0) await new Promise((r) => setTimeout(r, wait));

  typingWrap.closest(".msg").remove();
  if (data.ok) addBotReply(data);
  else addMessage("bot", "⚠️ " + (data.error || "something went wrong"));

  busy = false;
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
  if (name === "growth") refreshStats();
  if (name === "mind") refreshMind();
}

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

async function refreshStats() {
  const data = await api("/api/stats");
  $("st-pairs").textContent = data.pairs;
  $("st-msgs").textContent = data.counters.messages;
  $("st-up").textContent = data.counters.up;
  $("st-corr").textContent = data.counters.corrections;
  $("st-vocab").textContent = data.vocab_size;
  $("st-rounds").textContent = data.counters.train_rounds;

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

function refreshSidebars() {
  refreshMemory();
  if (!$("panel-growth").classList.contains("hidden")) refreshStats();
  if (!$("panel-mind").classList.contains("hidden")) refreshMind();
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

async function refreshMind() {
  const data = await api("/api/stats");
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

/* ---------------- boot ---------------- */

addMessage("bot",
  "Hi! I'm MyGPT — a tiny chatbot that trains itself on our conversation.\n" +
  "Ask me things (hard questions get a full System-2 chain of thought 💭), " +
  "rate my answers with 👍/👎, teach me facts in the Learn tab, and watch the " +
  "self-learning loop in the Mind tab.");
refreshSidebars();
$("input").focus();
