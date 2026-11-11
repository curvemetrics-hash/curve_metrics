
window.showConsole = function() {
  window._viewingConsole = true;
  const pGated = document.getElementById('p-gated');
  const pEnv = document.getElementById('p-env');
  if (pGated) pGated.style.display = 'none';
  if (pEnv) pEnv.style.display = '';
  document.body.classList.remove('is-guest');
  page('env');
  lastList = '';
  load();
  window.scrollTo(0, 0);
};

window.showLanding = function() {
  window._viewingConsole = false;
  const pGated = document.getElementById('p-gated');
  const pEnv = document.getElementById('p-env');
  const pRoll = document.getElementById('p-roll');
  const pAct = document.getElementById('p-act');
  const pHow = document.getElementById('p-how');
  if (pGated) pGated.style.display = 'block';
  if (pEnv) pEnv.style.display = 'none';
  if (pRoll) pRoll.style.display = 'none';
  if (pAct) pAct.style.display = 'none';
  if (pHow) pHow.style.display = 'none';
  window.scrollTo(0, 0);
};
function getInitials(name, id) {
  const full = (name || id || "User").trim();
  const parts = full.split(/[\s_.-]+/).filter(Boolean);
  if (parts.length >= 2) {
    return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
  }
  return full.slice(0, 2).toUpperCase();
}

