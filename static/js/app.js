const bloodGroups = ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"];
const demoAccounts = {
  donor: ["donor@bloodbank.demo", "Donor@123"],
  hospital: ["hospital@bloodbank.demo", "Hospital@123"],
  admin: ["admin@bloodbank.demo", "Admin@123"],
};

const state = {
  user: null,
  overview: null,
  charts: {},
  sse: null,
};

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));

function iconRefresh() {
  if (window.lucide) window.lucide.createIcons();
}

function toast(message, type = "info") {
  const root = $("#toast-root");
  const el = document.createElement("div");
  el.className = `toast ${type}`;
  el.textContent = message;
  root.appendChild(el);
  setTimeout(() => el.remove(), 4200);
}

async function api(path, options = {}) {
  const config = {
    credentials: "same-origin",
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  };
  if (config.body && typeof config.body !== "string") {
    config.body = JSON.stringify(config.body);
  }
  const response = await fetch(path, config);
  const text = await response.text();
  const data = text ? JSON.parse(text) : {};
  if (!response.ok) {
    throw new Error(data.error || "Request failed");
  }
  return data;
}

function formData(form) {
  return Object.fromEntries(new FormData(form).entries());
}

function setLoading(selector) {
  const el = $(selector);
  if (el) el.innerHTML = '<div class="skeleton"></div>';
}

function statusTag(value) {
  const normalized = String(value || "").toLowerCase();
  return `<span class="tag ${normalized}">${value}</span>`;
}

function setDefaultDateTimes() {
  const now = new Date(Date.now() + 3 * 60 * 60 * 1000);
  const value = new Date(now.getTime() - now.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
  $$('input[type="datetime-local"]').forEach((input) => {
    if (!input.value) input.value = value;
  });
}

function populateBloodSelects() {
  $$("select").forEach((select) => {
    if (select.name === "blood_group" || select.id.includes("blood")) {
      const keepFirst = select.querySelector("option[value='']") ? '<option value="">All groups</option>' : "";
      select.innerHTML = keepFirst + bloodGroups.map((group) => `<option value="${group}">${group}</option>`).join("");
    }
  });
}

function isAdmin() {
  return state.user && ["blood_bank_admin", "super_admin"].includes(state.user.role);
}

function syncAuthVisibility() {
  const authed = Boolean(state.user);
  $$(".app-only").forEach((el) => el.classList.toggle("hidden", !authed));
  $$(".public-only").forEach((el) => el.classList.toggle("hidden", authed));
  $$(".admin-only").forEach((el) => el.classList.toggle("hidden", !isAdmin()));
  $$(".donor-only").forEach((el) => el.classList.toggle("hidden", state.user?.role !== "donor"));
  $$(".admin-hospital").forEach((el) => {
    const visible = state.user && ["hospital", "blood_bank_admin", "super_admin"].includes(state.user.role);
    el.classList.toggle("hidden", !visible);
  });
  $("#app-shell").hidden = !authed;
  if (!authed) {
    $("#landing-view").classList.add("active");
  } else {
    showAppView("dashboard");
  }
  iconRefresh();
}

function showAppView(viewName) {
  $("#landing-view").classList.toggle("active", viewName === "landing");
  $$(".app-view").forEach((view) => view.classList.toggle("active", view.id === `${viewName}-view`));
  $$(".nav-link").forEach((btn) => btn.classList.toggle("active", btn.dataset.view === viewName));
  if (viewName !== "landing" && state.user) {
    $("#app-shell").hidden = false;
    $("#landing-view").classList.remove("active");
  }
}

async function bootstrap() {
  populateBloodSelects();
  setDefaultDateTimes();
  bindEvents();
  await loadPublicOverview();
  try {
    const { user } = await api("/api/auth/me");
    state.user = user;
  } catch {
    state.user = null;
  }
  syncAuthVisibility();
  if (state.user) await loadAll();
  connectRealtime();
  iconRefresh();
}

function bindEvents() {
  $$(".nav-link").forEach((button) => {
    button.addEventListener("click", () => {
      const view = button.dataset.view;
      if (view === "landing") {
        $("#app-shell").hidden = true;
        $("#landing-view").classList.add("active");
      } else {
        showAppView(view);
        loadView(view);
      }
    });
  });

  $$("[data-scroll-target]").forEach((button) => {
    button.addEventListener("click", () => $(`#${button.dataset.scrollTarget}`)?.scrollIntoView({ behavior: "smooth" }));
  });

  $("#login-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      const data = await api("/api/auth/login", { method: "POST", body: formData(event.currentTarget) });
      state.user = data.user;
      toast(data.message, "success");
      syncAuthVisibility();
      await loadAll();
    } catch (error) {
      toast(error.message, "error");
    }
  });

  $("#register-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const payload = formData(event.currentTarget);
    payload.gender = "Not specified";
    try {
      const data = await api("/api/auth/register", { method: "POST", body: payload });
      state.user = data.user;
      toast(data.message, "success");
      syncAuthVisibility();
      await loadAll();
    } catch (error) {
      toast(error.message, "error");
    }
  });

  $$("[data-demo-login]").forEach((button) => {
    button.addEventListener("click", () => {
      const [email, password] = demoAccounts[button.dataset.demoLogin];
      $("#login-form [name='email']").value = email;
      $("#login-form [name='password']").value = password;
      $("#login-form").requestSubmit();
    });
  });

  $("#logout-btn").addEventListener("click", async () => {
    await api("/api/auth/logout", { method: "POST" });
    state.user = null;
    state.overview = null;
    syncAuthVisibility();
    $("#app-shell").hidden = true;
    $("#landing-view").classList.add("active");
    toast("Logged out.");
  });

  $("#refresh-btn").addEventListener("click", () => loadAll(true));
  $("#request-form").addEventListener("submit", submitRequest);
  $("#appointment-form").addEventListener("submit", submitAppointment);

  ["filter-request-status", "filter-request-urgency", "filter-request-blood", "sort-request"].forEach((id) => {
    $(`#${id}`).addEventListener("change", loadRequests);
  });
  ["filter-donor-search", "filter-donor-city"].forEach((id) => {
    $(`#${id}`).addEventListener("input", debounce(loadDonors, 300));
  });
  ["filter-donor-blood", "sort-donor"].forEach((id) => $(`#${id}`).addEventListener("change", loadDonors));
}

