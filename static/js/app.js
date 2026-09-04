/*
  app.js
  ------
  Plain vanilla JS, no framework. Jobs:
    1. Fetch data from the Flask API and render it
    2. Split invoices into 4 sections (Awaiting Due Date, Active Recovery,
       Needs Human Attention, Recovered)
    3. Let the user sort each section (dropdown + asc/desc toggle)
    4. Handle button clicks (force step / mark as paid)
    5. Show generated messages in a modal popup
    6. Let you click a "Needs Human Attention" company to see its FULL
       history (every message/action ever taken on that invoice)

  AUTOMATION NOTE: the background loop on the server does the actual work
  on its own. This frontend just polls every few seconds so you can watch
  it happen live without touching anything. The "Force Step Now" button
  only exists to speed things up during a live demo.
*/

const ACTION_LABELS = {
  nudge: "Friendly Nudge",
  reminder: "Firm Reminder",
  formal_notice: "Formal Notice",
  human_handoff: "Human Handoff",
  promise_broken_detected: "Promise Broken (auto-detected)",
  payment_received: "Payment Received",
};

const CHANNEL_LABELS = { whatsapp: "WhatsApp", email: "Email", sms: "SMS" };

let currentSort = { field: "days_overdue", direction: "desc" };
let allInvoices = [];

async function fetchJSON(url, options) {
  const res = await fetch(url, options);
  return res.json();
}

function formatMoney(n) {
  return "₹" + n.toLocaleString("en-IN");
}

// ---------------------------------------------------------------------
// SECURITY: escapeHtml()
// Any text that came from a USER (company name, description, contact,
// generated messages) must pass through this before going into innerHTML.
// Without it, someone could type something like <script>...</script> as
// a "company name" and the browser would actually RUN it instead of just
// displaying it as text - that's called an XSS (Cross-Site Scripting)
// vulnerability. This function converts dangerous characters (< > & " ')
// into their harmless "display only" versions, e.g. "<" becomes "&lt;",
// which the browser shows as the character < but never executes as code.
// ---------------------------------------------------------------------
function escapeHtml(str) {
  if (str === null || str === undefined) return "";
  const div = document.createElement("div");
  div.textContent = String(str);
  return div.innerHTML;
}

async function loadSummary() {
  const data = await fetchJSON("/api/summary");
  document.getElementById("stat-total").textContent = formatMoney(data.total_amount);
  document.getElementById("stat-at-risk").textContent = formatMoney(data.at_risk_amount);
  document.getElementById("stat-recovered").textContent = formatMoney(data.recovered_amount);
  document.getElementById("stat-handoff").textContent = data.human_handoff_count;
}

// ---------------------------------------------------------------------
// Sorting: default is "most urgent first" - highest days overdue, then
// highest amount. That order matches our purpose - the most overdue
// invoices lose recovery probability every day, so they're the ones
// worth surfacing first. The dropdown lets the user override this.
// ---------------------------------------------------------------------
function sortInvoices(invoices, field, direction) {
  const sorted = [...invoices].sort((a, b) => {
    let diff = (a[field] ?? 0) - (b[field] ?? 0);
    return direction === "desc" ? -diff : diff;
  });
  return sorted;
}

function invoiceCardHTML(inv) {
  const isPaid = inv.status === "paid";
  const badgeClass = isPaid ? "paid" : inv.risk_tier;
  const badgeText = isPaid ? "PAID" : inv.risk_tier + " RISK";
  const canRecover = !isPaid && inv.status === "broken" && inv.escalation_stage < 4;
  const canPay = !isPaid;

  return `
    <div class="invoice-card" data-id="${inv.id}">
      <div class="invoice-card-top">
        <div>
          <div class="invoice-customer">${escapeHtml(inv.customer_name)}</div>
          <div class="muted" style="font-size:12px;">${escapeHtml(inv.customer_industry)} · ${escapeHtml(inv.invoice_no)}</div>
        </div>
        <div style="text-align:right;">
          <div class="invoice-amount">${formatMoney(inv.amount)}</div>
          <span class="badge ${badgeClass}">${badgeText}</span>
        </div>
      </div>

      <div class="muted" style="font-size:13px; margin-bottom:8px;">${escapeHtml(inv.description)}</div>

      <div class="invoice-meta">
        <span>Reliability: <strong>${inv.reliability_score}/100</strong></span>
        <span>Days overdue: <strong>${inv.days_overdue}</strong></span>
        <span>Stage: <strong>${inv.escalation_stage}/4</strong></span>
      </div>

      ${!isPaid ? `
        <div class="muted" style="font-size:12px; margin-bottom:4px;">
          Recovery probability: ${inv.recovery_probability}%
        </div>
        <div class="prob-bar-track">
          <div class="prob-bar-fill" style="width:${inv.recovery_probability}%;"></div>
        </div>
      ` : ""}

      <div class="invoice-actions">
        ${canRecover ? `<button class="btn-primary" onclick="runRecovery(${inv.id})">Force Step Now</button>` : ""}
        ${canPay ? `<button class="btn-secondary" onclick="simulatePay(${inv.id})">Mark as Paid</button>` : ""}
      </div>
    </div>
  `;
}

