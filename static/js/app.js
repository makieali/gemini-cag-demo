"use strict";

const $ = (sel) => document.querySelector(sel);

const state = {
  staged: [],      // File objects waiting to be uploaded
  kbActive: false,
  ttlTimer: null,
};

/* ---------- helpers ---------- */

function fmtMoney(n) {
  if (n >= 0.01) return "$" + n.toFixed(4);
  return "$" + n.toFixed(6);
}

function fmtInt(n) {
  return (n || 0).toLocaleString();
}

async function api(path, opts = {}) {
  const res = await fetch(path, opts);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || `Request failed (${res.status})`);
  return data;
}

function addMessage(html, kind = "assistant") {
  const wrap = document.createElement("div");
  wrap.className = `msg ${kind}`;
  wrap.innerHTML = html;
  $("#messages").appendChild(wrap);
  $("#messages").scrollTop = $("#messages").scrollHeight;
  return wrap;
}

function metricsRow(r) {
  const c = r.cost, u = r.usage;
  return `<div class="metrics">
    <span title="Cached prompt tokens reused from the context cache">🧠 ${fmtInt(u.cached_tokens)} cached</span>
    <span title="Fresh prompt tokens billed at full rate">✏️ ${fmtInt(u.fresh_prompt_tokens)} fresh</span>
    <span title="Output tokens">📤 ${fmtInt(u.output_tokens)} out</span>
    <span title="End-to-end latency">⏱ ${r.latency_ms} ms</span>
    <span class="cost" title="Cost of this call">${fmtMoney(c.total_cost)}</span>
    <span class="saved" title="Saved versus re-sending the documents">▼ ${c.savings_pct}%</span>
  </div>`;
}

/* ---------- file staging ---------- */

const dropzone = $("#dropzone");
const fileInput = $("#file-input");

dropzone.addEventListener("dragover", (e) => { e.preventDefault(); dropzone.classList.add("hover"); });
dropzone.addEventListener("dragleave", () => dropzone.classList.remove("hover"));
dropzone.addEventListener("drop", (e) => {
  e.preventDefault();
  dropzone.classList.remove("hover");
  stageFiles(e.dataTransfer.files);
});
fileInput.addEventListener("change", () => stageFiles(fileInput.files));

function stageFiles(fileList) {
  for (const f of fileList) state.staged.push(f);
  renderStaged();
}

function renderStaged() {
  const ul = $("#staged-files");
  ul.innerHTML = "";
  state.staged.forEach((f, i) => {
    const li = document.createElement("li");
    li.innerHTML = `<span>${f.name}</span><button data-i="${i}" aria-label="remove">✕</button>`;
    ul.appendChild(li);
  });
  ul.querySelectorAll("button").forEach((b) =>
    b.addEventListener("click", () => {
      state.staged.splice(Number(b.dataset.i), 1);
      renderStaged();
    })
  );
  $("#build-btn").disabled = state.staged.length === 0;
}

/* ---------- build cache ---------- */

$("#build-btn").addEventListener("click", async () => {
  if (!state.staged.length) return;
  const btn = $("#build-btn");
  btn.disabled = true;
  btn.textContent = "Building cache…";
  const fd = new FormData();
  state.staged.forEach((f) => fd.append("files[]", f));
  try {
    const data = await api("/api/kb", { method: "POST", body: fd });
    state.staged = [];
    renderStaged();
    activateKb(data);
    addMessage(`<p>✅ ${data.message} <strong>${fmtInt(data.cached_token_count)}</strong> tokens cached.
      Ask anything about: ${data.files.map((f) => `<code>${f}</code>`).join(", ")}.</p>`, "system");
  } catch (e) {
    addMessage(`<p class="err">⚠️ ${e.message}</p>`, "system");
  } finally {
    btn.textContent = "Build context cache";
    btn.disabled = state.staged.length === 0;
  }
});

function activateKb(data) {
  state.kbActive = true;
  $("#kb-status").classList.remove("hidden");
  $("#kb-tokens").textContent = `${fmtInt(data.cached_token_count)} tokens cached`;
  $("#question").disabled = false;
  $("#send-btn").disabled = false;
  startTtl(data.expires_at);
  refreshStats();
}