function debounce(fn, wait) {
  let timeout;
  return (...args) => {
    clearTimeout(timeout);
    timeout = setTimeout(() => fn(...args), wait);
  };
}

async function loadPublicOverview() {
  const snapshot = await api("/api/dashboard/public");
  renderLanding(snapshot);
}

async function loadAll(showToast = false) {
  if (!state.user) return;
  await Promise.all([loadOverview(), loadRequests(), loadInventory(), loadAppointments(), loadNotifications()]);
  if (isAdmin()) await Promise.all([loadAdmin(), loadDonations()]);
  if (["hospital", "blood_bank_admin", "super_admin"].includes(state.user.role)) await loadDonors();
  if (state.user.role === "donor") await renderDonorDashboard();
  if (showToast) toast("Dashboard refreshed.", "success");
}

async function loadView(view) {
  if (view === "dashboard") await loadOverview();
  if (view === "requests") await loadRequests();
  if (view === "donors") await loadDonors();
  if (view === "inventory") await loadInventory();
  if (view === "appointments") await loadAppointments();
  if (view === "analytics") await loadOverview();
  if (view === "admin") await Promise.all([loadAdmin(), loadDonations()]);
}

function renderLanding(snapshot) {
  const inventory = snapshot.inventory || [];
  $("#landing-inventory-preview").innerHTML = inventory
    .map((item) => `<div class="blood-chip ${item.stock_status}"><strong>${item.blood_group}</strong><span>${item.available_units} available</span></div>`)
    .join("");
  $("#stat-donors").textContent = snapshot.counts?.total_donors ?? 0;
  $("#stat-requests").textContent = snapshot.counts?.total_requests ?? 0;
  $("#stat-critical").textContent = snapshot.counts?.critical_pending ?? 0;
  renderCritical(snapshot.critical_requests || [], "#landing-critical", false);
  iconRefresh();
}

