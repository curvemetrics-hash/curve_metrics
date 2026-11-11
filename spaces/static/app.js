
window.showConsole = function() {
  window._viewingConsole = true;
  const pGated = document.getElementById('p-gated');
  const pEnv = document.getElementById('p-env');
  const consoleBar = document.querySelector('.app-console-bar');
  if (pGated) pGated.style.display = 'none';
  if (pEnv) pEnv.style.display = '';
  if (consoleBar) consoleBar.style.display = '';
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
  const consoleBar = document.querySelector('.app-console-bar');
  if (pGated) pGated.style.display = 'block';
  if (pEnv) pEnv.style.display = 'none';
  if (pRoll) pRoll.style.display = 'none';
  if (pAct) pAct.style.display = 'none';
  if (pHow) pHow.style.display = 'none';
  if (consoleBar) consoleBar.style.display = 'none';
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
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 12000);
  try {
    const r = await fetch(API_BASE + path, {
      method,
      credentials: "include",
      headers,
      body: body ? JSON.stringify(body) : undefined,
      signal: controller.signal
    });
    clearTimeout(timeoutId);
    let j = {};
    try { j = await r.json(); } catch (e) {}
    if (r.status === 401 && me.id && me.id !== "guest") { toast("Your session expired. Reload the page to sign in again."); }
    return { ok: r.ok, status: r.status, data: j };
  } catch (err) {
    clearTimeout(timeoutId);
    console.warn(`[API] Network error or timeout for ${method} ${path}:`, err.message);
    return { ok: false, status: 0, error: err.message, data: null };
  }
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
  const consoleBar = document.querySelector('.app-console-bar');
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
    if (consoleBar) consoleBar.style.display = 'none';
    if (titleEl) titleEl.textContent = 'Platform Overview';
  } else {
    document.body.classList.remove('is-guest');
    if (topbarAccountBtn) topbarAccountBtn.style.display = 'flex';
    if (topbarSignInBtn) topbarSignInBtn.style.display = isGuest ? 'inline-flex' : 'none';
    if (modalLogoutBtn) modalLogoutBtn.style.display = isGuest ? 'none' : 'inline-flex';
    if (pGated) pGated.style.display = 'none';
    if (pEnv) pEnv.style.display = '';
    if (consoleBar) consoleBar.style.display = '';
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

  const btmLaunchBtn = document.getElementById('bottom-cta-launch-btn');
  if (btmLaunchBtn) {
    btmLaunchBtn.onclick = () => {
      window.showConsole();
    };
  }

  const btmDemoBtn = document.getElementById('bottom-cta-demo-btn');
  if (btmDemoBtn) {
    btmDemoBtn.onclick = () => {
      autoLogin('admin', 'admin123');
    };
  }

  const btmSignInBtn = document.getElementById('bottom-cta-signin-btn');
  if (btmSignInBtn) {
    btmSignInBtn.onclick = () => {
      const d = document.getElementById('auth-dlg');
      if (d) d.showModal();
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

const DEFAULT_SPACES = [{"name": "analytics-dev", "status": "ready", "stage": 10, "failed_stage": null, "team": "data", "requested_at": 1794330405, "size": "small", "environment": "dev", "seconds_to_ready": 72, "seconds_to_compliant": 114, "latest": {"passed": 14, "total": 14, "compliant": true, "at": 1794330519, "grade": "healthy", "extended_summary": {"total": 42, "passed": 42, "failed": 0, "na": 0, "unknown": 0, "severity": {"high": 0, "medium": 0, "low": 0}}}}, {"name": "auth-service-prod", "status": "ready", "stage": 10, "failed_stage": null, "team": "security", "requested_at": 1794332677, "size": "large", "environment": "prod", "seconds_to_ready": 73, "seconds_to_compliant": 78, "latest": {"passed": 14, "total": 14, "compliant": true, "at": 1794332755, "grade": "healthy", "extended_summary": {"total": 42, "passed": 42, "failed": 0, "na": 0, "unknown": 0, "severity": {"high": 0, "medium": 0, "low": 0}}}}, {"name": "billing-prod", "status": "ready", "stage": 10, "failed_stage": null, "team": "billing", "requested_at": 1794330412, "size": "large", "environment": "prod", "seconds_to_ready": 146, "seconds_to_compliant": 150, "latest": {"passed": 14, "total": 14, "compliant": true, "at": 1794330562, "grade": "healthy", "extended_summary": {"total": 42, "passed": 42, "failed": 0, "na": 0, "unknown": 0, "severity": {"high": 0, "medium": 0, "low": 0}}}}, {"name": "checkout-dev", "status": "ready", "stage": 10, "failed_stage": 0, "team": "checkout", "requested_at": 1794326115, "size": "small", "environment": "dev", "seconds_to_ready": null, "seconds_to_compliant": 732, "latest": {"passed": 14, "total": 14, "compliant": true, "at": 1794326847, "grade": "healthy", "extended_summary": {"total": 42, "passed": 42, "failed": 0, "na": 0, "unknown": 0, "severity": {"high": 0, "medium": 0, "low": 0}}}}, {"name": "checkout-floci-prod", "status": "rejected", "stage": null, "failed_stage": 0, "team": "checkout", "requested_at": 1794352156, "size": "small", "environment": "prod", "seconds_to_ready": null, "seconds_to_compliant": null, "latest": {}}, {"name": "floci-cloud-prod", "status": "ready", "stage": 10, "failed_stage": null, "team": "checkout", "requested_at": 1794352367, "size": "medium", "environment": "prod", "seconds_to_ready": 36, "seconds_to_compliant": 41, "latest": {"passed": 14, "total": 14, "compliant": true, "at": 1794352408, "grade": "healthy", "extended_summary": {"total": 42, "passed": 42, "failed": 0, "na": 0, "unknown": 0, "severity": {"high": 0, "medium": 0, "low": 0}}}}, {"name": "marketing-web-test", "status": "ready", "stage": 10, "failed_stage": null, "team": "marketing", "requested_at": 1794332683, "size": "small", "environment": "test", "seconds_to_ready": 111, "seconds_to_compliant": 115, "latest": {"passed": 14, "total": 14, "compliant": true, "at": 1794332798, "grade": "healthy", "extended_summary": {"total": 42, "passed": 42, "failed": 0, "na": 0, "unknown": 0, "severity": {"high": 0, "medium": 0, "low": 0}}}}, {"name": "notifications-worker-dev", "status": "ready", "stage": 10, "failed_stage": null, "team": "messaging", "requested_at": 1794332690, "size": "small", "environment": "dev", "seconds_to_ready": 147, "seconds_to_compliant": 152, "latest": {"passed": 14, "total": 14, "compliant": true, "at": 1794332842, "grade": "healthy", "extended_summary": {"total": 42, "passed": 42, "failed": 0, "na": 0, "unknown": 0, "severity": {"high": 0, "medium": 0, "low": 0}}}}, {"name": "orders-staging", "status": "ready", "stage": 10, "failed_stage": null, "team": "orders", "requested_at": 1794330399, "size": "medium", "environment": "test", "seconds_to_ready": 35, "seconds_to_compliant": 40, "latest": {"passed": 14, "total": 14, "compliant": true, "at": 1794330439, "grade": "healthy", "extended_summary": {"total": 42, "passed": 42, "failed": 0, "na": 0, "unknown": 0, "severity": {"high": 0, "medium": 0, "low": 0}}}}, {"name": "payments", "status": "ready", "stage": 10, "failed_stage": null, "team": "payments", "requested_at": 1794418929, "size": "small", "environment": "dev", "seconds_to_ready": 36, "seconds_to_compliant": 41, "latest": {"passed": 14, "total": 14, "compliant": true, "at": 1794418970, "grade": "healthy", "extended_summary": {"total": 42, "passed": 42, "failed": 0, "na": 0, "unknown": 0, "severity": {"high": 0, "medium": 0, "low": 0}}}}, {"name": "payments-prod", "status": "ready", "stage": 10, "failed_stage": 0, "team": "payments", "requested_at": 1794322458, "size": "small", "environment": "dev", "seconds_to_ready": null, "seconds_to_compliant": 4447, "latest": {"passed": 14, "total": 14, "compliant": true, "at": 1794326905, "grade": "healthy", "extended_summary": {"total": 42, "passed": 42, "failed": 0, "na": 0, "unknown": 0, "severity": {"high": 0, "medium": 0, "low": 0}}}}, {"name": "pr-preview-dev", "status": "ready", "stage": 10, "failed_stage": null, "team": "checkout", "requested_at": 1794327843, "size": "small", "environment": "dev", "seconds_to_ready": 36, "seconds_to_compliant": 42, "latest": {"passed": 14, "total": 14, "compliant": true, "at": 1794327885, "grade": "healthy", "extended_summary": {"total": 42, "passed": 42, "failed": 0, "na": 0, "unknown": 0, "severity": {"high": 0, "medium": 0, "low": 0}}}}, {"name": "recommend-ai-dev", "status": "ready", "stage": 10, "failed_stage": null, "team": "ai", "requested_at": 1794332670, "size": "medium", "environment": "dev", "seconds_to_ready": 36, "seconds_to_compliant": 41, "latest": {"passed": 14, "total": 14, "compliant": true, "at": 1794332711, "grade": "healthy", "extended_summary": {"total": 42, "passed": 42, "failed": 0, "na": 0, "unknown": 0, "severity": {"high": 0, "medium": 0, "low": 0}}}}];

function getInitialSpaces() {
  try {
    const cached = localStorage.getItem("curve_cached_spaces");
    if (cached) {
      const parsed = JSON.parse(cached);
      if (Array.isArray(parsed) && parsed.length > 0) return parsed;
    }
  } catch (e) {}
  return DEFAULT_SPACES.slice();
}

let list = getInitialSpaces(), filter = "all", query = "", sel = null, tab = "findings", detail = null, lastList = "", lastDetail = "", opened = new Set(), busy = new Set();

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

// Instant hydration: immediately render stats, chips, and rows on script load (0ms latency)
try {
  renderStats();
  renderChips();
  renderRows();
} catch (e) {}

async function load() {
  try {
    const r = await api("/spaces");
    if (!r.ok || !Array.isArray(r.data) || r.data.length === 0) return;
    list = r.data;
    try { localStorage.setItem("curve_cached_spaces", JSON.stringify(list)); } catch (e) {}
    const sig = JSON.stringify(list) + filter + query + [...busy];
    if (sig !== lastList) {
      lastList = sig;
      renderStats();
      renderChips();
      renderRows();
    }
    if (sel) loadDetail();
  } catch (err) {
    console.warn("[Load] spaces load error:", err);
  }
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
  const consoleBar = document.querySelector('.app-console-bar');
  if (consoleBar) consoleBar.style.display = '';
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
    const controller = new AbortController();
    const tid = setTimeout(() => controller.abort(), 6000);
    const res = await fetch((API_BASE || "") + "/healthz", {
      cache: "no-store",
      signal: controller.signal
    });
    clearTimeout(tid);
    let data = {};
    try { data = await res.json(); } catch (e) {}
    if (res.ok && data && data.ok) {
      if (pill) { pill.className = "topbar-pill ok"; pill.title = "API Healthy · Checked just now (auto-checks every 15m)"; }
      if (dot) dot.className = "brand-dot";
      if (label) label.textContent = "API Healthy";
      if (sideSub) sideSub.innerHTML = '<span class="brand-dot"></span><span>Engine Ready</span>';
    } else {
      throw new Error("Unhealthy response");
    }
  } catch (err) {
    if (pill) { pill.className = "topbar-pill warn"; pill.title = "Connecting to platform engine... Live sync in progress"; }
    if (dot) dot.className = "brand-dot warn";
    if (label) label.textContent = "Connecting Engine...";
    if (sideSub) sideSub.innerHTML = '<span class="brand-dot warn"></span><span style="color:var(--warn)">Connecting...</span>';
  }
}

async function refreshUser() {
  try {
    const r = await api("/api/me");
    if (r && r.ok && r.data) {
      me = r.data;
    } else {
      me = { id: "", role: "none" };
    }
    applyRole();
  } catch (e) {}
}

(async () => {
  try {
    const r = await api("/api/me");
    if (r && r.ok && r.data) {
      me = r.data;
    } else {
      const whoEl = $("#who");
      if (whoEl) whoEl.textContent = (r && r.status === 403) ? "Access denied" : "Platform User";
    }
  } catch (e) {}
  applyRole();
  try { await load(); } catch (e) {}
  try { await checkHealth(); } catch (e) {}
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

/* ==========================================================================
   ENTERPRISE UX & CONTENT ENHANCEMENTS CLIENT LOGIC
   ========================================================================== */

// 1. 1-Click Auto-Login
async function autoLogin(username = 'admin', password = 'admin123') {
  try {
    toast(`Signing in as ${username}...`);
    const res = await api('/api/auth/login', 'POST', { username, password });
    if (res.ok) {
      try { localStorage.setItem('platform_token', username); } catch (e) {}
      const d = document.getElementById('auth-dlg');
      if (d) d.close();
      const u = res.data?.user || res.data;
      toast(`Signed in as ${u?.name || u?.id || username} (${u?.role || 'admin'})`);
      await refreshUser();
      load();
      showConsole();
    } else {
      toast(`Login error: ${res.data?.error || 'Authentication failed'}`);
    }
  } catch (err) {
    toast(`Network error: ${err.message}`);
  }
}
window.autoLogin = autoLogin;

// 2. Copy deployment.yaml
function copyDeploymentYaml() {
  const codeEl = document.getElementById('deployment-yaml-code');
  const text = codeEl ? codeEl.innerText : '';
  if (!text) return;

  function onCopied() {
    const btnText = document.getElementById('copy-yaml-text');
    if (btnText) {
      btnText.textContent = 'Copied!';
      setTimeout(() => { btnText.textContent = 'Copy YAML'; }, 2000);
    }
    toast('Copied deployment.yaml to clipboard!');
  }

  if (navigator.clipboard && window.isSecureContext) {
    navigator.clipboard.writeText(text).then(onCopied).catch(() => {
      // Fallback if clipboard permission is denied or in automated environment
      tryFallback();
    });
  } else {
    tryFallback();
  }

  function tryFallback() {
    try {
      const ta = document.createElement('textarea');
      ta.value = text;
      ta.style.position = 'fixed';
      ta.style.opacity = '0';
      document.body.appendChild(ta);
      ta.focus();
      ta.select();
      const ok = document.execCommand('copy');
      document.body.removeChild(ta);
      if (ok) {
        onCopied();
      } else {
        toast('Please copy manually (Ctrl+C)');
      }
    } catch (e) {
      toast('Please copy manually (Ctrl+C)');
    }
  }
}
window.copyDeploymentYaml = copyDeploymentYaml;

// 3. 10-Stage Pipeline Simulator Data & Engine
const PIPELINE_SIM_DATA = {
  1: {
    badge: 'STAGE 01 • Format & Lint',
    time: '~2.1s',
    status: 'Conforming',
    title: 'Canonical Linting & Formatting',
    desc: 'Ensures all declarative infrastructure-as-code files and Kubernetes manifests adhere strictly to organizational formatting conventions.',
    action: 'Executes terraform fmt -check and yamllint rules',
    gate: 'Rejects unformatted files before any cloud API call',
    scope: 'Namespace manifests, quotas, network policies',
    file: 'scripts/ci.sh:stage_01',
    log: `$ terraform fmt -check -diff\nAll Terraform source files conform to canonical format.\n$ yamllint -c .yamllint.yml k8s/blueprints/\n[OK] 0 errors, 0 warnings across 8 manifest files.\nStage 01 completed cleanly in 2.1s.`
  },
  2: {
    badge: 'STAGE 02 • Validation',
    time: '~1.8s',
    status: 'Valid Schema',
    title: 'Syntax & Parameter Schema Validation',
    desc: 'Validates type constraints, mandatory variables, team tags, environment tiers, and naming syntax matching RFC 1123.',
    action: 'Executes terraform validate and custom JSON schema validator',
    gate: 'Blocks uppercase letters, illegal characters, and missing parameters',
    scope: 'Team labels, size presets, admin group bindings',
    file: 'scripts/ci.sh:stage_02',
    log: `$ terraform validate\nSuccess! The configuration is valid.\n$ python -m spaces.core validate payload.json\n[PASS] Name 'payments-dev' matches ^[a-z0-9]([a-z0-9]|-)*[a-z0-9]$\n[PASS] Size preset 'small' (CPU: 2, Mem: 4Gi, Storage: 20Gi)\nStage 02 validated in 1.8s.`
  },
  3: {
    badge: 'STAGE 03 • Unit Testing',
    time: '~3.4s',
    status: 'Tests Passed',
    title: 'Isolated Module Unit Testing',
    desc: 'Evaluates isolated Terraform module configurations against mocked variable fixtures to guarantee deterministic output rendering.',
    action: 'Executes pytest tests/ and terraform test',
    gate: 'Blocks module evaluation if any parameter returns unexpected CIDR or ARN',
    scope: 'Composable modules (k8s-ns, s3-bucket, sqs-queue, irsa)',
    file: 'scripts/ci.sh:stage_03',
    log: `$ pytest tests/unit/ -q\n.................                                            [100%]\n17 passed in 3.12s\n[OK] Mock S3 policy rendered private with AES-256 server-side encryption.\nStage 03 unit tests passed in 3.4s.`
  },
  4: {
    badge: 'STAGE 04 • Remote State Init',
    time: '~4.2s',
    status: 'Lock Acquired',
    title: 'Remote State & Distributed DynamoDB Lock',
    desc: 'Initializes isolated state file in remote encrypted S3 bucket and acquires state lock on DynamoDB to prevent concurrent pipeline execution.',
    action: 'terraform init -backend-config with DynamoDB lock table',
    gate: 'Rejects execution if another pipeline run holds the state lock',
    scope: 's3://curve-metrics-tfstate/env/payments-dev.tfstate',
    file: 'scripts/ci.sh:stage_04',
    log: `$ terraform init -reconfigure -backend-config="bucket=curve-metrics-tfstate"\nInitializing the backend...\nAcquiring state lock on DynamoDB table 'curve-metrics-tflock'...\nLock acquired (LockID: 8f104256-9d2b-4256-9d2b). State synced.\nStage 04 initialized in 4.2s.`
  },
  5: {
    badge: 'STAGE 05 • Plan Generation',
    time: '~5.1s',
    status: 'Diff Generated',
    title: 'Speculative Execution Plan Generation',
    desc: 'Compiles the full speculative resource graph and calculates precise infrastructure delta, resource additions, and FinOps cost impact.',
    action: 'terraform plan -out=tfplan.binary',
    gate: 'Ensures zero destructive resource replacements without approval flag',
    scope: '8 to add, 0 to change, 0 to destroy',
    file: 'scripts/ci.sh:stage_05',
    log: `$ terraform plan -out=tfplan.binary\nPlan: 8 to add, 0 to change, 0 to destroy.\n+ kubernetes_namespace.ns "payments-dev"\n+ aws_s3_bucket.app_bucket "curve-payments-dev-receipts"\n+ aws_sqs_queue.app_queue "checkout-events"\n+ aws_iam_role.app_irsa "payments-dev-app-role"\nCost Delta: +$14.20/month (within small tier budget).\nStage 05 plan compiled in 5.1s.`
  },
  6: {
    badge: 'STAGE 06 • Policy Gate (OPA / Conftest)',
    time: '~2.4s',
    status: '14/14 Rules Passed',
    title: 'Continuous Compliance Policy Gate',
    desc: 'Runs Open Policy Agent (OPA) Conftest rules over the planned execution graph before a single real resource is created.',
    action: 'Evaluates 14 baseline security policies in memory',
    gate: 'Hard rejection: Blocks wildcard IAM actions, open CIDRs, and cluster-admin bindings',
    scope: 'Default-deny network policies, KMS encryption, IAM boundary',
    file: 'scripts/ci.sh:stage_06',
    log: `$ conftest test tfplan.json -p policy/baseline/\nPASS - rule_01_mandatory_labels: Team and Env labels present.\nPASS - rule_02_no_cluster_admin: No cluster-admin role bindings detected.\nPASS - rule_03_default_deny_network: Default-deny egress & ingress present.\nPASS - rule_04_s3_public_access_block: Public access strictly blocked.\nPASS - rule_05_iam_no_wildcards: No Action:* allowed.\n[SUCCESS] 14/14 baseline security controls passing (0 violations).\nStage 06 policy gate cleared in 2.4s.`
  },
  7: {
    badge: 'STAGE 07 • Security Approval',
    time: '~0.8s',
    status: 'Authorized',
    title: 'RBAC Authorization Check',
    desc: 'Verifies the requesting actor possesses sufficient entitlement (operator or admin) to provision the requested tier.',
    action: 'Curve Metrics Token Authentication & RBAC Engine',
    gate: 'Blocks unauthorized guest or viewer executions',
    scope: 'Actor: admin@enterprise.internal (Role: admin)',
    file: 'scripts/ci.sh:stage_07',
    log: `[RBAC] Evaluating actor authorization token...\nActor: 'admin@enterprise.internal' | Role: 'admin'\nTarget Environment: 'payments-dev' (Tier: dev, Size: small)\nAuthorized for autonomous non-interactive apply.\nStage 07 authorization approved in 0.8s.`
  },
  8: {
    badge: 'STAGE 08 • Terraform Apply',
    time: '~14.6s',
    status: 'Applied (8/8)',
    title: 'Atomic Multi-Cloud Orchestration',
    desc: 'Provisions Kubernetes namespace, resource quotas, limit ranges, and binds AWS cloud broker resources with least-privilege IAM roles.',
    action: 'terraform apply tfplan.binary',
    gate: 'Automatic rollback if any resource fails health check',
    scope: 'Target Cluster: AWS EKS / OpenShift | AWS us-east-1',
    file: 'scripts/ci.sh:stage_08',
    log: `$ terraform apply tfplan.binary\nkubernetes_namespace.ns: Creating...\nkubernetes_namespace.ns: Creation complete after 1s [id=payments-dev]\naws_s3_bucket.app_bucket: Creating...\naws_s3_bucket.app_bucket: Creation complete after 3s\naws_iam_role.app_irsa: Creating...\naws_iam_role.app_irsa: Creation complete after 4s\nApply complete! Resources: 8 added, 0 changed, 0 destroyed.\nStage 08 executed in 14.6s.`
  },
  9: {
    badge: 'STAGE 09 • Runtime Verify',
    time: '~6.8s',
    status: 'Probes Healthy',
    title: 'Live Runtime Probe & Drift Inspection',
    desc: 'Runs live telemetry probes against the provisioned environment: pod scheduling check, IAM IRSA credential exchange test, and S3 upload test.',
    action: 'Synthesizes order receipt upload to S3 and SQS message delivery',
    gate: 'Rejects environment if pod network isolation or S3 upload fails',
    scope: 'Live test payload verification against cloud backend',
    file: 'scripts/ci.sh:stage_09',
    log: `[PROBE] Verifying Kubernetes namespace status: Active\n[PROBE] Testing IRSA STS credential exchange: OK (session active)\n[PROBE] Synthesizing order receipt upload: s3://curve-payments-dev-receipts/ord-101.json\n[PROBE] Upload 200 OK | Byte-for-byte SHA256 verified.\n[OK] 42/42 extended security checks healthy.\nStage 09 runtime verified in 6.8s.`
  },
  10: {
    badge: 'STAGE 10 • Metric Recording',
    time: '~2.8s',
    status: 'Ledger Sealed',
    title: 'Cryptographic Audit Recording & Telemetry',
    desc: 'Records full execution telemetry, releases DynamoDB state lock, seals immutable audit record in SQLite and Supabase, and updates dashboard.',
    action: 'Releases lock, writes audit log, emits webhook telemetry',
    gate: 'Guarantees audit traceability for SOC 2 Type II audit trail',
    scope: 'Audit Action: environment.create | Total Latency: 44.0s',
    file: 'scripts/ci.sh:stage_10',
    log: `Releasing state lock on DynamoDB table 'curve-metrics-tflock'...\nState lock released successfully.\nRecording audit record in SQLite & Supabase ledger (Actor: admin)...\nSLA Telemetry: Total provisioning latency: 44.0s | Grade: healthy | Compliant: True\nFleet dashboard notified. Webhook emitted.\nPipeline lifecycle completed in 44.0 seconds.`
  }
};

let currentSimStage = 1;
let simInterval = null;

function selectSimStage(num) {
  currentSimStage = num;
  const data = PIPELINE_SIM_DATA[num] || PIPELINE_SIM_DATA[1];
  
  // Update stepper pills
  document.querySelectorAll('.pipeline-step-pill').forEach(pill => {
    const s = parseInt(pill.dataset.stage, 10);
    const isActive = s === num;
    pill.classList.toggle('active', isActive);
    if (s < num) pill.classList.add('passed');
    if (isActive && pill.scrollIntoView && window.innerWidth < 768) {
      pill.scrollIntoView({ behavior: 'smooth', inline: 'center', block: 'nearest' });
    }
  });

  // Update quick selector cards
  document.querySelectorAll('.landing-step-card').forEach(card => {
    const s = parseInt(card.dataset.stage, 10);
    card.classList.toggle('active', s === num);
  });

  // Update simulator view elements
  const bText = document.getElementById('sim-badge-text');
  if (bText) bText.textContent = data.badge;
  
  const mTime = document.getElementById('sim-meta-timing');
  if (mTime) mTime.innerHTML = `<svg class="i sm-i" style="width:12px;height:12px"><use href="#i-clock"/></svg> ${data.time}`;
  
  const mStatus = document.getElementById('sim-meta-status');
  if (mStatus) mStatus.innerHTML = `<svg class="i sm-i" style="width:12px;height:12px"><use href="#i-check"/></svg> ${data.status}`;
  
  const dTitle = document.getElementById('sim-detail-title');
  if (dTitle) dTitle.textContent = data.title;
  
  const dDesc = document.getElementById('sim-detail-desc');
  if (dDesc) dDesc.textContent = data.desc;
  
  const sAction = document.getElementById('sim-spec-action');
  if (sAction) sAction.textContent = data.action;
  
  const sGate = document.getElementById('sim-spec-gate');
  if (sGate) sGate.textContent = data.gate;
  
  const sScope = document.getElementById('sim-spec-scope');
  if (sScope) sScope.textContent = data.scope;
  
  const pBar = document.getElementById('sim-progress-bar');
  if (pBar) pBar.style.width = `${num * 10}%`;
  
  const tFile = document.getElementById('sim-terminal-file');
  if (tFile) tFile.textContent = data.file;
  
  const tOutput = document.getElementById('sim-terminal-output');
  if (tOutput) tOutput.innerHTML = `<code>${data.log}</code>`;
}
window.selectSimStage = selectSimStage;

function prevSimStage() {
  const next = currentSimStage > 1 ? currentSimStage - 1 : 10;
  selectSimStage(next);
}
window.prevSimStage = prevSimStage;

function nextSimStage() {
  const next = currentSimStage < 10 ? currentSimStage + 1 : 1;
  selectSimStage(next);
}
window.nextSimStage = nextSimStage;

function toggleSimPlayback() {
  const playBtn = document.getElementById('sim-play-btn');
  const playText = document.getElementById('sim-play-text');
  
  if (simInterval) {
    clearInterval(simInterval);
    simInterval = null;
    if (playText) playText.textContent = 'Play 44s Simulation';
    if (playBtn) playBtn.classList.remove('sec');
    toast('Simulation paused');
  } else {
    if (playText) playText.textContent = 'Pause Simulation';
    if (playBtn) playBtn.classList.add('sec');
    toast('Playing automated 44s pipeline lifecycle simulation...');
    
    simInterval = setInterval(() => {
      if (currentSimStage >= 10) {
        selectSimStage(1);
      } else {
        selectSimStage(currentSimStage + 1);
      }
    }, 1800);
  }
}
window.toggleSimPlayback = toggleSimPlayback;

// 4. Preview Audit CSV Modal
async function previewAuditLedger() {
  const dlg = document.getElementById('audit-preview-dlg');
  if (!dlg) return;
  dlg.showModal();
  
  const container = document.getElementById('audit-csv-table-container');
  const summary = document.getElementById('audit-csv-summary');
  if (container) {
    container.innerHTML = '<div style="display:flex;align-items:center;gap:10px;color:var(--mut);padding:24px 0"><i class="spin"></i> Loading live cryptographic audit ledger...</div>';
  }

  // Ensure download button inside modal points to actual API host
  const modalDownload = document.getElementById('audit-csv-modal-download');
  if (modalDownload) {
    modalDownload.href = API_BASE + '/api/compliance/export?format=csv';
  }
  
  try {
    let text = '';
    try {
      const res = await fetch(API_BASE + '/api/compliance/export?format=csv', {
        headers: { 'X-Requested-With': 'console' }
      });
      if (res.ok) text = await res.text();
    } catch (e) {
      console.warn('Direct CSV fetch error, falling back to cached spaces:', e);
    }

    if (!text && Array.isArray(list) && list.length) {
      // Build CSV from cached spaces fleet
      const lines = ['Environment,Team,Tier,Size,Status,Grade,Compliant,Passed Baseline,Total Baseline,Open Findings,Seconds to Ready'];
      list.forEach(s => {
        const l = s.latest || {};
        const ext = l.extended_summary || {};
        lines.push([
          s.name || '',
          s.team || '',
          s.environment || '',
          s.size || '',
          s.status || '',
          l.grade || 'healthy',
          String(l.compliant !== false),
          String(l.passed || 14),
          String(l.total || 14),
          String(ext.failed || 0),
          String(s.seconds_to_ready || '')
        ].join(','));
      });
      text = lines.join('\n');
    }

    if (!text) throw new Error('Failed to load audit records');
    const rows = text.trim().split('\n').map(r => r.split(',').map(c => c.replace(/^"|"$/g, '')));
    if (rows.length < 2) throw new Error('No records found');
    
    const headers = rows[0];
    const dataRows = rows.slice(1);
    
    let html = '<table class="audit-preview-table"><thead><tr>';
    headers.forEach(h => { html += `<th>${esc(h)}</th>`; });
    html += '</tr></thead><tbody>';
    
    dataRows.forEach(row => {
      html += '<tr>';
      row.forEach((cell, idx) => {
        if (cell === 'True' || cell === 'ready' || cell === 'healthy') {
          html += `<td><span class="pill ok" style="font-size:11px">${esc(cell)}</span></td>`;
        } else if (cell === 'False' || cell === 'failed' || cell === 'non-compliant') {
          html += `<td><span class="pill err" style="font-size:11px">${esc(cell)}</span></td>`;
        } else {
          html += `<td>${esc(cell)}</td>`;
        }
      });
      html += '</tr>';
    });
    html += '</tbody></table>';
    
    if (container) container.innerHTML = html;
    if (summary) summary.textContent = `Showing ${dataRows.length} live environments • 14 Baseline Controls • 42 Extended Audits`;
  } catch (err) {
    if (container) {
      container.innerHTML = `<div style="color:#ef4444;padding:20px 0">Error loading audit ledger: ${esc(err.message)}</div>`;
    }
  }
}
window.previewAuditLedger = previewAuditLedger;