const $ = s => document.querySelector(s), $$ = s => [...document.querySelectorAll(s)];
const esc = t => String(t ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const ic = n => `<svg class="i"><use href="#i-${n}"/></svg>`;

const STAGES = [
  ["format", "Terraform formatting"],
  ["validate", "Validate modules"],
  ["tests", "Module unit tests"],
  ["init", "Initialise remote state"],
  ["plan", "Plan the change"],
  ["policy", "Policy gate"],
  ["approve", "Approval"],
  ["apply", "Apply"],
  ["verify", "Verify cluster and AWS"],
  ["metric", "Record the metric"]
];

const GRADE = { "healthy": "ok", "needs attention": "warn", "at risk": "bad", "non-compliant": "bad" };
const SEV = ["high", "medium", "low"];

const fmt = s => s == null ? "-" : (s >= 60 ? Math.floor(s / 60) + "m " + (s % 60) + "s" : s + "s");

const ago = t => {
  if (!t) return "";
  const d = Math.floor(Date.now() / 1000 - t);
  return d < 60 ? "just now" : d < 3600 ? Math.floor(d / 60) + " min ago" : d < 86400 ? Math.floor(d / 3600) + " h ago" : Math.floor(d / 86400) + " d ago";
};

let me = { id: "", role: "viewer" };
const can = r => ["viewer", "operator", "admin"].indexOf(me.role) >= ["viewer", "operator", "admin"].indexOf(r);

const API_BASE = (window.location.hostname.endsWith(".pages.dev") || window.location.hostname.includes("cloudflare"))
  ? "https://curve-metrics-platform.onrender.com"
  : "";

async function api(path, method = "GET", body) {
  const token = localStorage.getItem("platform_token");
  const headers = {
    "X-Requested-With": "console",
    ...(token ? { "Authorization": "Bearer " + token } : {}),
    ...(body ? { "Content-Type": "application/json" } : {})
  };
  const r = await fetch(API_BASE + path, {
    method,
    credentials: "include",
    headers,
    body: body ? JSON.stringify(body) : undefined
  });
  let j = {};
  try { j = await r.json(); } catch (e) {}
  if (r.status === 401 && me.id && me.id !== "guest") { toast("Your session expired. Reload the page to sign in again."); }
  return { ok: r.ok, status: r.status, data: j };
}

async function waitJob(id, seconds = 180) {
  const end = Date.now() + seconds * 1000;
  while (Date.now() < end) {
    const r = await api("/jobs/" + id);
    if (r.ok && (r.data.status === "done" || r.data.status === "failed")) return r.data;
    await new Promise(x => setTimeout(x, 1500));
  }
  return null;
}

function applyRole() {
  const newBtn = $("#new"); if (newBtn) { newBtn.hidden = false; }
  const navAct = $("#nav-act"); if (navAct) navAct.hidden = !can("admin");
  const rctl = $("#rctl"); if (rctl) rctl.hidden = !can("operator");
  const rstart = $("#rstart"); if (rstart) rstart.hidden = !can("admin");
  const initial = (me.name || me.id || 'L').charAt(0).toUpperCase();
  const whoEl = document.getElementById('who');
  if (whoEl) {
    whoEl.style.cursor = 'pointer';
    whoEl.title = 'Click to sign in, sign up, or switch accounts';
    whoEl.onclick = () => {
      const d = document.getElementById('auth-dlg');
      if (d) d.showModal();
    };
    if (me.id) {
      whoEl.innerHTML = '<div class="user-avatar">' + esc(initial) + '</div>' +
        '<div class="user-details">' +
          '<div class="user-header-line">' +
            '<span class="user-name">' + esc(me.name || me.id) + '</span>' +
            '<span class="pill ' + (me.role === 'admin' ? 'acc' : '') + ' user-badge-pill">' + esc(me.role) + '</span>' +
          '</div>' +
          '<div class="user-meta-line">' +
            '<span class="mode-bullet"></span>' +
            '<span class="user-mode">' + (me.id.includes('@') ? esc(me.id) : (me.mode === 'aws' ? 'AWS' : 'local mode')) + '</span>' +
          '</div>' +
        '</div>';
    } else {
      whoEl.innerHTML = '<button class="btn sm pri" onclick="document.getElementById(\'auth-dlg\').showModal()">Sign In</button>';
    }
  }

  const isGuest = !me.id || me.id === 'guest' || me.id === 'anonymous' || me.role === 'none';
  const topbarAccountBtn = document.getElementById('topbar-account-btn');
  const topbarSignInBtn = document.getElementById('topbar-signin-btn');

  const modalLogoutBtn = document.getElementById('auth-modal-logout');
  const pGated = document.getElementById('p-gated');
  const pEnv = document.getElementById('p-env');
  const pRoll = document.getElementById('p-roll');
  const pAct = document.getElementById('p-act');

  const titleEl = document.getElementById('topbar-page-name');
  const wantsConsole = window._viewingConsole || location.hash === '#console' || location.hash === '#env' || location.search.includes('console');
  if (isGuest && !wantsConsole) {
    document.body.classList.add('is-guest');
    if (topbarAccountBtn) topbarAccountBtn.style.display = 'none';
    if (topbarSignInBtn) {
      topbarSignInBtn.style.display = 'inline-flex';
      topbarSignInBtn.onclick = () => {
        const d = document.getElementById('auth-dlg');
        if (d) d.showModal();
      };
    }
    if (modalLogoutBtn) modalLogoutBtn.style.display = 'none';
    if (pGated) pGated.style.display = 'block';
    if (pEnv) pEnv.style.display = 'none';
    if (pRoll) pRoll.style.display = 'none';
    if (pAct) pAct.style.display = 'none';
    if (titleEl) titleEl.textContent = 'Platform Overview';
  } else {
    document.body.classList.remove('is-guest');
    if (topbarAccountBtn) topbarAccountBtn.style.display = 'flex';
    if (topbarSignInBtn) topbarSignInBtn.style.display = isGuest ? 'inline-flex' : 'none';
    if (modalLogoutBtn) modalLogoutBtn.style.display = isGuest ? 'none' : 'inline-flex';
    if (pGated) pGated.style.display = 'none';
    if (pEnv) pEnv.style.display = '';
    if (titleEl) titleEl.textContent = isGuest ? 'Environments (Visitor View)' : 'Environments';
  }

  // Hook landing page nav buttons
  const landingSignIn = document.getElementById('landing-nav-signin-btn');
  if (landingSignIn) {
    landingSignIn.onclick = () => {
      const d = document.getElementById('auth-dlg');
      if (d) d.showModal();
    };
  }
  const landingThemeBtn = document.getElementById('landing-theme-btn');
  if (landingThemeBtn) {
    landingThemeBtn.onclick = () => {
      const cur = document.documentElement.getAttribute('data-theme') || 'dark';
      const nxt = cur === 'dark' ? 'light' : 'dark';
      document.documentElement.setAttribute('data-theme', nxt);
      try { localStorage.setItem('theme', nxt); } catch (e) {}
    };
  }

  const gatedSignInBtn = document.getElementById('gated-signin-btn');
  if (gatedSignInBtn) {
    gatedSignInBtn.onclick = () => {
      window.showConsole();
    };
  }

  const topbarInitials = document.getElementById('topbar-user-initials');
  if (topbarInitials) {
    topbarInitials.textContent = isGuest ? '?' : getInitials(me.name, me.id);
  }
  const topbarUser = document.getElementById('topbar-user-name');
  if (topbarUser) {
    topbarUser.textContent = isGuest ? 'Sign In' : `${me.name || me.id} (${me.role})`;
  }
  const ddAvatar = document.getElementById('dd-avatar');
  if (ddAvatar) ddAvatar.textContent = isGuest ? '?' : getInitials(me.name, me.id);
  const ddName = document.getElementById('dd-user-name');
  if (ddName) ddName.textContent = isGuest ? 'Signed Out' : (me.name || me.id || 'User');
  const ddRole = document.getElementById('dd-user-role');
  if (ddRole) ddRole.textContent = isGuest ? 'Guest Session' : `${me.role || 'viewer'} · ${me.mode === 'aws' ? 'AWS' : 'local mode'}`;
}

let list = [], filter = "all", query = "", sel = null, tab = "findings", detail = null, lastList = "", lastDetail = "", opened = new Set(), busy = new Set();

function toast(m) {
  const t = $("#toast");
  t.textContent = m;
  t.classList.add("on");
  clearTimeout(toast.t);
  toast.t = setTimeout(() => t.classList.remove("on"), 2800);
}

function statusPill(s) {
  if (s.status === "ready") return `<span class="pill ok"><i class="dot"></i>Ready</span>`;
  if (s.status === "provisioning") return `<span class="pill warn"><i class="dot pulse"></i>Building</span>`;
  if (s.status === "rejected") return `<span class="pill bad"><i class="dot"></i>Rejected by policy</span>`;
  return `<span class="pill bad"><i class="dot"></i>${esc(s.status || "unknown")}</span>`;
}

function seg(s) {
  const failed = s.status === "rejected" || s.status === "failed", ready = s.status === "ready", cur = failed ? (s.failed_stage || s.stage || 0) : (s.stage || 0);
  return `<div class="seg" title="Pipeline stage ${cur || (ready ? 10 : 0)} of 10">` + STAGES.map(([name, desc], i) => {
    const k = i + 1;
    const c = ready || k < cur ? "d" : (k === cur ? (failed ? "f" : "c") : "");
    return `<i class="${c}" title="Stage ${k}: ${desc}"></i>`;
  }).join("") + `</div>`;
}

function gradePill(l) {
  return l && l.grade ? `<span class="pill ${GRADE[l.grade] || ''}"><i class="dot"></i>${esc(l.grade)}</span>` : `<span class="pill">not scanned</span>`;
}

function sevBadges(l) {
  const v = l && l.extended_summary && l.extended_summary.severity;
  if (!v || !(v.high + v.medium + v.low)) return "";
  return `<div class="sev">${v.high ? `<b class="h">${v.high} high</b>` : ""}${v.medium ? `<b class="m">${v.medium} med</b>` : ""}${v.low ? `<b class="lo">${v.low} low</b>` : ""}</div>`;
}

/* ---------- list ---------- */
function filtered() {
  return list.filter(s => {
    const q = query.trim().toLowerCase();
    if (q && ![s.name, s.team, s.environment, s.size].join(" ").toLowerCase().includes(q)) return false;
    if (filter === "attention") return s.latest && s.latest.grade && s.latest.grade !== "healthy";
    if (filter === "building") return s.status === "provisioning";
    if (filter === "failed") return s.status === "rejected" || s.status === "failed";
    return true;
  });
}

function renderStats() {
  const ready = list.filter(s => s.status === "ready").length;
  const healthy = list.filter(s => s.latest && s.latest.grade === "healthy").length;
  const high = list.reduce((a, s) => a + ((s.latest && s.latest.extended_summary && s.latest.extended_summary.severity.high) || 0), 0);
  const t = list.map(s => s.seconds_to_ready).filter(x => x != null);
  const avg = t.length ? Math.round(t.reduce((a, b) => a + b) / t.length) : null;
  const healthRate = list.length ? Math.round((healthy / list.length) * 100) + "%" : "100%";

  $("#stats").innerHTML = `
    <div class="stat">
      <div class="stat-top">
        <div class="stat-icon icon-env">${ic("cube")}</div>
        <span class="stat-tag">Total</span>
      </div>
      <div class="n">${list.length}</div>
      <div class="l">Environments</div>
      <div class="stat-sub">Managed blueprints</div>
    </div>
    <div class="stat">
      <div class="stat-top">
        <div class="stat-icon icon-ready">${ic("check-circle")}</div>
        <span class="stat-tag ${ready > 0 ? 'ok' : ''}">${ready > 0 ? 'Active' : 'Idle'}</span>
      </div>
      <div class="n">${ready}</div>
      <div class="l">Ready</div>
      <div class="stat-sub">${ready === list.length && list.length ? '100% operational' : 'Verified clusters'}</div>
    </div>
    <div class="stat">
      <div class="stat-top">
        <div class="stat-icon icon-health">${ic("shield")}</div>
        <span class="stat-tag ${healthy === list.length && list.length ? 'ok' : 'mut'}">${healthRate}</span>
      </div>
      <div class="n ${healthy === list.length && list.length ? 'ok' : ''}">${healthy}<span class="mut" style="font-size:15px;font-weight:500"> / ${list.length}</span></div>
      <div class="l">Healthy</div>
      <div class="stat-sub">Baseline controls</div>
    </div>
    <div class="stat">
      <div class="stat-top">
        <div class="stat-icon icon-sec ${high ? 'bad' : 'ok'}">${ic("alert-triangle")}</div>
        <span class="stat-tag ${high ? 'bad' : 'ok'}">${high ? 'Alert' : 'Clean'}</span>
      </div>
      <div class="n ${high ? 'bad' : 'ok'}">${high}</div>
      <div class="l">Open high findings</div>
      <div class="stat-sub">${high ? 'Requires review' : '0 critical issues'}</div>
    </div>
    <div class="stat">
      <div class="stat-top">
        <div class="stat-icon icon-time">${ic("clock")}</div>
        <span class="stat-tag">Pipeline</span>
      </div>
      <div class="n">${fmt(avg)}</div>
      <div class="l">Avg time to ready</div>
      <div class="stat-sub">Local execution</div>
    </div>`;
}

function renderChips() {
  const n = {
    all: list.length,
    attention: list.filter(s => s.latest && s.latest.grade && s.latest.grade !== "healthy").length,
    building: list.filter(s => s.status === "provisioning").length,
    failed: list.filter(s => s.status === "rejected" || s.status === "failed").length
  };
  $("#chips").innerHTML = [
    ["all", "All", n.all, ""],
    ["attention", "Needs attention", n.attention, n.attention ? "warn" : ""],
    ["building", "Building", n.building, n.building ? "acc" : ""],
    ["failed", "Failed", n.failed, n.failed ? "bad" : ""]
  ].map(([k, l, cnt, color]) => `
    <button class="chip ${filter === k ? 'on' : ''}" data-chip="${k}">
      <span>${l}</span>
      <span class="chip-count ${color}">${cnt}</span>
    </button>
  `).join("");
}

let selectedEnvNames = new Set();

function updateBatchBar() {
  const bar = $("#batch-bar");
  const countLabel = $("#batch-selected-count");
  if (!bar) return;
  const count = selectedEnvNames.size;
  if (count > 0 || (list && list.some(s => s.latest && !s.latest.compliant))) {
    bar.style.display = "flex";
    if (countLabel) countLabel.textContent = `${count} selected`;
  } else {
    bar.style.display = "none";
  }
}

function renderRows() {
  const rows = filtered();
  const badgeEl = $("#nav-badge-env");
  if (badgeEl) badgeEl.textContent = list.length;

  const selectAll = $("#select-all-env");
  if (selectAll) {
    selectAll.checked = rows.length > 0 && rows.every(s => selectedEnvNames.has(s.name));
  }
  updateBatchBar();

  if (!rows.length) {
    $("#rows").innerHTML = `<tr><td colspan="6">
      <div class="empty-state">
        <div class="empty-icon-wrap">
          <div class="empty-icon-halo"></div>
          <div class="empty-icon">${ic("cube")}</div>
        </div>
        <h3>${list.length ? "No matching environments found" : "No environments yet"}</h3>
        <p>${list.length ? "Try adjusting your search query or switching to another filter." : "Request your first self-service Kubernetes environment configured with automated compliance and policy verification."}</p>
        ${!list.length && can("operator") ? `
          <button class="btn pri empty-cta" id="empty-new-btn">${ic("plus")} Request environment</button>
          <div class="empty-suggestions">
            <span class="empty-sugg-title">Quick presets:</span>
            <button class="sugg-chip" data-quick-name="payments-dev" data-quick-team="payments" data-quick-env="dev" data-quick-size="small" data-quick-grp="payments-admins">dev · small</button>
            <button class="sugg-chip" data-quick-name="orders-staging" data-quick-team="orders" data-quick-env="test" data-quick-size="medium" data-quick-grp="orders-admins">test · medium</button>
            <button class="sugg-chip" data-quick-name="checkout-prod" data-quick-team="checkout" data-quick-env="prod" data-quick-size="large" data-quick-grp="checkout-admins">prod · large</button>
          </div>
        ` : ""}
      </div>
    </td></tr>`;
    return;
  }

  $("#rows").innerHTML = rows.map(s => {
    const l = s.latest && s.latest.total ? s.latest : null;
    const kindClass = s.environment === "prod" ? "prod" : (s.environment === "test" ? "test" : "dev");
    const isChecked = selectedEnvNames.has(s.name) ? "checked" : "";
    return `<tr class="row" data-open="${esc(s.name)}">
      <td style="text-align:center" onclick="event.stopPropagation()">
        <input type="checkbox" class="env-chk" data-select-name="${esc(s.name)}" ${isChecked}>
      </td>
      <td>
        <div class="nm"><span class="mono">${esc(s.name)}</span></div>
        <div class="env-tags">
          <span class="tag-badge ${kindClass}">${esc(s.environment)}</span>
          <span class="tag-badge">${esc(s.size)}</span>
          <span class="sub" style="margin-left:4px">${esc(s.team || "")}</span>
        </div>
      </td>
      <td>
        ${statusPill(s)}
        ${seg(s)}
        <div class="m-only">${l ? `${gradePill(l)}${sevBadges(l)}` : ""}</div>
      </td>
      <td class="col-c">
        ${l ? `<div>${gradePill(l)} <span class="sub" style="font-weight:550;margin-left:4px">${l.passed}/${l.total} baseline</span></div>${sevBadges(l)}` : '<span class="sub">not scanned</span>'}
      </td>
      <td class="col-t">
        <div style="font-weight:600;font-variant-numeric:tabular-nums">${fmt(s.seconds_to_ready)}</div>
        <div class="sub">${esc(ago(s.requested_at))}</div>
      </td>
      <td style="text-align:right;white-space:nowrap" onclick="event.stopPropagation()">
        ${can("admin") && (l && (!l.compliant || l.grade === "needs attention" || l.grade === "at risk" || l.grade === "non-compliant") || s.status === "failed" || s.status === "rejected") ? `
          <button class="btn sm" data-fix="${esc(s.name)}" title="Re-apply blueprint and remediate compliance drift">
            ${ic("fix")}
            <span>Fix</span>
          </button>
        ` : ""}
        <button class="btn sm" data-scan="${esc(s.name)}" ${busy.has(s.name) || !can("operator") ? "disabled" : ""}>
          ${busy.has(s.name) ? '<i class="spin"></i>' : ic("scan")}
          <span>Scan</span>
        </button>
      </td>
    </tr>`;
  }).join("");
}

async function load() {
  const r = await api("/spaces");
  if (!r.ok) return;
  list = r.data;
  const sig = JSON.stringify(list) + filter + query + [...busy];
  if (sig !== lastList) {
    lastList = sig;
    renderStats();
    renderChips();
    renderRows();
  }
  if (sel) loadDetail();
}

/* ---------- drawer ---------- */
async function loadDetail() {
  let d;
  {
    const r = await api("/spaces/" + encodeURIComponent(sel));
    if (!r.ok) return;
    d = r.data;
  }
  const sig = JSON.stringify(d) + tab + [...busy];
  if (sig === lastDetail) return;
  lastDetail = sig;
  detail = d;
  renderDrawer();
}

function openDrawer(n) {
  sel = n;
  tab = "findings";
  detail = null;
  lastDetail = "";
  history.replaceState(null, "", "#env/" + n);
  $("#drawer").innerHTML = `<div class="db"><span class="spin"></span></div>`;
  $("#drawer").classList.add("on");
  $("#scrim").classList.add("on");
  $("#drawer").setAttribute("aria-hidden", "false");
  loadDetail();
}

function closeDrawer() {
  sel = null;
  history.replaceState(null, "", location.pathname);
  $("#drawer").classList.remove("on");
  $("#scrim").classList.remove("on");
  $("#drawer").setAttribute("aria-hidden", "true");
}

function findings(l) {
  if (!l || !l.extended) return `<div class="empty-state" style="padding:40px 10px"><h3>Not scanned yet</h3><p>Press Scan to evaluate all 14 baseline and 42 extended compliance checks.</p></div>`;
  const x = l.extended, sm = l.extended_summary, open = x.filter(c => c.status === "fail"), unk = x.filter(c => c.status === "unknown");
  let h = `<p class="mut sm" style="margin-top:0">${sm.failed} open · ${sm.passed} passed · ${sm.na} not applicable${sm.unknown ? ` · <b class="bad-t">${sm.unknown} could not be checked</b>` : ""} · scanned ${esc(ago(l.at))}</p>`;
  if (!open.length) h += `<div class="pill ok" style="padding:8px 12px;margin-bottom:14px"><i class="dot"></i> No open security or compliance findings</div>`;
  for (const sv of SEV) {
    const g = open.filter(c => c.severity === sv);
    if (!g.length) continue;
    h += `<div class="fgroup"><h3>${sv} severity (${g.length})</h3>` + g.map(c => `
      <details class="f" data-id="${esc(c.id)}" ${opened.has(c.id) ? "open" : ""}>
        <summary>
          <span class="pill ${sv === "high" ? "bad" : sv === "medium" ? "warn" : ""}">${sv}</span>
          <span><b>${esc(c.title)}</b><div class="sub">${esc(c.id)} · ${esc(c.area)}</div></span>
        </summary>
        <div class="fbody">
          <div class="mono" style="padding:8px;background:var(--panel2);border-radius:6px;margin-bottom:8px">${esc(c.evidence)}</div>
          <div class="fix"><b>Recommended Fix:</b> ${esc(c.fix)}</div>
        </div>
      </details>
    `).join("") + `</div>`;
  }
  if (unk.length) h += `<div class="note">Could not check ${unk.map(c => esc(c.id)).join(", ")}. ${esc(unk[0].evidence)}</div>`;
  const pass = x.filter(c => c.status === "pass");
  h += `<details class="f" style="margin-top:16px"><summary><b>${pass.length} extended checks passed</b></summary><div class="fbody">${pass.map(c => `<div class="crow" style="grid-template-columns:70px 1fr"><span class="mono mut">${esc(c.id)}</span><span>${esc(c.title)}</span></div>`).join("")}</div></details>`;
  return h;
}

function baseline(l) {
  if (!l) return `<div class="empty-state" style="padding:40px 10px"><h3>Not scanned yet</h3><p>Run a compliance scan to evaluate the 14 baseline controls.</p></div>`;
  return `<p class="mut sm" style="margin-top:0">These ${l.total} baseline controls determine compliant state. ${l.passed}/${l.total} passed.</p><div class="card">` +
    l.controls.map(c => `
      <div class="crow">
        <span class="mono mut">${esc(c.id)}</span>
        <span>
          <div style="font-weight:600">${esc(c.title)}</div>
          <div class="sub">${esc(c.evidence)}</div>
        </span>
        <span class="${c.passed ? 'ok-t' : 'bad-t'}">${c.passed ? 'Pass' : 'Fail'}</span>
      </div>
    `).join("") + `</div>`;
}

function pipeline(s) {
  const failed = s.status === "rejected" || s.status === "failed", ready = s.status === "ready", cur = failed ? (s.failed_stage || s.stage || 0) : (s.stage || 0);
  let h = STAGES.map(([k, d], i) => {
    const n = i + 1, c = ready || n < cur ? "d" : (n === cur ? (failed ? "f" : "c") : "");
    return `<div class="step ${c}"><span class="b">${c === "d" ? "✓" : n}</span><div><b>${esc(k)}</b><div class="sub">${esc(d)}${c === "f" ? " · stopped here" : ""}</div></div></div>`;
  }).join("");
  if (failed) h += `<h3 style="margin:16px 0 8px" class="bad-t">${s.status === "rejected" ? "Rejected by policy gate" : "Pipeline failed"} at stage ${s.failed_stage || "?"}</h3><pre>${esc(s.log)}</pre>`;
  return h;
}

function hist(s) {
  const h = (s.scans || []).slice().reverse();
  if (!h.length) return `<div class="empty-state" style="padding:40px 10px"><h3>No scans recorded yet</h3><p>Trigger a scan to record your first compliance audit.</p></div>`;
  return `<div class="card">` + h.map(x => `
    <div class="crow" style="grid-template-columns:1fr auto auto">
      <span>${new Date(x.at * 1000).toLocaleString()}</span>
      <span class="sub">${x.passed}/${x.total} baseline${x.findings != null ? ` · ${x.findings} findings` : ""}</span>
      <span class="pill ${GRADE[x.grade] || ''}">${esc(x.grade || (x.compliant ? "compliant" : "non-compliant"))}</span>
    </div>
  `).join("") + `</div>`;
}

function diff(s) {
  const l = s.latest, r = s.request || {};
  if (!l || !l.controls) return `<div class="empty-state" style="padding:40px 10px"><h3>No scan data</h3><p>Run a compliance scan to generate the live drift diff.</p></div>`;
  const failedCtrls = l.controls.filter(c => !c.passed);
  const openFindings = (l.extended || []).filter(c => c.status === "fail");
  
  if (!failedCtrls.length && !openFindings.length) {
    return `<div class="pill ok" style="padding:12px 16px;margin-bottom:14px"><i class="dot"></i> In Sync: 100% compliant with blueprint specifications. No infrastructure or workload drift detected.</div>`;
  }

  let h = `<p class="mut sm" style="margin-top:0">Comparing live inspected state against the declared blueprint specification (${esc(r.size || 'small')} tier):</p>`;

  if (failedCtrls.length) {
    h += `<div class="fgroup"><h3>Infrastructure & Baseline Drift (${failedCtrls.length})</h3>` +
      failedCtrls.map(c => `
        <div class="card" style="margin-bottom:10px;padding:12px">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
            <span class="mono bad-t" style="font-weight:600">${esc(c.id)}: ${esc(c.title)}</span>
            <span class="pill bad">Out of Spec</span>
          </div>
          <div style="background:var(--panel2);padding:8px 12px;border-radius:6px;font-family:monospace;font-size:12px;line-height:1.5">
            <div style="color:var(--bad)">- Live State: ${esc(c.evidence)}</div>
            <div style="color:var(--ok)">+ Blueprint Spec: Compliant with standard preset rules</div>
          </div>
        </div>
      `).join("") + `</div>`;
  }

  if (openFindings.length) {
    h += `<div class="fgroup" style="margin-top:16px"><h3>Workload Manifest Drift (${openFindings.length})</h3>` +
      openFindings.map(f => `
        <div class="card" style="margin-bottom:10px;padding:12px">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
            <span class="mono ${f.severity === 'high' ? 'bad-t' : 'warn-t'}" style="font-weight:600">${esc(f.id)}: ${esc(f.title)}</span>
            <span class="pill ${f.severity === 'high' ? 'bad' : 'warn'}">${esc(f.severity)}</span>
          </div>
          <div style="background:var(--panel2);padding:8px 12px;border-radius:6px;font-family:monospace;font-size:12px;line-height:1.5;margin-bottom:8px">
            <div style="color:var(--bad)">- Detected: ${esc(f.evidence)}</div>
            <div style="color:var(--ok)">+ Remediation: ${esc(f.fix)}</div>
          </div>
          <button class="btn sm" onclick="navigator.clipboard.writeText('${esc(f.fix)}');toast('Copied remediation snippet to clipboard!')" style="font-size:12px">
            📋 Copy YAML Remediation
          </button>
        </div>
      `).join("") + `</div>`;
  }

  return h;
}

function renderDrawer() {
  const s = detail, l = s.latest, r = s.request || {};
  const hasIssues = l && (!l.compliant || l.grade === "needs attention" || l.grade === "at risk" || l.grade === "non-compliant");
  const fixable = can("admin") && (hasIssues || s.status === "failed" || s.status === "rejected");
  $("#drawer").innerHTML = `
    <div class="dh">
      <div class="top">
        <div>
          <h2>${esc(sel)}</h2>
          <div class="sub">${esc(r.team || "")} · ${esc(r.environment || "")} · ${esc(r.size || "")} ${s.seconds_to_ready != null ? `· ready in ${fmt(s.seconds_to_ready)}` : ""}</div>
        </div>
        <button class="icon-btn" data-close aria-label="Close">${ic("x")}</button>
      </div>
      <div class="acts">${statusPill(s)} ${gradePill(l)}</div>
      <div class="acts">
        <button class="btn" data-scan="${esc(sel)}" ${busy.has(sel) || !can("operator") ? "disabled" : ""}>
          ${busy.has(sel) ? '<i class="spin"></i>' : ic("scan")}
          <span>Scan now</span>
        </button>
        ${fixable ? `<button class="btn pri" data-fix="${esc(sel)}" style="background:var(--acc);color:#fff">${ic("fix")}<span>Re-apply blueprint (Fix)</span></button>` : ""}
        ${can("admin") ? `<button class="btn" data-delete-env="${esc(sel)}" style="color:var(--bad);border-color:rgba(239,68,68,0.3)" title="Tear down and decommission environment">${ic("trash")}<span>Decommission</span></button>` : ""}
      </div>
      <div class="tabs">
        ${[["findings", "Findings"], ["baseline", "Baseline"], ["diff", "Drift Diff"], ["pipeline", "Pipeline"], ["history", "History"]].map(([k, t]) => `
          <button data-tab="${k}" class="${tab === k ? "on" : ""}">${t}</button>
        `).join("")}
      </div>
    </div>
    <div class="db">
      ${tab === "findings" ? findings(l) : tab === "baseline" ? baseline(l) : tab === "diff" ? diff(s) : tab === "pipeline" ? pipeline(s) : hist(s)}
      ${fixable && tab !== "pipeline" ? `<p class="mut sm" style="margin-top:16px">Re-apply restores what the blueprint manages. Out-of-band resources must be reconciled manually.</p>` : ""}
    </div>`;
}

/* ---------- rollouts ---------- */
async function loadRoll() {
  const rr = await api("/rollout");
  if (!rr.ok) return;
  const d = rr.data;
  fillVersions(d.versions || []);
  $("#renv").innerHTML = d.environments.length ? `
    <div class="table-responsive">
      <table>
        <thead>
          <tr>
            <th>Environment</th>
            <th>Team</th>
            <th>Kind</th>
            <th>Pinned Blueprint</th>
          </tr>
        </thead>
        <tbody>
          ${d.environments.map(e => `
            <tr>
              <td class="nm">${esc(e.name)}${e.canary ? ` <span class="pill acc">canary</span>` : ""}</td>
              <td>${esc(e.team)}</td>
              <td><span class="tag-badge ${e.environment === 'prod' ? 'prod' : (e.environment === 'test' ? 'test' : 'dev')}">${esc(e.environment)}</span></td>
              <td><span class="pill acc mono">${esc(e.version)}</span></td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    </div>` : `<div class="empty-state" style="padding:40px 10px"><h3>No registry initialized yet</h3><p>Run <span class="mono">python3 -m rollout demo-registry</span> to populate reference blueprints.</p></div>`;

  $("#rruns").innerHTML = d.runs.length ? d.runs.map(r => {
    const cls = ["completed", "nothing_to_do"].includes(r.status) ? "ok" : (r.status === "blocked_by_preview" ? "warn" : "bad");
    return `<div class="run">
      <div class="rh">
        <b class="mono" style="font-size:14px">${esc(r.version)}</b>
        <span class="pill ${cls}">${esc(r.status.replace(/_/g, " "))}</span>
        <span class="sub">${r.total_seconds ?? "?"}s · ${(r.targets || []).length} environments · ${r.at ? new Date(r.at * 1000).toLocaleString() : ""}</span>
      </div>
      <div style="margin-top:10px">
        ${(r.records || []).map(x => `
          <div class="rec">
            <span class="sub">${esc(x.stage)}</span>
            <span>${esc(x.name)}${x.ok ? "" : `<div class="sub bad-t">Rolled back: ${esc(x.rolled_back)}. ${esc((x.problems || []).join("; "))}</div>`}</span>
            <span class="${x.ok ? 'ok-t' : 'bad-t'}">${x.ok ? "ok" : "failed"} · ${x.seconds}s</span>
          </div>
        `).join("")}
        ${Object.entries(r.destroys || {}).map(([n, i]) => `
          <div class="rec">
            <span class="sub">blocked</span>
            <span>${esc(n)}<div class="sub">would destroy ${esc(i.join(", "))}</div></span>
            <span class="pill warn">preview</span>
          </div>
        `).join("")}
        ${r.not_attempted && r.not_attempted.length ? `<div class="sub" style="margin-top:6px">Not attempted: ${esc(r.not_attempted.join(", "))}</div>` : ""}
      </div>
    </div>`;
  }).join("") : `<div class="empty-state" style="padding:40px 10px"><h3>No rollouts recorded yet</h3><p>Version rollouts will appear here with canary and verification logs.</p></div>`;
}

function fillVersions(v) {
  const s = $("#rver");
  if (!s || (s.options.length === v.length && v.every((x, i) => s.options[i].value === x))) return;
  const cur = s.value;
  s.innerHTML = v.map(x => `<option value="${esc(x)}">${esc(x)}</option>`).join("");
  if (cur && v.includes(cur)) s.value = cur;
}

async function loadAct() {
  const [j, a] = await Promise.all([api("/jobs"), api("/audit")]);
  $("#jobs").innerHTML = j.ok && j.data.length ? `
    <div class="table-responsive">
      <table>
        <thead>
          <tr>
            <th>Job Type</th>
            <th>Target</th>
            <th>Status</th>
            <th>Actor</th>
            <th>Timestamp</th>
          </tr>
        </thead>
        <tbody>
          ${j.data.map(x => `
            <tr>
              <td class="nm">${esc(x.kind)}</td>
              <td><span class="mono">${esc(x.name)}</span></td>
              <td>
                <span class="pill ${x.status === "done" ? "ok" : x.status === "failed" ? "bad" : x.status === "running" ? "warn" : ""}">
                  ${esc(x.status)}
                </span>
                ${x.result && x.result.error ? `<div class="sub bad-t">${esc(x.result.error)}</div>` : ""}
              </td>
              <td class="sub">${esc(x.actor)}</td>
              <td class="sub">${esc(ago(x.created))}</td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    </div>` : `<div class="empty-state" style="padding:32px 10px"><h3>No pending jobs</h3><p>Background workers are idle.</p></div>`;

  $("#audit").innerHTML = a.ok && a.data.length ? `
    <div class="table-responsive">
      <table>
        <thead>
          <tr>
            <th>Actor</th>
            <th>Action</th>
            <th>Target Environment</th>
            <th>Timestamp</th>
          </tr>
        </thead>
        <tbody>
          ${a.data.map(x => `
            <tr>
              <td>${esc(x.actor)} <span class="pill">${esc(x.role)}</span></td>
              <td><span class="mono" style="font-weight:600">${esc(x.action)}</span></td>
              <td><span class="mono">${esc(x.target)}</span></td>
              <td class="sub">${new Date(x.at * 1000).toLocaleString()}</td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    </div>` : `<div class="empty-state" style="padding:32px 10px"><h3>Nothing recorded in audit log yet</h3></div>`;
}

/* ---------- events ---------- */
function page(p) {
  window._viewingConsole = true;
  const pGated = document.getElementById('p-gated');
  if (pGated) pGated.style.display = 'none';
  document.body.classList.remove('is-guest');
  $$("#nav button").forEach(b => b.classList.toggle("on", b.dataset.page === p));
  for (const k of ["env", "roll", "act", "how"]) {
    const el = $("#p-" + k);
    if (el) {
      el.hidden = k !== p;
      el.style.display = (k === p) ? '' : 'none';
    }
  }
  const pageNames = { "env": "Environments", "roll": "Rollouts", "act": "Activity", "how": "Architecture & Docs" };
  const titleEl = $("#topbar-page-name");
  if (titleEl) titleEl.textContent = pageNames[p] || "Console";
  if (p === "env") { lastList = ""; load(); }
  if (p === "roll") loadRoll();
  if (p === "act") loadAct();
  window.scrollTo(0, 0);
}

document.addEventListener("click", async e => {
  const t = e.target.closest("button, tr.row, details.f summary, a.icon-btn");
  if (!t) return;
  if (t.dataset.page) return page(t.dataset.page);
  if (t.dataset.chip) {
    filter = t.dataset.chip;
    lastList = "";
    return load();
  }
  if (t.dataset.tab) {
    tab = t.dataset.tab;
    lastDetail = "";
    return loadDetail();
  }
  if ("close" in t.dataset) return closeDrawer();

  // Sidebar toggle button handlers
  if (t.id === "sidebar-toggle" || t.id === "topbar-toggle-sidebar" || t.closest("#sidebar-toggle, #topbar-toggle-sidebar")) {
    toggleSidebar();
    return;
  }

  // Quick preset click in empty state
  if (t.id === "empty-new-btn") {
    $("#ferr").textContent = "";
    $("#dlg").showModal();
    return;
  }
  if (t.classList.contains("sugg-chip")) {
    $("#ferr").textContent = "";
    const f = $("#f");
    if (f) {
      if (t.dataset.quickName) f.name.value = t.dataset.quickName;
      if (t.dataset.quickTeam) f.team.value = t.dataset.quickTeam;
      if (t.dataset.quickEnv) f.environment.value = t.dataset.quickEnv;
      if (t.dataset.quickSize) f.size.value = t.dataset.quickSize;
      if (t.dataset.quickGrp) f.groups.value = t.dataset.quickGrp;
    }
    $("#dlg").showModal();
    return;
  }

  if (t.dataset.scan) {
    e.stopPropagation();
    const n = t.dataset.scan;
    busy.add(n);
    lastList = lastDetail = "";
    load();
    const r = await api(`/spaces/${encodeURIComponent(n)}/scan`, "POST");
    if (!r.ok) {
      toast(r.data.error || "Scan failed");
    } else {
      const j = await waitJob(r.data.job);
      const res = j && j.result || {};
      toast(j && j.status === "done" ? `${n}: ${res.grade}` : (j ? `Scan failed: ${res.error || "unknown error"}` : "Scan is still running"));
    }
    busy.delete(n);
    lastList = lastDetail = "";
    return load();
  }

  if (t.dataset.fix) {
    e.stopPropagation();
    const r = await api(`/spaces/${encodeURIComponent(t.dataset.fix)}/fix`, "POST");
    toast(r.ok ? "Re-applying blueprint..." : (r.data.error || "Could not start"));
    lastList = lastDetail = "";
    return load();
  }

  if (t.id === "batch-fix-btn") {
    const names = Array.from(selectedEnvNames);
    if (!names.length) return toast("No environments selected");
    const r = await api("/spaces/batch-fix", "POST", { names });
    if (r.ok) {
      toast(`Enqueued blueprint fix for ${r.data.count} environment(s)`);
      selectedEnvNames.clear();
      updateBatchBar();
    } else {
      toast(r.data.error || "Could not trigger batch fix");
    }
    lastList = lastDetail = "";
    return load();
  }

  if (t.id === "batch-fix-all-btn") {
    const r = await api("/spaces/batch-fix", "POST", {});
    if (r.ok) {
      toast(r.data.count > 0 ? `Enqueued fix for ${r.data.count} degraded environment(s)` : "All environments are already healthy");
      selectedEnvNames.clear();
      updateBatchBar();
    } else {
      toast(r.data.error || "Could not trigger batch fix");
    }
    lastList = lastDetail = "";
    return load();
  }

  if (t.dataset.deleteEnv) {
    const name = t.dataset.deleteEnv;
    if (!confirm(`Are you sure you want to decommission and delete environment '${name}'? This will tear down all associated resources.`)) {
      return;
    }
    const r = await api(`/spaces/${encodeURIComponent(name)}`, "DELETE");
    if (r.ok) {
      toast(`Environment '${name}' decommissioned successfully`);
      closeDrawer();
      lastList = lastDetail = "";
      return load();
    } else {
      toast(r.data.error || "Failed to decommission environment");
    }
  }

  if (t.id === "rpreview" || t.id === "rstart") {
    const version = $("#rver").value;
    if (!version) return toast("No blueprint versions found");
    const start = t.id === "rstart";
    $("#rmsg").innerHTML = '<i class="spin"></i> Queued...';
    t.disabled = true;
    const r = await api(start ? "/rollout/start" : "/rollout/preview", "POST", {
      version,
      allow_destroy: $("#rdestroy").checked
    });
    if (!r.ok) {
      $("#rmsg").textContent = r.data.error || "Could not queue";
      t.disabled = false;
      return;
    }
    const j = await waitJob(r.data.job, start ? 1800 : 600);
    t.disabled = false;
    const res = j && j.result || {};
    if (!j) $("#rmsg").textContent = "Still running. Check the Activity page.";
    else if (j.status === "failed" && res.error) $("#rmsg").innerHTML = `<span class="bad-t">Failed: ${esc(res.error)}</span>`;
    else if (start) $("#rmsg").innerHTML = `<span class="${res.ok ? "ok-t" : "bad-t"}">${esc(res.version)}: ${esc(String(res.status).replace(/_/g, " "))}</span>`;
    else {
      const p = res.plans || {}, n = Object.keys(p).length, d = Object.keys(res.destroys || {}).length;
      $("#rmsg").innerHTML = `${n} environment(s) would change.${d ? ` <span class="bad-t">${d} would destroy resources.</span>` : ' <span class="ok-t">Nothing is destroyed.</span>'}`;
    }
    return loadRoll();
  }

  if (t.id === "new") {
    $("#ferr").textContent = "";
    $("#dlg").showModal();
    return;
  }
  if (t.id === "cancel") return $("#dlg").close();
  if (t.matches("tr.row")) return openDrawer(t.dataset.open);
  if (t.tagName === "SUMMARY") {
    const d = t.parentElement;
    if (d.dataset.id) {
      setTimeout(() => d.open ? opened.add(d.dataset.id) : opened.delete(d.dataset.id));
    }
  }

  // Handle select-all checkbox change
  if (t.id === "select-all-env") {
    const visibleRows = filtered();
    if (t.checked) {
      visibleRows.forEach(s => selectedEnvNames.add(s.name));
    } else {
      visibleRows.forEach(s => selectedEnvNames.delete(s.name));
    }
    renderRows();
  }

  // Handle individual environment checkbox change
  if (t.classList.contains("env-chk")) {
    const name = t.dataset.selectName;
    if (name) {
      if (t.checked) selectedEnvNames.add(name);
      else selectedEnvNames.delete(name);
      updateBatchBar();
    }
  }
});

$("#scrim").onclick = closeDrawer;

function toggleSidebar() {
  const isCollapsed = document.body.classList.toggle("sidebar-collapsed");
  try {
    localStorage.setItem("sidebar_collapsed", isCollapsed ? "1" : "0");
  } catch (e) {}
}

(function () {
  try {
    if (localStorage.getItem("sidebar_collapsed") === "1") {
      document.body.classList.add("sidebar-collapsed");
    }
  } catch (e) {}
})();

document.addEventListener("keydown", e => {
  // Toggle sidebar with Ctrl+B or Cmd+B
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "b" && !$("#dlg").open) {
    e.preventDefault();
    toggleSidebar();
    return;
  }
  // Focus search with '/' key
  if (e.key === "/" && !["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement?.tagName) && !$("#dlg").open) {
    e.preventDefault();
    const q = $("#q");
    if (q) {
      q.focus();
      q.select();
    }
  }
  // Escape key dismissals
  if (e.key === "Escape") {
    if (document.activeElement?.id === "q") {
      document.activeElement.blur();
    } else if (sel && !$("#dlg").open) {
      closeDrawer();
    }
  }
});

$("#q").addEventListener("input", e => {
  query = e.target.value;
  lastList = "";
  load();
});

// Auto-fill admin group when selecting a known team
$("#fld-team")?.addEventListener("input", e => {
  const teamVal = e.target.value.trim().toLowerCase();
  const groupInput = $("#fld-groups");
  if (groupInput && (!groupInput.value || groupInput.value.endsWith("-admins"))) {
    if (teamVal) groupInput.value = `${teamVal}-admins`;
  }
});

$("#f").addEventListener("submit", async e => {
  e.preventDefault();
  const d = Object.fromEntries(new FormData(e.target));
  const b = $("#submit");
  b.disabled = true;
  const body = {
    name: d.name.trim().toLowerCase(),
    team: d.team.trim().toLowerCase(),
    environment: d.environment,
    size: d.size,
    blueprint: d.blueprint || "standard",
    admin_groups: d.groups.split(",").map(x => x.trim().toLowerCase()).filter(Boolean)
  };
  const r = await api("/spaces", "POST", body);
  if (r.ok) {
    $("#dlg").close();
    e.target.reset();
    toast(`Requested ${r.data.name}. The pipeline is queued.`);
    page("env");
    lastList = "";
    load();
  } else {
    $("#ferr").textContent = r.data.error || "Could not reach the server";
  }
  b.disabled = false;
});

(function () {
  const root = document.documentElement;
  try {
    const v = localStorage.getItem("theme");
    if (v) root.dataset.theme = v;
  } catch (e) {}

  const isDark = () => root.dataset.theme ? root.dataset.theme === "dark" : matchMedia("(prefers-color-scheme:dark)").matches;
  const updateIcon = () => {
    const dark = isDark();
    const iconName = dark ? "sun" : "moon";
    const themeBtn = $("#theme");
    if (themeBtn) {
      themeBtn.innerHTML = ic(iconName) + ` <span>${dark ? "Switch to Light Mode" : "Switch to Dark Mode"}</span>`;
    }
  };
  updateIcon();

  const themeBtn = $("#theme");
  if (themeBtn) {
    themeBtn.addEventListener("click", () => {
      root.dataset.theme = isDark() ? "light" : "dark";
      try { localStorage.setItem("theme", root.dataset.theme); } catch (e) {}
      updateIcon();
    });
  }
})();

if (location.hash.startsWith("#env/")) {
  setTimeout(() => openDrawer(decodeURIComponent(location.hash.slice(5))), 0);
}

async function checkHealth() {
  const pill = $("#health-pill");
  const dot = $("#health-dot");
  const label = $("#health-label");
  const sideSub = $(".brand-sub");

  try {
    const res = await fetch("/healthz", { cache: "no-store" });
    const data = await res.json();
    if (res.ok && data && data.ok) {
      if (pill) { pill.className = "topbar-pill ok"; pill.title = "API Healthy · Checked just now (auto-checks every 15m)"; }
      if (dot) dot.className = "brand-dot";
      if (label) label.textContent = "API Healthy";
      if (sideSub) sideSub.innerHTML = '<span class="brand-dot"></span><span>Engine Ready</span>';
    } else {
      throw new Error("Unhealthy response");
    }
  } catch (err) {
    if (pill) { pill.className = "topbar-pill error"; pill.title = "API Error: Unable to reach /healthz · Auto-checks every 15m"; }
    if (dot) dot.className = "brand-dot error";
    if (label) label.textContent = "API Disconnected";
    if (sideSub) sideSub.innerHTML = '<span class="brand-dot error"></span><span style="color:var(--bad)">Engine Error</span>';
  }
}

async function refreshUser() {
  const r = await api("/api/me");
  if (r.ok) {
    me = r.data;
  } else {
    me = { id: "", role: "none" };
  }
  applyRole();
}

(async () => {
  const r = await api("/api/me");
  if (r.ok) {
    me = r.data;
  } else {
    $("#who").textContent = r.status === 403 ? "Access denied" : "Sign in required";
  }
  applyRole();
  await load();
  await checkHealth();
  setInterval(checkHealth, 15 * 60 * 1000); // Poll /healthz automatically every 15 minutes
  setInterval(() => {
    load();
    if (!$("#p-roll").hidden) loadRoll();
    if (!$("#p-act").hidden) loadAct();
  }, 3000);
})();



/* -----------------------------------------------------------------------------
   AI Platform Copilot Chatbot Controller
----------------------------------------------------------------------------- */
const cbTrigger = $("#chatbot-trigger");
const cbNavBtn = $("#nav-copilot-btn");
const cbPanel = $("#chatbot-panel");
const cbClose = $("#chatbot-close");
const cbClear = $("#chatbot-clear");
const cbForm = $("#chatbot-form");
const cbInput = $("#chatbot-input");
const cbMessages = $("#chatbot-messages");

function toggleChatbot() {
  if (!cbPanel) return;
  const isHidden = cbPanel.hasAttribute("hidden");
  if (isHidden) {
    cbPanel.removeAttribute("hidden");
    setTimeout(() => cbInput && cbInput.focus(), 50);
  } else {
    cbPanel.setAttribute("hidden", "");
  }
}

if (cbTrigger) cbTrigger.onclick = toggleChatbot;
if (cbNavBtn) cbNavBtn.onclick = toggleChatbot;
if (cbClose) cbClose.onclick = () => cbPanel && cbPanel.setAttribute("hidden", "");
if (cbClear) {
  cbClear.onclick = () => {
    if (cbMessages) {
      cbMessages.innerHTML = `
        <div class="cb-msg bot">
          <div class="cb-bubble">
            Chat cleared. How can I assist you with your Kubernetes environments and compliance controls today?
            <div class="cb-time">Just now</div>
          </div>
        </div>`;
    }
  };
}

let chatSessionId = 'session_' + Math.random().toString(36).substring(2, 9);

function renderMarkdown(md) {
  if (!md) return '';
  let out = esc(md);
  out = out.replace(/\*\*(.*?)\*\*/g, '<b>$1</b>');
  out = out.replace(/`([^`]+)`/g, '<code style="background:var(--panel2);padding:1px 5px;border-radius:4px;font-family:JetBrains Mono,monospace;font-size:11.5px;color:var(--acc)">$1</code>');
  out = out.replace(/^•\s+(.*)$/gm, '<li style="margin-left:14px;list-style:disc">$1</li>');
  out = out.replace(/^###\s+(.*)$/gm, '<div style="font-weight:700;font-size:13.5px;margin:6px 0 2px">$1</div>');
  out = out.replace(/\n/g, '<br>');
  return out;
}

function appendCbMessage(text, sender = 'bot', card = null, suggestions = null) {
  if (!cbMessages) return;
  const div = document.createElement('div');
  div.className = `cb-msg ${sender}`;

  const timeStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  const renderedContent = sender === 'bot' ? renderMarkdown(text) : esc(text);

  let html = `<div class="cb-bubble">${renderedContent}`;

  if (card) {
    html += `
      <div style="margin-top:10px;background:var(--panel2);border:1px solid var(--line);border-radius:10px;padding:12px;font-size:12.5px">
        <div style="font-weight:700;color:var(--fg);margin-bottom:8px;display:flex;align-items:center;gap:6px">
          ${esc(card.title || 'Details')}
        </div>`;
    if (card.fields && card.fields.length) {
      card.fields.forEach(f => {
        html += `<div style="margin-bottom:3px;display:flex;justify-content:space-between;gap:8px"><span style="color:var(--mut)">${esc(f.label)}:</span><span style="font-weight:600;color:var(--fg)">${esc(f.val)}</span></div>`;
      });
    }
    if (card.action_url) {
      html += `<div style="margin-top:10px"><a class="btn pri sm" href="${esc(card.action_url)}" download style="text-decoration:none">${esc(card.action_label || 'Download')}</a></div>`;
    }
    html += `</div>`;
  }

  if (suggestions && suggestions.length) {
    html += `<div style="display:flex;flex-wrap:wrap;gap:6px;margin-top:10px">`;
    suggestions.forEach(sug => {
      const cleanSug = sug.replace(/"/g, '&quot;');
      html += `<button class="btn sm" onclick="handleCopilotCommand('${cleanSug}')" style="font-size:11.5px;padding:4px 9px">${esc(sug)}</button>`;
    });
    html += `</div>`;
  }

  html += `<div class="cb-time">${timeStr}</div></div>`;
  div.innerHTML = html;
  cbMessages.appendChild(div);
  cbMessages.scrollTop = cbMessages.scrollHeight;
}

function showTypingIndicator() {
  if (!cbMessages) return null;
  const div = document.createElement('div');
  div.className = 'cb-msg bot typing-ind';
  div.innerHTML = `<div class="cb-bubble" style="padding:8px 14px;color:var(--mut);display:flex;gap:4px;align-items:center"><span class="spin" style="width:10px;height:10px"></span> <span>Thinking...</span></div>`;
  cbMessages.appendChild(div);
  cbMessages.scrollTop = cbMessages.scrollHeight;
  return div;
}

async function handleCopilotCommand(text) {
  const q = text.trim();
  if (!q) return;

  const typing = showTypingIndicator();

  try {
    const res = await api('/api/chat', 'POST', {
      message: q,
      session_id: chatSessionId
    });

    if (typing && typing.parentNode) {
      typing.parentNode.removeChild(typing);
    }

    if (res.ok && res.data) {
      appendCbMessage(res.data.reply, 'bot', res.data.card, res.data.suggestions);
      if (res.data.card && (res.data.card.type === 'success_env' || res.data.card.type === 'confirm_fix')) {
        load();
      }
    } else {
      appendCbMessage('Sorry, I encountered an issue connecting to the Platform Copilot engine. Please try again.', 'bot');
    }
  } catch (err) {
    if (typing && typing.parentNode) typing.parentNode.removeChild(typing);
    appendCbMessage('Network error communicating with Copilot backend: ' + (err.message || 'Error'), 'bot');
  }
}

if (cbForm) {
  cbForm.onsubmit = async e => {
    e.preventDefault();
    const val = cbInput ? cbInput.value.trim() : '';
    if (!val) return;
    appendCbMessage(val, 'user');
    cbInput.value = '';
    await handleCopilotCommand(val);
  };
}

document.addEventListener('click', e => {
  const chip = e.target.closest('.cb-chip');
  if (chip && chip.dataset.cbPrompt) {
    const prompt = chip.dataset.cbPrompt;
    appendCbMessage(prompt, 'user');
    handleCopilotCommand(prompt);
  }
});

/* -----------------------------------------------------------------------------
   Enterprise Authentication Modal Handler (Sign In & Sign Up)
----------------------------------------------------------------------------- */
let authMode = 'login'; // 'login' | 'signup'

const tabLogin = document.getElementById('tab-auth-login');
const tabSignup = document.getElementById('tab-auth-signup');
const authExtraFields = document.getElementById('auth-extra-fields');
const authTitle = document.getElementById('auth-modal-title');
const authSubmit = document.getElementById('auth-submit');
const authForm = document.getElementById('auth-form');
const authErr = document.getElementById('auth-err');
const authCancel = document.getElementById('auth-cancel');

if (tabLogin && tabSignup) {
  tabLogin.onclick = () => {
    authMode = 'login';
    tabLogin.classList.add('active');
    tabSignup.classList.remove('active');
    tabLogin.style.background = '';
    tabLogin.style.boxShadow = '';
    tabSignup.style.background = '';
    tabSignup.style.boxShadow = '';
    if (authExtraFields) authExtraFields.style.display = 'none';
    if (authTitle) authTitle.textContent = 'Enterprise Sign In';
    if (authSubmit) {
      authSubmit.innerHTML = '<span>Sign In</span><svg class="i sm-i"><use href="#i-chevron-right"/></svg>';
    }
    if (authErr) authErr.style.display = 'none';
  };

  tabSignup.onclick = () => {
    authMode = 'signup';
    tabSignup.classList.add('active');
    tabLogin.classList.remove('active');
    tabSignup.style.background = '';
    tabSignup.style.boxShadow = '';
    tabLogin.style.background = '';
    tabLogin.style.boxShadow = '';
    if (authExtraFields) authExtraFields.style.display = 'flex';
    if (authTitle) authTitle.textContent = 'Create Enterprise Account';
    if (authSubmit) {
      authSubmit.innerHTML = '<span>Create Account</span><svg class="i sm-i"><use href="#i-check"/></svg>';
    }
    if (authErr) authErr.style.display = 'none';
  };
}

// Password show/hide toggle
const pwdToggle = document.getElementById('auth-pwd-toggle');
const pwdInput = document.getElementById('auth-password');
if (pwdToggle && pwdInput) {
  pwdToggle.onclick = () => {
    const isPwd = pwdInput.type === 'password';
    pwdInput.type = isPwd ? 'text' : 'password';
  };
}

// Top X close button
const authCloseX = document.getElementById('auth-close-x');
if (authCloseX) {
  authCloseX.onclick = () => {
    const d = document.getElementById('auth-dlg');
    if (d) d.close();
  };
}

// Quick 1-click Preset Fill Chips
document.querySelectorAll('.auth-preset-pill').forEach(btn => {
  btn.onclick = () => {
    const p = btn.dataset.preset;
    const uField = document.getElementById('auth-username');
    const pField = document.getElementById('auth-password');
    if (uField && pField) {
      if (p === 'admin') {
        uField.value = 'admin';
        pField.value = 'admin123';
      } else if (p === 'operator') {
        uField.value = 'operator';
        pField.value = 'operator123';
      } else if (p === 'viewer') {
        uField.value = 'viewer';
        pField.value = 'viewer123';
      }
      if (tabLogin) tabLogin.click();
      uField.focus();
    }
  };
});

if (authCancel) {
  authCancel.onclick = () => {
    const d = document.getElementById('auth-dlg');
    if (d) d.close();
  };
}

if (authForm) {
  authForm.onsubmit = async e => {
    e.preventDefault();
    if (authErr) authErr.style.display = 'none';
    const username = document.getElementById('auth-username').value.trim();
    const password = document.getElementById('auth-password').value;
    const fullname = document.getElementById('auth-fullname') ? document.getElementById('auth-fullname').value.trim() : '';
    const role = document.getElementById('auth-role') ? document.getElementById('auth-role').value : 'viewer';

    const endpoint = authMode === 'signup' ? '/api/auth/signup' : '/api/auth/login';
    const payload = authMode === 'signup' ? { username, password, role, name: fullname } : { username, password };

    try {
      const res = await api(endpoint, 'POST', payload);
      if (res.ok) {
        try { localStorage.setItem('platform_token', username); } catch (e) {}
        const d = document.getElementById('auth-dlg');
        if (d) d.close();
        const u = res.data?.user || res.data;
        toast(`Signed in as ${u?.name || u?.id || username} (${u?.role || 'user'})`);
        await refreshUser();
        load();
      } else {
        if (authErr) {
          authErr.textContent = res.data?.error || 'Authentication failed';
          authErr.style.display = 'block';
        }
      }
    } catch (err) {
      if (authErr) {
        authErr.textContent = err.message || 'Network error';
        authErr.style.display = 'block';
      }
    }
  };
}

async function handleLogout() {
  try {
    try { localStorage.removeItem('platform_token'); } catch (e) {}
    if (accountDropdown) accountDropdown.setAttribute('hidden', '');
    await api('/api/auth/logout', 'POST', {});
    toast('Logged out successfully');
    const d = document.getElementById('auth-dlg');
    if (d) d.close();
    me = { id: 'guest', role: 'viewer', name: 'Guest' };
    applyRole();
    await refreshUser();
    load();
  } catch (err) {
    toast('Logout failed: ' + (err.message || 'Error'));
  }
}

const logoutBtn = document.getElementById('auth-logout-btn');
if (logoutBtn) logoutBtn.onclick = handleLogout;

const modalLogoutBtn = document.getElementById('auth-modal-logout');
if (modalLogoutBtn) modalLogoutBtn.onclick = handleLogout;

const topbarAccountBtn = document.getElementById('topbar-account-btn');
const accountDropdown = document.getElementById('account-dropdown');

if (topbarAccountBtn && accountDropdown) {
  topbarAccountBtn.onclick = (e) => {
    e.stopPropagation();
    const isHidden = accountDropdown.hasAttribute('hidden');
    if (isHidden) {
      accountDropdown.removeAttribute('hidden');
      topbarAccountBtn.setAttribute('aria-expanded', 'true');
    } else {
      accountDropdown.setAttribute('hidden', '');
      topbarAccountBtn.setAttribute('aria-expanded', 'false');
    }
  };

  document.addEventListener('click', (e) => {
    if (!accountDropdown.hasAttribute('hidden') && !accountDropdown.contains(e.target) && e.target !== topbarAccountBtn) {
      accountDropdown.setAttribute('hidden', '');
      topbarAccountBtn.setAttribute('aria-expanded', 'false');
    }
  });
}

const ddProfileBtn = document.getElementById('dd-profile-btn');
if (ddProfileBtn) {
  ddProfileBtn.onclick = () => {
    if (accountDropdown) accountDropdown.setAttribute('hidden', '');
    const d = document.getElementById('auth-dlg');
    if (d) d.showModal();
  };
}

const ddSettingsBtn = document.getElementById('dd-settings-btn');
if (ddSettingsBtn) {
  ddSettingsBtn.onclick = () => {
    if (accountDropdown) accountDropdown.setAttribute('hidden', '');
    const d = document.getElementById('auth-dlg');
    if (d) d.showModal();
  };
}

const topbarLogoutBtn = document.getElementById('topbar-logout-btn');
if (topbarLogoutBtn) {
  topbarLogoutBtn.onclick = handleLogout;
}

// ---------------- Sidebar Hover Motion Interaction ----------------
(function() {
  const sideEl = document.querySelector('.side');
  let hoverTimeout = null;

  if (sideEl) {
    sideEl.addEventListener('mouseenter', () => {
      if (document.body.classList.contains('sidebar-collapsed')) {
        clearTimeout(hoverTimeout);
        hoverTimeout = setTimeout(() => {
          document.body.classList.add('sidebar-hover-expanded');
        }, 60);
      }
    });

    sideEl.addEventListener('mouseleave', () => {
      clearTimeout(hoverTimeout);
      if (document.body.classList.contains('sidebar-hover-expanded')) {
        hoverTimeout = setTimeout(() => {
          document.body.classList.remove('sidebar-hover-expanded');
        }, 120);
      }
    });
  }
})();


/* -----------------------------------------------------------------------------
   Landing Page Interactive Motions & Scroll Observer
----------------------------------------------------------------------------- */
function initLandingMotions() {
  const elements = document.querySelectorAll('.animate-on-scroll');
  if (!elements.length) return;

  if ('IntersectionObserver' in window) {
    const observer = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          entry.target.classList.add('is-visible');
        }
      });
    }, { threshold: 0.12 });

    elements.forEach(el => observer.observe(el));
  } else {
    elements.forEach(el => el.classList.add('is-visible'));
  }

  // Active glowing pulse sequencing through the 10-stage pipeline
  const stepCards = document.querySelectorAll('.landing-step-card');
  if (stepCards.length) {
    let currentStep = 0;
    setInterval(() => {
      stepCards.forEach((c, idx) => {
        c.classList.toggle('active-pulse', idx === currentStep);
      });
      currentStep = (currentStep + 1) % stepCards.length;
    }, 1800);
  }
}

// Trigger motions once DOM is interactive
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initLandingMotions);
} else {
  initLandingMotions();
}


