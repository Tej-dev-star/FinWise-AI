// FinWise AI frontend connected to the Flask API.
// API URL can be changed here if the backend runs on another host/port.
const API_BASE = "http://127.0.0.1:5000/api";
const TOKEN_KEY = "finwise_access_token";
let currentUser = null;
let transactions = [];
let loans = [];
let bankConnections = [];
let toastTimer;

const $ = (id) => document.getElementById(id);
const inr = (value) => new Intl.NumberFormat("en-IN", {
  style: "currency", currency: "INR", maximumFractionDigits: 0
}).format(Number(value || 0));
const safe = (value) => String(value ?? "").replace(/[&<>"']/g, ch => ({
  "&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;"
}[ch]));

function showToast(message) {
  const el = $("toast");
  if (!el) return;
  el.textContent = message;
  el.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove("show"), 3000);
}
function token() { return localStorage.getItem(TOKEN_KEY); }

async function api(path, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (options.body && !headers["Content-Type"]) headers["Content-Type"] = "application/json";
  if (token()) headers.Authorization = `Bearer ${token()}`;
  let response;
  try {
    response = await fetch(`${API_BASE}${path}`, { ...options, headers });
  } catch (e) {
    throw new Error("Cannot reach the backend. Make sure Flask is running at http://127.0.0.1:5000.");
  }
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    if (response.status === 401 && token()) {
      localStorage.removeItem(TOKEN_KEY);
      currentUser = null;
    }
    throw new Error(data.error || data.message || `Request failed (${response.status}).`);
  }
  return data;
}

function installAuthStyles() {
  const style = document.createElement("style");
  style.textContent = `
    .auth-overlay{position:fixed;inset:0;background:rgba(9,20,39,.72);z-index:100;display:grid;place-items:center;padding:18px}
    .auth-card{width:min(430px,100%);background:#fff;border-radius:18px;padding:26px;box-shadow:0 25px 90px #0003}
    .auth-card h2{margin:0 0 7px;font-size:23px;color:#14213a}.auth-card p{color:#75829a;line-height:1.5}
    .auth-card label{display:grid;gap:6px;margin:13px 0;font-size:12px;color:#44536c;font-weight:600}
    .auth-card input{width:100%;padding:12px;border:1px solid #dfe5ef;border-radius:9px;box-sizing:border-box}
    .auth-actions{display:flex;gap:9px;margin-top:18px}.auth-actions button{flex:1}
    .secondary-btn{border:1px solid #dfe5ef;border-radius:9px;background:white;padding:11px;color:#34425a;font-weight:600}
    .auth-error{color:#c92e43!important;min-height:18px;font-size:12px}
    .inline-tools{display:flex;gap:8px;flex-wrap:wrap;margin:0 0 12px}
    .inline-tools button{border:1px solid #dfe5ef;border-radius:8px;background:#fff;color:#34425a;padding:8px 10px;font-size:11px;font-weight:600}
    .empty-state{padding:20px;text-align:center;color:#75829a;font-size:12px}
    .form-modal{position:fixed;inset:0;background:#0b1937a8;z-index:90;display:grid;place-items:center;padding:18px}
    .form-modal>div{background:#fff;border-radius:14px;padding:22px;width:min(420px,100%)}
    .form-modal label{display:grid;gap:6px;margin:10px 0;font-size:12px}.form-modal input,.form-modal select{padding:10px;border:1px solid #dfe5ef;border-radius:8px}
    .form-modal .modal-actions{display:flex;gap:8px;margin-top:14px}
  `;
  document.head.appendChild(style);
}