async function loadOverview() {
  state.overview = await api("/api/dashboard/overview");
  $("#role-eyebrow").textContent = state.user.role.replaceAll("_", " ");
  $("#welcome-title").textContent = `Welcome, ${state.user.name}`;
  renderMetrics(state.overview.counts);
  renderCritical(state.overview.critical_requests, "#critical-list", true);
  renderLowStock(state.overview.low_stock || []);
  renderCharts(state.overview);
  $("#role-dashboard-panel").innerHTML = "";
  if (state.user.role === "donor") await renderDonorDashboard();
  iconRefresh();
}

function renderMetrics(counts) {
  const metrics = [
    ["Total donors", counts.total_donors],
    ["Total requests", counts.total_requests],
    ["Critical pending", counts.critical_pending],
    ["Pending appointments", counts.appointments_pending],
    ["Users", counts.users],
  ];
  $("#metric-grid").innerHTML = metrics.map(([label, value]) => `<article class="metric-card"><span>${label}</span><strong>${value}</strong></article>`).join("");
}

function renderCritical(items, selector, actionable) {
  const root = $(selector);
  if (!items.length) {
    root.innerHTML = '<div class="empty">No critical requests right now.</div>';
    return;
  }
  root.innerHTML = items
    .map(
      (item) => `
      <article class="list-item critical">
        <div class="item-top">
          <p class="item-title">${item.blood_group} needed for ${item.patient_name}</p>
          ${statusTag(item.status)}
        </div>
        <div class="item-meta">
          <span>${item.units_required} unit(s)</span><span>${item.hospital_name}</span><span>${item.city}</span><span>${formatDate(item.required_at)}</span>
        </div>
        ${actionable && isAdmin() ? requestActions(item) : ""}
      </article>`
    )
    .join("");
  $$("[data-request-action]", root).forEach((btn) => btn.addEventListener("click", () => updateRequest(btn.dataset.requestId, btn.dataset.requestAction)));
}

function renderLowStock(items) {
  const root = $("#low-stock-list");
  if (!items.length) {
    root.innerHTML = '<div class="empty">All blood groups are above threshold.</div>';
    return;
  }
  root.innerHTML = items
    .map((item) => `<article class="list-item"><div class="item-top"><p class="item-title">${item.blood_group}</p>${statusTag(item.stock_status)}</div><div class="item-meta"><span>${item.available_units} available</span><span>threshold ${item.low_stock_threshold}</span><span>${item.expired_units} expired</span></div></article>`)
    .join("");
}

async function renderDonorDashboard() {
  const [profileResult, appointmentsResult, donationsResult] = await Promise.all([
    api("/api/donors/me"),
    api("/api/appointments"),
    api("/api/donations"),
  ]);
  const profile = profileResult.profile;
  const upcoming = (appointmentsResult.items || []).find((item) => ["Pending", "Approved", "Rescheduled"].includes(item.status));
  const latestDonation = (donationsResult.items || [])[0];
  $("#role-dashboard-panel").innerHTML = `
    <section class="panel donor-self">
      <div class="panel-title"><h3>Donor dashboard</h3><span>${profile.profile_completion}% profile complete</span></div>
      <div class="horizontal-list">
        <article class="list-item"><p class="item-title">${profile.eligibility.eligible ? "Eligible" : "Not Eligible Yet"}</p><div class="item-meta"><span>${profile.eligibility.reason}</span><span>${profile.blood_group}</span></div></article>
        <article class="list-item"><p class="item-title">Upcoming appointment</p><div class="item-meta"><span>${upcoming ? `${upcoming.center} on ${formatDate(upcoming.appointment_at)}` : "No upcoming appointment"}</span></div></article>
        <article class="list-item"><p class="item-title">Donation history</p><div class="item-meta"><span>${donationsResult.items.length} record(s)</span><span>${latestDonation ? `${latestDonation.status} on ${formatDate(latestDonation.donation_date)}` : "No donations yet"}</span></div></article>
        <article class="list-item critical"><p class="item-title">Emergency alerts</p><div class="item-meta"><span>${state.overview?.critical_requests?.length || 0} active critical request(s)</span></div></article>
      </div>
    </section>`;
}