/* -----------------------------------------------------------------------------
   Enterprise Cluster & Cloud Backend Onboarding Wizard
----------------------------------------------------------------------------- */
window.openClusterModal = function() {
  const d = document.getElementById('cluster-dlg');
  if (d) d.showModal();
};

function initClusterDialog() {
  // Provider card click selection
  document.querySelectorAll('.cluster-provider-card').forEach(card => {
    card.addEventListener('click', () => {
      document.querySelectorAll('.cluster-provider-card').forEach(c => c.classList.remove('active'));
      card.classList.add('active');
      const radio = card.querySelector('input[type="radio"]');
      if (radio) radio.checked = true;
    });
  });

  // Auth mode tabs
  document.querySelectorAll('.cluster-auth-tab').forEach(tab => {
    tab.addEventListener('click', () => {
      document.querySelectorAll('.cluster-auth-tab').forEach(t => t.classList.remove('on'));
      tab.classList.add('on');
      const auth = tab.dataset.auth;
      const panels = {
        'sts_assumerole': 'auth-panel-sts',
        'helm_agent': 'auth-panel-helm',
        'scoped_token': 'auth-panel-token'
      };
      Object.entries(panels).forEach(([k, panelId]) => {
        const el = document.getElementById(panelId);
        if (el) el.style.display = (k === auth) ? 'block' : 'none';
      });
    });
  });

  // Test Connection button
  const testBtn = document.getElementById('cluster-test-btn');
  const banner = document.getElementById('cluster-test-banner');
  if (testBtn) {
    testBtn.addEventListener('click', async () => {
      testBtn.disabled = true;
      testBtn.innerHTML = '<i class="spin"></i> <span>Testing Connection...</span>';
      if (banner) {
        banner.style.display = 'block';
        banner.style.background = 'rgba(99, 102, 241, 0.1)';
        banner.style.border = '1px solid rgba(99, 102, 241, 0.3)';
        banner.style.color = '#818cf8';
        banner.innerHTML = 'Establishing secure handshake with cluster control plane...';
      }

      const activeCard = document.querySelector('.cluster-provider-card.active');
      const provider = activeCard ? activeCard.dataset.provider : 'aws_eks';
      const activeTab = document.querySelector('.cluster-auth-tab.on');
      const authMode = activeTab ? activeTab.dataset.auth : 'sts_assumerole';

      try {
        const r = await api('/api/clusters/test', 'POST', { provider, auth_mode: authMode });
        testBtn.disabled = false;
        testBtn.innerHTML = '<svg class="i sm-i"><use href="#i-sparkles"/></svg> <span>Test Connection</span>';
        if (r.ok) {
          banner.style.background = 'rgba(16, 185, 129, 0.12)';
          banner.style.border = '1px solid rgba(16, 185, 129, 0.4)';
          banner.style.color = '#34d399';
          banner.innerHTML = '<strong>Connection Verified:</strong> ' + r.data.message + ' (Latency: ' + r.data.latency_ms + 'ms)';
        } else {
          banner.style.background = 'rgba(239, 68, 68, 0.12)';
          banner.style.border = '1px solid rgba(239, 68, 68, 0.4)';
          banner.style.color = '#f87171';
          banner.innerHTML = '<strong>Connection Failed:</strong> ' + (r.data.error || 'Failed to reach cluster');
        }
      } catch (err) {
        testBtn.disabled = false;
        testBtn.innerHTML = '<svg class="i sm-i"><use href="#i-sparkles"/></svg> <span>Test Connection</span>';
        if (banner) {
          banner.style.background = 'rgba(239, 68, 68, 0.12)';
          banner.style.border = '1px solid rgba(239, 68, 68, 0.4)';
          banner.style.color = '#f87171';
          banner.innerHTML = '<strong>Connection Error:</strong> ' + err.message;
        }
      }
    });
  }

  // Save & Enroll button
  const saveBtn = document.getElementById('cluster-enroll-submit-btn');
  if (saveBtn) {
    saveBtn.addEventListener('click', async () => {
      const nameInput = document.getElementById('cluster-name-input');
      const name = nameInput ? nameInput.value.trim() : '';
      if (!name) {
        toast('Please enter a cluster name');
        return;
      }
      saveBtn.disabled = true;
      saveBtn.innerHTML = '<i class="spin"></i> <span>Enrolling...</span>';

      const activeCard = document.querySelector('.cluster-provider-card.active');
      const provider = activeCard ? activeCard.dataset.provider : 'aws_eks';
      const activeTab = document.querySelector('.cluster-auth-tab.on');
      const authMode = activeTab ? activeTab.dataset.auth : 'sts_assumerole';
      const roleArn = document.getElementById('cluster-role-arn') ? document.getElementById('cluster-role-arn').value : '';
      const extId = document.getElementById('cluster-ext-id') ? document.getElementById('cluster-ext-id').value : '';
      const prefixes = document.getElementById('cluster-prefixes-input') ? document.getElementById('cluster-prefixes-input').value : '';

      try {
        const r = await api('/api/clusters', 'POST', {
          name,
          provider,
          auth_mode: authMode,
          role_arn: roleArn,
          external_id: extId,
          allowed_prefixes: prefixes
        });
        saveBtn.disabled = false;
        saveBtn.innerHTML = 'Save & Enroll Cluster';
        if (r.ok) {
          toast('Cluster "' + name + '" enrolled successfully!');
          const d = document.getElementById('cluster-dlg');
          if (d) d.close();
        } else {
          toast('Enrollment error: ' + (r.data.error || 'Failed'));
        }
      } catch (err) {
        saveBtn.disabled = false;
        saveBtn.innerHTML = 'Save & Enroll Cluster';
        toast('Error: ' + err.message);
      }
    });
  }
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initClusterDialog);
} else {
  initClusterDialog();
}