function showAuth() {
  if ($("authOverlay")) $("authOverlay").remove();
  const overlay = document.createElement("div");
  overlay.id = "authOverlay";
  overlay.className = "auth-overlay";
  overlay.innerHTML = `
    <section class="auth-card" aria-labelledby="authTitle">
      <div class="brand-mark" style="font-size:27px">◢</div>
      <h2 id="authTitle">FinWise AI</h2>
      <p id="authDescription">Sign in to load your own saved transactions and loans.</p>
      <form id="authForm">
        <label id="nameField">Name<input id="authName" autocomplete="name" placeholder="Your name" /></label>
        <label>Email<input id="authEmail" type="email" required autocomplete="email" placeholder="you@example.com" /></label>
        <label>Password<input id="authPassword" type="password" required minlength="10" autocomplete="current-password" placeholder="At least 10 characters" /></label>
        <p class="auth-error" id="authError" role="alert"></p>
        <div class="auth-actions"><button class="primary-btn" type="submit" id="authSubmit">Sign in</button><button class="secondary-btn" type="button" id="authToggle">Create account</button></div>
      </form>
      <p style="font-size:11px;margin-bottom:0">Demo bank connection uses synthetic data only. Never enter bank credentials here.</p>
    </section>`;
  document.body.appendChild(overlay);
  let mode = "login";
  const syncMode = () => {
    $("authTitle").textContent = mode === "login" ? "Welcome back" : "Create your FinWise account";
    $("authDescription").textContent = mode === "login" ? "Sign in to load your saved financial data." : "Create an account to start saving your transactions.";
    $("nameField").style.display = mode === "register" ? "grid" : "none";
    $("authName").required = mode === "register";
    $("authPassword").autocomplete = mode === "login" ? "current-password" : "new-password";
    $("authSubmit").textContent = mode === "login" ? "Sign in" : "Create account";
    $("authToggle").textContent = mode === "login" ? "Create account" : "I have an account";
  };
  $("authToggle").addEventListener("click", () => { mode = mode === "login" ? "register" : "login"; $("authError").textContent = ""; syncMode(); });
  syncMode();
  $("authForm").addEventListener("submit", async e => {
    e.preventDefault();
    $("authError").textContent = "";
    $("authSubmit").disabled = true;
    try {
      const body = { email: $("authEmail").value.trim(), password: $("authPassword").value };
      let data;
      if (mode === "register") {
        body.name = $("authName").value.trim();
        data = await api("/auth/register", { method:"POST", body:JSON.stringify(body) });
      } else {
        data = await api("/auth/login", { method:"POST", body:JSON.stringify(body) });
      }
      localStorage.setItem(TOKEN_KEY, data.access_token);
      currentUser = data.user;
      overlay.remove();
      await loadAppData();
      showToast(mode === "register" ? "Account created." : "Signed in.");
    } catch (err) {
      $("authError").textContent = err.message;
    } finally {
      $("authSubmit").disabled = false;
    }
  });
}