async function loadNotifications() {
  const root = $("#notification-list");
  if (!root) return;
  const { items } = await api("/api/notifications");
  if (!items.length) {
    root.innerHTML = '<div class="empty">No notifications yet.</div>';
    return;
  }
  root.innerHTML = items
    .slice(0, 8)
    .map((item) => `<article class="list-item"><div class="item-top"><p class="item-title">${item.title}</p>${statusTag(item.type)}</div><div class="item-meta"><span>${item.message}</span><span>${formatDate(item.created_at)}</span></div></article>`)
    .join("");
}

async function loadRequests() {
  if (!state.user) return;
  setLoading("#request-list");
  const params = new URLSearchParams({
    status: $("#filter-request-status").value,
    urgency: $("#filter-request-urgency").value,
    blood_group: $("#filter-request-blood").value,
    sort: $("#sort-request").value,
  });
  const data = await api(`/api/requests?${params}`);
  $("#request-total").textContent = `${data.pagination.total} result(s)`;
  renderRequests(data.items);
}

function renderRequests(items) {
  const root = $("#request-list");
  if (!items.length) {
    root.innerHTML = '<div class="empty">No requests match the current filters.</div>';
    return;
  }
  root.innerHTML = items
    .map(
      (item) => `
      <article class="list-item ${item.urgency === "Critical" ? "critical" : ""}" data-request-id="${item.id}">
        <div class="item-top"><p class="item-title">${item.patient_name} needs ${item.blood_group}</p>${statusTag(item.status)}</div>
        <div class="item-meta"><span>${item.urgency}</span><span>${item.units_required} unit(s)</span><span>${item.hospital_name}</span><span>${item.city}</span><span>${formatDate(item.required_at)}</span></div>
        <div class="item-actions">
          <button class="mini-btn" data-show-matches="${item.id}">Matches</button>
          ${isAdmin() ? requestActions(item) : ""}
        </div>
        <div class="match-zone" id="matches-${item.id}"></div>
      </article>`
    )
    .join("");
  $$("[data-show-matches]").forEach((btn) => btn.addEventListener("click", () => loadMatches(btn.dataset.showMatches)));
  $$("[data-request-action]").forEach((btn) => btn.addEventListener("click", () => updateRequest(btn.dataset.requestId, btn.dataset.requestAction)));
}

function requestActions(item) {
  if (!isAdmin()) return "";
  const buttons = [];
  if (item.status === "Pending") {
    buttons.push(`<button class="mini-btn success" data-request-id="${item.id}" data-request-action="approve">Approve</button>`);
    buttons.push(`<button class="mini-btn danger" data-request-id="${item.id}" data-request-action="reject">Reject</button>`);
  }
  if (item.status === "Matched") {
    buttons.push(`<button class="mini-btn success" data-request-id="${item.id}" data-request-action="fulfill">Fulfill</button>`);
    buttons.push(`<button class="mini-btn danger" data-request-id="${item.id}" data-request-action="cancel">Cancel</button>`);
  }
  return buttons.length ? `<div class="item-actions">${buttons.join("")}</div>` : "";
}

async function loadMatches(requestId) {
  const zone = $(`#matches-${requestId}`);
  zone.innerHTML = '<div class="skeleton"></div>';
  try {
    const { matches } = await api(`/api/requests/${requestId}/matches`);
    zone.innerHTML = matches.length
      ? `<div class="match-grid">${matches
          .slice(0, 6)
          .map((match) => `<span class="mini-status">${match.name} · ${match.blood_group} · score ${match.score}</span>`)
          .join("")}</div>`
      : '<div class="empty">No compatible donors found yet.</div>';
  } catch (error) {
    zone.innerHTML = `<div class="empty">${error.message}</div>`;
  }
}