function humanAttentionRowHTML(inv) {
  return `
    <div class="human-row">
      <div onclick="openHistoryModal(${inv.id})" style="flex:1; cursor:pointer;">
        <div class="invoice-customer">${escapeHtml(inv.customer_name)}</div>
        <div class="muted" style="font-size:12px;">${escapeHtml(inv.customer_industry)} · ${escapeHtml(inv.invoice_no)} · ${inv.days_overdue} days overdue</div>
      </div>
      <div style="text-align:right;">
        <div class="invoice-amount">${formatMoney(inv.amount)}</div>
        <div class="human-row-actions">
          <span class="muted" style="font-size:12px; cursor:pointer;" onclick="openHistoryModal(${inv.id})">History →</span>
          <button class="btn-secondary" onclick="event.stopPropagation(); simulatePay(${inv.id})">Mark as Paid</button>
        </div>
      </div>
    </div>
  `;
}

function renderSections() {
  const sorted = sortInvoices(allInvoices, currentSort.field, currentSort.direction);

  const awaitingDue = sorted.filter(i => i.status === "promised");
  const active = sorted.filter(i => i.status === "broken" && i.escalation_stage < 4);
  const needsHuman = sorted.filter(i => i.status === "broken" && i.escalation_stage >= 4);
  const recovered = sorted.filter(i => i.status === "paid");

  document.getElementById("count-awaiting").textContent = awaitingDue.length;
  document.getElementById("count-active").textContent = active.length;
  document.getElementById("count-human").textContent = needsHuman.length;
  document.getElementById("count-recovered").textContent = recovered.length;

  document.getElementById("section-awaiting").innerHTML =
    awaitingDue.length ? awaitingDue.map(invoiceCardHTML).join("") : '<p class="muted">Nothing here right now.</p>';

  document.getElementById("section-active").innerHTML =
    active.length ? active.map(invoiceCardHTML).join("") : '<p class="muted">Nothing here right now.</p>';

  document.getElementById("section-human").innerHTML =
    needsHuman.length ? needsHuman.map(humanAttentionRowHTML).join("") : '<p class="muted">No invoices have needed human handoff yet.</p>';

  document.getElementById("section-recovered").innerHTML =
    recovered.length ? recovered.map(invoiceCardHTML).join("") : '<p class="muted">Nothing recovered yet.</p>';
}

async function loadInvoices() {
  allInvoices = await fetchJSON("/api/invoices");
  renderSections();
}

async function loadAuditLog() {
  const entries = await fetchJSON("/api/audit-log");
  const container = document.getElementById("audit-log");

  if (entries.length === 0) {
    container.innerHTML = '<p class="muted">No actions yet. The automation will start acting on overdue invoices shortly.</p>';
    return;
  }

  container.innerHTML = entries.slice(0, 25).map(e => `
    <div class="audit-entry">
      <div class="a-action">
        ${ACTION_LABELS[e.action] || e.action} — ${escapeHtml(e.customer_name)}
        <span class="trigger-tag ${e.triggered_by}">${e.triggered_by === "automatic" ? "AUTO" : "MANUAL"}</span>
      </div>
      <div class="a-explanation">${escapeHtml(e.explanation)}</div>
      ${e.delivery_detail ? `<div class="muted" style="font-size:11px;">${escapeHtml(e.delivery_detail)}</div>` : ""}
      <div class="muted" style="font-size:11px; margin-top:2px;">${e.timestamp} · Invoice #${e.invoice_id}</div>
    </div>
  `).join("");
}

async function refreshAll() {
  await Promise.all([loadSummary(), loadInvoices(), loadAuditLog()]);
}

async function runRecovery(invoiceId) {
  const result = await fetchJSON(`/api/recover/${invoiceId}`, { method: "POST" });
  showModal(result);
  refreshAll();
}

async function simulatePay(invoiceId) {
  await fetchJSON(`/api/simulate-pay/${invoiceId}`, { method: "POST" });
  refreshAll();
}

// Builds the HTML for the message preview, styled to match the channel
// it was "sent" on. Same message text, three different visual skins.
function messagePreviewHTML(message, channel, customerName) {
  const safeMessage = escapeHtml(message);
  if (channel === "whatsapp") {
    return `<div class="msg-whatsapp"><div class="bubble">${safeMessage}</div><div class="meta">✓✓ Delivered</div></div>`;
  }
  if (channel === "sms") {
    return `<div class="msg-sms"><div class="bubble">${safeMessage}</div></div>`;
  }
  return `
    <div class="msg-email">
      <div class="email-header"><strong>To:</strong> ${escapeHtml(customerName)}<br/><strong>Subject:</strong> Payment Reminder - Outstanding Invoice</div>
      <div class="email-body">${safeMessage}</div>
    </div>
  `;
}