/* ---------- TTL countdown ---------- */

function startTtl(expiresAt) {
  clearInterval(state.ttlTimer);
  if (!expiresAt) { $("#kb-ttl").textContent = ""; return; }
  const tick = () => {
    const left = Math.max(0, Math.floor(expiresAt - Date.now() / 1000));
    const m = String(Math.floor(left / 60)).padStart(2, "0");
    const s = String(left % 60).padStart(2, "0");
    $("#kb-ttl").textContent = `${m}:${s}`;
    $("#kb-ttl").classList.toggle("expiring", left < 60);
    if (left <= 0) { clearInterval(state.ttlTimer); $("#kb-ttl").textContent = "expired"; }
  };
  tick();
  state.ttlTimer = setInterval(tick, 1000);
}

$("#extend-btn").addEventListener("click", async () => {
  try {
    await api("/api/kb/extend", { method: "POST" });
    const kb = await api("/api/kb");
    startTtl(kb.expires_at);
  } catch (e) { addMessage(`<p class="err">⚠️ ${e.message}</p>`, "system"); }
});

$("#clear-btn").addEventListener("click", async () => {
  await api("/api/kb", { method: "DELETE" });
  state.kbActive = false;
  clearInterval(state.ttlTimer);
  $("#kb-status").classList.add("hidden");
  $("#question").disabled = true;
  $("#send-btn").disabled = true;
  addMessage(`<p>🗑️ Cache deleted.</p>`, "system");
});

/* ---------- ask / compare ---------- */

$("#composer").addEventListener("submit", async (e) => {
  e.preventDefault();
  const q = $("#question").value.trim();
  if (!q || !state.kbActive) return;
  $("#question").value = "";
  addMessage(`<p>${q}</p>`, "user");
  const thinking = addMessage(`<p class="thinking">Thinking…</p>`, "assistant");

  try {
    if ($("#compare-toggle").checked) {
      const data = await api("/api/compare", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: q }),
      });
      thinking.remove();
      renderComparison(data);
    } else {
      const r = await api("/api/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: q }),
      });
      thinking.innerHTML = `${marked.parse(r.answer)}${metricsRow(r)}`;
      applyStats(r.session_stats);
    }
  } catch (err) {
    thinking.innerHTML = `<p class="err">⚠️ ${err.message}</p>`;
  }
});

function renderComparison(data) {
  const cag = data.cag, full = data.full_context;
  const speedup = full.latency_ms / Math.max(cag.latency_ms, 1);
  const costCut = full.cost.total_cost > 0
    ? (1 - cag.cost.total_cost / full.cost.total_cost) * 100 : 0;
  addMessage(`
    <div class="compare">
      <div class="compare-head">
        <span class="pill win">CAG ${costCut.toFixed(0)}% cheaper · ${speedup.toFixed(1)}× faster</span>
      </div>
      <div class="compare-cols">
        <div class="col">
          <h4>⚡ CAG (cached)</h4>
          ${marked.parse(cag.answer)}
          ${metricsRow(cag)}
        </div>
        <div class="col">
          <h4>📦 Full-context (no cache)</h4>
          ${marked.parse(full.answer)}
          ${metricsRow(full)}
        </div>
      </div>
    </div>`);
  refreshStats();
}

/* ---------- stats ---------- */

function applyStats(s) {
  if (!s) return;
  $("#savings-amount").textContent = fmtMoney(s.total_savings);
  $("#savings-pct").textContent = `${s.savings_pct}% saved vs no-cache`;
  $("#stat-queries").textContent = fmtInt(s.query_count);
  $("#stat-cached").textContent = fmtInt(s.total_cached_tokens);
  $("#stat-spent").textContent = fmtMoney(s.total_cost);
  $("#stat-nocache").textContent = fmtMoney(s.total_cost_without_cache);
}

async function refreshStats() {
  try { applyStats(await api("/api/stats")); } catch { /* ignore */ }
}

/* ---------- boot: restore any active KB ---------- */

(async function boot() {
  try {
    const kb = await api("/api/kb");
    if (kb.active) {
      activateKb({ cached_token_count: kb.cached_token_count, expires_at: kb.expires_at });
    }
  } catch { /* no session yet */ }
})();