async function updateRequest(requestId, action) {
  try {
    const data = await api(`/api/requests/${requestId}/status`, { method: "PATCH", body: { action } });
    toast(data.message, "success");
    await Promise.all([loadRequests(), loadInventory(), loadOverview()]);
  } catch (error) {
    toast(error.message, "error");
  }
}

async function submitRequest(event) {
  event.preventDefault();
  try {
    const data = await api("/api/requests", { method: "POST", body: formData(event.currentTarget) });
    toast(data.message, "success");
    event.currentTarget.reset();
    setDefaultDateTimes();
    await Promise.all([loadRequests(), loadOverview()]);
  } catch (error) {
    toast(error.message, "error");
  }
}

async function loadDonors() {
  if (!state.user) return;
  setLoading("#donor-list");
  const params = new URLSearchParams({
    search: $("#filter-donor-search").value,
    city: $("#filter-donor-city").value,
    blood_group: $("#filter-donor-blood").value,
    sort: $("#sort-donor").value,
  });
  const data = await api(`/api/donors?${params}`);
  $("#donor-total").textContent = `${data.pagination.total} donor(s)`;
  renderDonors(data.items);
}

function renderDonors(items) {
  const root = $("#donor-list");
  if (!items.length) {
    root.innerHTML = '<div class="empty">No donors found.</div>';
    return;
  }
  root.innerHTML = `
    <table>
      <thead><tr><th>Name</th><th>Blood</th><th>City</th><th>Phone</th><th>Eligibility</th><th>Profile</th></tr></thead>
      <tbody>${items
        .map(
          (item) => `
          <tr>
            <td>${item.name}<br><small>${item.email}</small></td>
            <td><strong>${item.blood_group}</strong></td>
            <td>${item.city}</td>
            <td>${item.phone || "Not provided"}</td>
            <td>${item.eligibility.eligible ? statusTag("Eligible") : statusTag("Not Eligible Yet")}<br><small>${item.eligibility.reason}</small></td>
            <td>${item.profile_completion}%</td>
          </tr>`
        )
        .join("")}</tbody>
    </table>`;
}

async function loadInventory() {
  if (!state.user) return;
  setLoading("#inventory-grid");
  const { items } = await api("/api/inventory");
  renderInventory(items);
}

function renderInventory(items) {
  $("#inventory-grid").innerHTML = items
    .map(
      (item) => `
      <article class="inventory-card ${item.stock_status}">
        <header><strong>${item.blood_group}</strong>${statusTag(item.stock_status)}</header>
        <dl>
          <div><dt>Available</dt><dd>${item.available_units}</dd></div>
          <div><dt>Reserved</dt><dd>${item.reserved_units}</dd></div>
          <div><dt>Expired</dt><dd>${item.expired_units}</dd></div>
        </dl>
        <small>Updated ${formatDate(item.last_updated_at)}</small>
        ${isAdmin() ? inventoryControls(item) : ""}
      </article>`
    )
    .join("");
  $$("[data-inventory-save]").forEach((btn) => btn.addEventListener("click", () => saveInventory(btn.dataset.inventorySave)));
}

function inventoryControls(item) {
  return `
    <div class="inventory-controls" data-inventory-form="${item.blood_group}">
      <input type="number" min="0" data-field="available_units" value="${item.available_units}" title="Available units">
      <input type="number" min="0" data-field="reserved_units" value="${item.reserved_units}" title="Reserved units">
      <input type="number" min="0" data-field="expired_units" value="${item.expired_units}" title="Expired units">
      <input type="number" min="0" data-field="low_stock_threshold" value="${item.low_stock_threshold}" title="Low stock threshold">
      <button class="mini-btn success" data-inventory-save="${item.blood_group}">Save</button>
    </div>`;
}