function showModal(result) {
  document.getElementById("modal-title").textContent =
    `${ACTION_LABELS[result.action] || result.action} — ${result.customer_name}`;
  document.getElementById("modal-explanation").textContent = result.explanation;

  const msgBox = document.getElementById("modal-message");
  if (result.message) {
    const channel = result.channel || "email";
    const badge = `<span class="channel-badge ${channel}">via ${CHANNEL_LABELS[channel]}</span>`;
    const delivery = result.delivery_detail ? `<div class="muted" style="font-size:12px; margin-top:8px;">${escapeHtml(result.delivery_detail)}</div>` : "";
    msgBox.style.display = "block";
    msgBox.innerHTML = badge + messagePreviewHTML(result.message, channel, result.customer_name) + delivery;
  } else {
    msgBox.style.display = "none";
  }

  document.getElementById("message-modal").classList.remove("hidden");
}

// ---------------------------------------------------------------------
// "Needs Human Attention" click-through: shows the FULL history of every
// automated attempt made on that invoice before it got flagged.
// ---------------------------------------------------------------------
async function openHistoryModal(invoiceId) {
  const inv = allInvoices.find(i => i.id === invoiceId);
  const history = await fetchJSON(`/api/audit-log/${invoiceId}`);

  document.getElementById("modal-title").textContent = `${inv.customer_name} — Full History`;
  document.getElementById("modal-explanation").textContent =
    `${inv.invoice_no} · ${formatMoney(inv.amount)} · ${inv.days_overdue} days overdue · Flagged for human review after ${history.length} automated attempt(s).`;

  const msgBox = document.getElementById("modal-message");
  msgBox.style.display = "block";
  msgBox.innerHTML = history.map(e => `
    <div style="margin-bottom:10px; padding-bottom:10px; border-bottom:1px solid var(--border);">
      <div style="font-weight:600; font-size:13px;">
        ${ACTION_LABELS[e.action] || e.action}
        <span class="trigger-tag ${e.triggered_by}">${e.triggered_by === "automatic" ? "AUTO" : "MANUAL"}</span>
      </div>
      <div class="muted" style="font-size:12px;">${escapeHtml(e.explanation)}</div>
      <div class="muted" style="font-size:11px;">${e.timestamp}</div>
    </div>
  `).join("") || '<p class="muted">No history recorded.</p>';

  document.getElementById("message-modal").classList.remove("hidden");
}

// ---------------------------------------------------------------------
// Sort control wiring
// ---------------------------------------------------------------------
document.getElementById("sort-field").addEventListener("change", (e) => {
  currentSort.field = e.target.value;
  renderSections();
});

document.getElementById("sort-direction").addEventListener("click", () => {
  currentSort.direction = currentSort.direction === "desc" ? "asc" : "desc";
  document.getElementById("sort-direction").textContent = currentSort.direction === "desc" ? "↓ High to Low" : "↑ Low to High";
  renderSections();
});

document.getElementById("modal-close").addEventListener("click", () => {
  document.getElementById("message-modal").classList.add("hidden");
});

// Collapsible section headers (native <details> handles the toggle itself -
// no JS needed for that part, this just updates the arrow icon)
document.querySelectorAll("details.section").forEach(d => {
  d.addEventListener("toggle", () => {
    const icon = d.querySelector(".toggle-icon");
    if (icon) icon.textContent = d.open ? "▾" : "▸";
  });
});

// ---------------------------------------------------------------------
// Add Company form - lets you type in a brand-new company + invoice live,
// mainly useful to (a) prove the system isn't just replaying fixed data,
// and (b) test real email sending by putting in your own address.
// ---------------------------------------------------------------------
document.getElementById("add-company-form").addEventListener("submit", async (e) => {
  e.preventDefault();

  const payload = {
    name: document.getElementById("ac-name").value,
    industry: document.getElementById("ac-industry").value,
    contact: document.getElementById("ac-contact").value,
    amount: document.getElementById("ac-amount").value,
    promise_days_from_now: document.getElementById("ac-promise-days").value,
    history: document.getElementById("ac-history").value,
  };

  const result = await fetchJSON("/api/add-company", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  const resultBox = document.getElementById("add-company-result");
  if (result.error) {
    resultBox.innerHTML = `<p style="color:var(--high-risk); font-size:13px; margin-top:10px;">${escapeHtml(result.error)}</p>`;
    return;
  }

  let html = `<p style="color:var(--low-risk); font-size:13px; margin-top:10px;">
    Added! Reliability score: ${result.reliability_score}/100 (${result.risk_tier} risk).
  </p>`;
  if (result.caution) {
    html += `<p style="color:var(--high-risk); font-size:13px; font-weight:600; margin-top:6px;">${escapeHtml(result.caution)}</p>`;
  }
  resultBox.innerHTML = html;

  document.getElementById("add-company-form").reset();
  refreshAll();
});

refreshAll();
// Poll every 5 seconds so the automatic background escalation (running on
// the server) becomes visible on screen without you touching anything.
setInterval(refreshAll, 5000);