function setUserUI(user) {
  currentUser = user;
  $("profileBtn").innerHTML = `${safe(user.name)} <span>⌄</span>`;
  $("userAvatar").textContent = (user.name || "?").trim().charAt(0).toUpperCase();
  $("pageHeading").innerHTML = `Welcome back, ${safe(user.name)}! <span class="wave">👋</span>`;
}
function formatDate(date) {
  const d = new Date(`${date}T00:00:00`);
  return Number.isNaN(d.getTime()) ? safe(date) : d.toLocaleDateString("en-IN", { day:"2-digit", month:"short", year:"numeric" });
}
function sum(items, predicate) {
  return items.reduce((total, item) => total + (predicate(item) ? Number(item.amount || 0) : 0), 0);
}
function transactionDate(value) {
  if (!value) return null;
  const d = new Date(`${String(value).slice(0, 10)}T00:00:00`);
  return Number.isNaN(d.getTime()) ? null : d;
}
function monthKey(date) { return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}`; }
function renderTrendChart() {
  const now = new Date();
  const months = [];
  for (let offset = 5; offset >= 0; offset--) {
    const d = new Date(now.getFullYear(), now.getMonth() - offset, 1);
    months.push({ key: monthKey(d), label: d.toLocaleDateString("en-IN", { month: "short" }), income: 0, expenses: 0 });
  }
  const byMonth = new Map(months.map(m => [m.key, m]));
  transactions.forEach(t => {
    const date = transactionDate(t.date);
    if (!date) return;
    const month = byMonth.get(monthKey(date));
    if (!month) return;
    if (t.kind === "income") month.income += Number(t.amount || 0);
    else if (t.kind === "expense") month.expenses += Number(t.amount || 0);
  });
  const maxValue = Math.max(1, ...months.flatMap(m => [m.income, m.expenses]));
  const axis = $("chartYAxis");
  const bars = $("chartBars");
  if (!axis || !bars) return;
  axis.innerHTML = [1, .75, .5, .25, 0].map(f => `<span>${inr(maxValue * f)}</span>`).join("");
  bars.innerHTML = months.map(m => {
    const incomeHeight = m.income ? Math.max(2, m.income / maxValue * 100) : 0;
    const expenseHeight = m.expenses ? Math.max(2, m.expenses / maxValue * 100) : 0;
    return `<div class="bar-group"><div class="bars"><b class="bar income" style="height:${incomeHeight}%" title="${m.label} income: ${inr(m.income)}"></b><b class="bar expense" style="height:${expenseHeight}%" title="${m.label} expenses: ${inr(m.expenses)}"></b></div><span>${m.label}</span></div>`;
  }).join("");
}
function renderExpenseBreakdown() {
  const totals = new Map();
  transactions.filter(t => t.kind === "expense").forEach(t => {
    const category = String(t.category || "Other");
    totals.set(category, (totals.get(category) || 0) + Number(t.amount || 0));
  });
  const entries = [...totals.entries()].sort((a, b) => b[1] - a[1]);
  const total = entries.reduce((n, [, amount]) => n + amount, 0);
  $("expenseTotal").textContent = inr(total);
  const colors = ["#3976f6", "#83a5ff", "#ff6470", "#ffb449", "#a48af6", "#91a3c6", "#16b981", "#d28b5c"];
  if (!entries.length || total <= 0) {
    $("expenseDonut").style.background = "conic-gradient(#e9eef5 0 100%)";
    $("expenseCategories").innerHTML = `<div class="empty-state">No saved expenses yet.</div>`;
    return;
  }
  let cursor = 0;
  const segments = entries.map(([, amount], i) => {
    const start = cursor;
    cursor += amount / total * 100;
    return `${colors[i % colors.length]} ${start}% ${cursor}%`;
  });
  $("expenseDonut").style.background = `conic-gradient(${segments.join(",")})`;
  $("expenseCategories").innerHTML = entries.map(([category, amount], i) =>
    `<div><i class="cat" style="background:${colors[i % colors.length]}"></i><span>${safe(category)}</span><b>${Math.round(amount / total * 100)}%</b></div>`
  ).join("");
}
function renderCashflow(dashboard) {
  const income = sum(transactions, t => t.kind === "income");
  const expenses = sum(transactions, t => t.kind === "expense");
  const emis = loans.reduce((n, loan) => n + Number(loan.monthly_emi || 0), 0);
  const rows = [
    ["Total income (all saved)", income],
    ["Total expenses (all saved)", expenses],
    ["Net transaction flow", income - expenses],
    ["Monthly loan EMIs", emis]
  ];
  $("cashflowLines").innerHTML = rows.map(([label, value], i) =>
    `<div class="${i === 2 ? "available" : ""}"><span>${label}</span><b>${inr(value)}</b></div>`
  ).join("");
}
function renderHealthSnapshot() {
  const incomeCount = transactions.filter(t => t.kind === "income").length;
  const expenseCount = transactions.filter(t => t.kind === "expense").length;
  const loanCount = loans.length;
  $("healthChecks").innerHTML = [
    `Income transactions recorded: ${incomeCount}`,
    `Expense transactions recorded: ${expenseCount}`,
    `Saved loans: ${loanCount}`,
    "A reliable score needs consistent monthly history and a defined scoring model."
  ].map((line, i) => `<p><span class="${i === 3 ? "warning" : "check"}">${i === 3 ? "!" : "✓"}</span>${line}</p>`).join("");
}
function renderMetrics(dashboard) {
  const cards = document.querySelectorAll(".metric-card");
  const income = Number(dashboard.monthly_income || 0);
  const expenses = Number(dashboard.monthly_expenses || 0);
  const emis = Number(dashboard.estimated_monthly_emis || 0);
  // Transaction totals cover all saved dates, so do not subtract a monthly EMI from them.
  const netTransactions = income - expenses;
  const values = [income, expenses, netTransactions, emis];
  cards.forEach((card, i) => {
    const strong = card.querySelector("strong");
    if (strong) strong.textContent = inr(values[i]);
  });
  const labels = document.querySelectorAll(".metric-copy > span");
  if (labels[0]) labels[0].textContent = "Total Income";
  if (labels[1]) labels[1].textContent = "Total Expenses";
  if (labels[2]) labels[2].textContent = "Net Transaction Flow";
  if (labels[3]) labels[3].textContent = "Monthly Loan EMIs";
  const smalls = document.querySelectorAll(".metric-copy small");
  if (smalls[0]) smalls[0].textContent = `${dashboard.transaction_count || 0} saved transactions`;
  if (smalls[1]) smalls[1].textContent = "Across all saved dates";
  if (smalls[2]) smalls[2].textContent = netTransactions >= 0 ? "Income exceeds expenses" : "Expenses exceed income";
  if (smalls[3]) smalls[3].textContent = `${dashboard.active_loan_count || 0} saved loans`;
  $("pageSubtitle").textContent = "Overview calculated from your saved FinWise data. Transaction totals include all saved dates.";
  renderTrendChart();
  renderExpenseBreakdown();
  renderCashflow(dashboard);
  renderHealthSnapshot();
}

function renderTransactions() {
  const tbody = $("transactionsTable").querySelector("tbody");
  if (!transactions.length) {
    tbody.innerHTML = `<tr><td colspan="4"><div class="empty-state">No transactions yet. Add one or sync the demo bank.</div></td></tr>`;
    return;
  }
  tbody.innerHTML = transactions.slice(0, 8).map(t => {
    const income = t.kind === "income";
    const icon = income ? "green" : "red";
    const sign = income ? "+" : "−";
    return `<tr data-transaction-id="${t.id}">
      <td>${formatDate(t.date)}</td>
      <td><span class="transaction-icon ${icon}">${income ? "↗" : "↘"}</span>${safe(t.description)}</td>
      <td><span class="category-pill"><i class="cat c2"></i>${safe(t.category)}</span></td>
      <td class="amount ${income ? "positive-text" : "negative-text"}">${sign}${inr(t.amount)}</td>
    </tr>`;
  }).join("");
}
function renderLoans() {
  const panel = document.querySelector(".loans-panel");
  const rows = loans.map(loan => {
    const principal = Number(loan.principal || 0);
    const emi = Number(loan.monthly_emi || 0);
    return `<div class="loan-row">
      <div class="loan-icon blue">▣</div><div class="loan-info">
      <div class="loan-title"><strong>${safe(loan.name)}</strong><b>${inr(loan.outstanding_balance || principal)}</b></div>
      <div class="loan-meta">${safe(loan.lender || "Lender not specified")} • ${safe(loan.annual_interest_rate)}% p.a. <span>${inr(emi)} / month</span></div>
      <div class="progress"><i style="width:0%"></i></div>
      <div class="loan-meta small"><span>${safe(loan.tenure_months)} month tenure</span><span>Balance is an estimate</span></div>
      </div></div>`;
  }).join("");
  const container = panel.querySelectorAll(".loan-row");
  container.forEach(row => row.remove());
  const heading = panel.querySelector(".panel-heading");
  heading.insertAdjacentHTML("afterend", rows || `<div class="empty-state">No loans added yet.</div>`);
}
async function loadAppData() {
  const [me, dash, txn, loanData, banks] = await Promise.all([
    api("/me"), api("/dashboard"), api("/transactions"), api("/loans"), api("/bank/connections")
  ]);
  setUserUI(me.user);
  transactions = txn.transactions || [];
  loans = loanData.loans || [];
  bankConnections = banks.connections || [];
  renderMetrics(dash);
  renderTransactions();
  renderLoans();
  renderBankButton();
  $("appFooter").textContent = "FinWise AI · Data loaded from your account. Bank connection is simulated and uses synthetic transactions.";
}
function renderBankButton() {
  const active = bankConnections.find(c => c.status === "active");
  $("bankConnectBtn").textContent = active ? "↻ Sync demo bank" : "＋ Connect demo bank";
  $("bankConnectBtn").title = active ? "Sync synthetic demo transactions" : "Create a simulated bank connection";
}
async function connectOrSyncBank() {
  try {
    let active = bankConnections.find(c => c.status === "active");
    if (!active) {
      const result = await api("/bank/demo/connect", { method:"POST" });
      active = result.connection;
      showToast(result.message || "Demo connection created.");
    }
    const sync = await api(`/bank/connections/${active.id}/sync`, { method:"POST" });
    showToast(`Demo sync complete: ${sync.imported_count} new, ${sync.skipped_duplicate_count} duplicates skipped.`);
    await loadAppData();
  } catch (err) { showToast(err.message); }
}
function openModal(title, fields, onSubmit) {
  const old = $("dataModal"); if (old) old.remove();
  const modal = document.createElement("div");
  modal.id = "dataModal"; modal.className = "form-modal";
  modal.innerHTML = `<div><h2>${safe(title)}</h2><form id="dataModalForm">${fields}<p class="auth-error" id="dataModalError"></p><div class="modal-actions"><button class="primary-btn" type="submit">Save</button><button class="secondary-btn" type="button" id="modalCancel">Cancel</button></div></form></div>`;
  document.body.appendChild(modal);
  $("modalCancel").onclick = () => modal.remove();
  $("dataModalForm").onsubmit = async e => {
    e.preventDefault();
    try { await onSubmit(modal); modal.remove(); await loadAppData(); showToast("Saved successfully."); }
    catch (err) { $("dataModalError").textContent = err.message; }
  };
}
function addTransactionDialog() {
  const today = new Date().toISOString().slice(0,10);
  openModal("Add transaction", `
    <label>Description<input name="description" required maxlength="180"></label>
    <label>Amount (₹)<input name="amount" type="number" min="0.01" step="0.01" required></label>
    <label>Date<input name="date" type="date" value="${today}" required></label>
    <label>Type<select name="kind"><option value="expense">Expense</option><option value="income">Income</option></select></label>
    <label>Category<select name="category"><option>Food & Dining</option><option>Groceries</option><option>Housing</option><option>Transport</option><option>Utilities</option><option>Shopping</option><option>Income</option><option>Education</option><option>Other</option></select></label>`,
    async modal => {
      const f = new FormData(modal.querySelector("form"));
      await api("/transactions", {method:"POST", body:JSON.stringify(Object.fromEntries(f.entries()))});
    });
}
function addLoanDialog() {
  openModal("Add loan", `
    <label>Loan name<input name="name" required maxlength="100" placeholder="Education loan"></label>
    <label>Lender<input name="lender" maxlength="100" placeholder="Bank or lender"></label>
    <label>Principal (₹)<input name="principal" type="number" min="0.01" step="0.01" required></label>
    <label>Annual interest rate (%)<input name="annual_interest_rate" type="number" min="0" max="100" step="0.1" value="12" required></label>
    <label>Tenure (months)<input name="tenure_months" type="number" min="1" max="600" value="12" required></label>`,
    async modal => {
      const f = new FormData(modal.querySelector("form"));
      await api("/loans", {method:"POST", body:JSON.stringify(Object.fromEntries(f.entries()))});
    });
}
function wirePageControls() {
  document.querySelectorAll("[data-page]").forEach(button => button.addEventListener("click", () => {
    const page = button.dataset.page;
    document.querySelectorAll(".nav-item").forEach(item => item.classList.toggle("active", item.dataset.page === page));
    $("pageHeading").textContent = page === "Dashboard" ? `Welcome back, ${currentUser?.name || "there"}!` : page;
    $("pageSubtitle").textContent = page === "Dashboard" ? "Overview calculated from your saved FinWise data." : `${page} — account data is loaded where supported.`;
    $("sidebar").classList.remove("open");
    if (page === "Transactions") showToast("Use Add transaction to record a transaction.");
    if (page === "Loans & Leases") showToast("Use Add loan to record a loan.");
    if (page === "Loan Simulator") $("loanAmount").focus();
    if (page === "AI Assistant") $("assistantQuestion").focus();
  }));
  $("mobileMenu").addEventListener("click", () => $("sidebar").classList.toggle("open"));
  $("monthSelect").addEventListener("change", () => showToast("Current backend totals cover all saved transactions; date filtering is not implemented yet."));
  $("notificationBtn").addEventListener("click", () => showToast("No notifications are configured yet."));
  $("profileBtn").addEventListener("click", () => {
    if (!currentUser) return showAuth();
    if (confirm("Sign out of FinWise AI?")) {
      localStorage.removeItem(TOKEN_KEY); currentUser = null; transactions = []; loans = [];
      $("profileBtn").textContent = "Sign in"; $("userAvatar").textContent = "?"; showAuth();
    }
  });
  $("upgradeBtn").addEventListener("click", () => showToast("Pro features are not enabled."));
  $("bankConnectBtn").addEventListener("click", connectOrSyncBank);
  $("globalSearch").addEventListener("input", e => {
    const query = e.target.value.trim().toLowerCase();
    document.querySelectorAll("#transactionsTable tbody tr").forEach(row => row.style.display = row.textContent.toLowerCase().includes(query) ? "" : "none");
  });
  const txHeading = document.querySelector(".transactions-panel .panel-heading");
  txHeading.insertAdjacentHTML("beforeend", '<button class="text-link" id="addTransactionBtn">＋ Add</button>');
  $("addTransactionBtn").addEventListener("click", addTransactionDialog);
  const loanHeading = document.querySelector(".loans-panel .panel-heading");
  loanHeading.insertAdjacentHTML("beforeend", '<button class="text-link" id="addLoanBtn">＋ Add loan</button>');
  $("addLoanBtn").addEventListener("click", addLoanDialog);

  $("loanForm").addEventListener("submit", async e => {
    e.preventDefault();
    const result = $("simulatorResult");
    result.hidden = false; result.textContent = "Calculating…";
    try {
      const data = await api("/simulator", {method:"POST", body:JSON.stringify({
        principal: Number($("loanAmount").value),
        annual_interest_rate: Number($("interestRate").value),
        tenure_months: Number($("loanTenure").value)
      })});
      const income = sum(transactions, t => t.kind === "income");
      const expenses = sum(transactions, t => t.kind === "expense");
      const emis = loans.reduce((n, loan) => n + Number(loan.monthly_emi || 0), 0);
      const remaining = income - expenses - emis - data.monthly_emi;
      result.innerHTML = `<div>Estimated monthly EMI</div><strong>${inr(data.monthly_emi)}</strong>
        <div>Total repayment: <b>${inr(data.total_repayment)}</b><br>Estimated interest: <b>${inr(data.total_interest)}</b></div>
        <div style="margin-top:7px">${safe(data.disclaimer)}</div>
        <div class="${remaining < 5000 ? "result-warning" : ""}" style="margin-top:7px">${transactions.length ? `Balance after saved totals and this EMI: ${inr(remaining)} (rough estimate; totals are not month-filtered).` : "Add transactions to estimate affordability using your own records."}</div>`;
    } catch (err) { result.textContent = err.message; }
  });
  $("assistantForm").addEventListener("submit", e => {
    e.preventDefault();
    const q = $("assistantQuestion").value.trim();
    if (!q) return;
    $("assistantReply").hidden = false;
    $("assistantReply").textContent = "The AI assistant is not connected to an AI model yet. I can currently show your saved totals on the dashboard and calculate loan EMI through the backend.";
    $("assistantQuestion").value = "";
  });
  document.querySelectorAll("[data-question]").forEach(btn => btn.addEventListener("click", () => {
    $("assistantQuestion").value = btn.dataset.question;
    $("assistantForm").requestSubmit();
  }));
}
async function boot() {
  installAuthStyles();
  wirePageControls();
  try {
    const health = await fetch(`${API_BASE}/health`);
    if (!health.ok) throw new Error("Backend health check failed.");
  } catch {
    showToast("Backend unavailable. Start Flask, then reload this page.");
    showAuth();
    return;
  }
  if (!token()) { showAuth(); return; }
  try {
    const me = await api("/me");
    await loadAppData();
  } catch (err) {
    localStorage.removeItem(TOKEN_KEY);
    showAuth();
    showToast(err.message);
  }
}
boot();