async function saveInventory(group) {
  const form = $(`[data-inventory-form="${CSS.escape(group)}"]`);
  const body = {};
  $$("[data-field]", form).forEach((input) => (body[input.dataset.field] = input.value));
  try {
    const data = await api(`/api/inventory/${encodeURIComponent(group)}`, { method: "PATCH", body });
    toast(data.message, "success");
    await Promise.all([loadInventory(), loadOverview()]);
  } catch (error) {
    toast(error.message, "error");
  }
}

async function loadAppointments() {
  if (!state.user) return;
  const { items } = await api("/api/appointments");
  renderAppointments(items);
}

function renderAppointments(items) {
  const root = $("#appointment-list");
  if (!items.length) {
    root.innerHTML = '<div class="empty">No appointments yet.</div>';
    return;
  }
  root.innerHTML = items
    .map(
      (item) => `
      <article class="list-item">
        <div class="item-top"><p class="item-title">${item.donor_name} at ${item.center}</p>${statusTag(item.status)}</div>
        <div class="item-meta"><span>${item.blood_group}</span><span>${formatDate(item.appointment_at)}</span><span>${item.admin_notes || "No notes"}</span></div>
        ${isAdmin() ? `<div class="item-actions"><button class="mini-btn success" data-appointment-id="${item.id}" data-appointment-status="Approved">Approve</button><button class="mini-btn" data-appointment-id="${item.id}" data-appointment-status="Rescheduled">Reschedule</button><button class="mini-btn danger" data-appointment-id="${item.id}" data-appointment-status="Cancelled">Cancel</button></div>` : ""}
      </article>`
    )
    .join("");
  $$("[data-appointment-status]").forEach((btn) => btn.addEventListener("click", () => updateAppointment(btn.dataset.appointmentId, btn.dataset.appointmentStatus)));
}

async function submitAppointment(event) {
  event.preventDefault();
  try {
    const data = await api("/api/appointments", { method: "POST", body: formData(event.currentTarget) });
    toast(data.message, "success");
    event.currentTarget.reset();
    setDefaultDateTimes();
    await loadAppointments();
  } catch (error) {
    toast(error.message, "error");
  }
}

async function updateAppointment(id, status) {
  try {
    const data = await api(`/api/appointments/${id}/status`, { method: "PATCH", body: { status } });
    toast(data.message, "success");
    await loadAppointments();
  } catch (error) {
    toast(error.message, "error");
  }
}

async function loadDonations() {
  if (!isAdmin()) return;
  const { items } = await api("/api/donations");
  const pendingFirst = items.sort((a, b) => (a.status === "Pending" ? -1 : 1));
  $("#donation-list").innerHTML = pendingFirst.length
    ? pendingFirst
        .map(
          (item) => `
          <article class="list-item">
            <div class="item-top"><p class="item-title">${item.donor_name} · ${item.blood_group}</p>${statusTag(item.status)}</div>
            <div class="item-meta"><span>${item.center}</span><span>${formatDate(item.donation_date)}</span><span>${item.units} unit(s)</span></div>
            ${item.status === "Pending" ? `<div class="item-actions"><button class="mini-btn success" data-donation-id="${item.id}" data-donation-status="Accepted">Accept</button><button class="mini-btn danger" data-donation-id="${item.id}" data-donation-status="Rejected">Reject</button></div>` : ""}
          </article>`
        )
        .join("")
    : '<div class="empty">No donation records yet.</div>';
  $$("[data-donation-status]").forEach((btn) => btn.addEventListener("click", () => verifyDonation(btn.dataset.donationId, btn.dataset.donationStatus)));
}

async function verifyDonation(id, status) {
  try {
    const data = await api(`/api/donations/${id}/verify`, { method: "PATCH", body: { status } });
    toast(data.message, "success");
    await Promise.all([loadDonations(), loadInventory(), loadOverview()]);
  } catch (error) {
    toast(error.message, "error");
  }
}

async function loadAdmin() {
  if (!isAdmin()) return;
  const [users, logs] = await Promise.all([api("/api/admin/users"), api("/api/admin/audit-logs")]);
  renderUsers(users.items);
  renderAudit(logs.items);
}

function renderUsers(items) {
  $("#user-list").innerHTML = `
    <table><thead><tr><th>User</th><th>Role</th><th>City</th><th>Status</th></tr></thead>
    <tbody>${items
      .map((item) => `<tr><td>${item.name}<br><small>${item.email}</small></td><td>${item.role.replaceAll("_", " ")}</td><td>${item.city || ""}</td><td>${item.is_active ? "Active" : "Disabled"}</td></tr>`)
      .join("")}</tbody></table>`;
}

function renderAudit(items) {
  $("#audit-list").innerHTML = `
    <table><thead><tr><th>Time</th><th>Actor</th><th>Action</th><th>Details</th></tr></thead>
    <tbody>${items
      .map((item) => `<tr><td>${formatDate(item.created_at)}</td><td>${item.actor_name || "System"}</td><td>${item.action}</td><td>${item.details || ""}</td></tr>`)
      .join("")}</tbody></table>`;
}

function renderCharts(data) {
  if (!window.Chart) return;
  const stockLabels = (data.inventory || []).map((item) => item.blood_group);
  const stockValues = (data.inventory || []).map((item) => item.available_units);
  drawChart("stock-chart", "bar", stockLabels, [{ label: "Available units", data: stockValues, backgroundColor: "#c81e36" }]);
  drawChart("donation-chart", "line", Object.keys(data.monthly_donations || {}), [{ label: "Donations", data: Object.values(data.monthly_donations || {}), borderColor: "#157347", backgroundColor: "rgba(21, 115, 71, .15)", tension: 0.35, fill: true }]);
  drawChart("request-chart", "line", Object.keys(data.monthly_requests || {}), [{ label: "Requests", data: Object.values(data.monthly_requests || {}), borderColor: "#14213d", backgroundColor: "rgba(20, 33, 61, .13)", tension: 0.35, fill: true }]);
  drawChart("urgency-chart", "doughnut", Object.keys(data.urgency_distribution || {}), [{ data: Object.values(data.urgency_distribution || {}), backgroundColor: ["#c81e36", "#b45309", "#157347"] }]);
  drawChart("city-chart", "bar", (data.city_donor_count || []).map((item) => item.city), [{ label: "Donors", data: (data.city_donor_count || []).map((item) => item.count), backgroundColor: "#24324a" }]);
}

function drawChart(id, type, labels, datasets) {
  const canvas = $(`#${id}`);
  if (!canvas) return;
  if (state.charts[id]) state.charts[id].destroy();
  state.charts[id] = new Chart(canvas, {
    type,
    data: { labels, datasets },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      plugins: { legend: { display: type !== "bar" || datasets.length > 1 } },
      scales: type === "doughnut" ? {} : { y: { beginAtZero: true, ticks: { precision: 0 } } },
    },
  });
}

function connectRealtime() {
  if (!window.EventSource) {
    startPolling();
    return;
  }
  state.sse = new EventSource("/api/dashboard/events");
  state.sse.addEventListener("dashboard", (event) => {
    const snapshot = JSON.parse(event.data);
    renderLanding(snapshot);
    if (state.user && state.overview) {
      state.overview.inventory = snapshot.inventory;
      state.overview.low_stock = snapshot.low_stock;
      state.overview.critical_requests = snapshot.critical_requests;
      renderCritical(snapshot.critical_requests, "#critical-list", true);
      renderLowStock(snapshot.low_stock || []);
    }
    $("#realtime-status")?.classList.add("online");
  });
  state.sse.onerror = () => {
    $("#realtime-status")?.classList.add("offline");
    state.sse.close();
    startPolling();
  };
}

function startPolling() {
  $("#realtime-status")?.classList.add("offline");
  setInterval(loadPublicOverview, 10000);
}

function formatDate(value) {
  if (!value) return "Not scheduled";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

document.addEventListener("DOMContentLoaded", bootstrap);
