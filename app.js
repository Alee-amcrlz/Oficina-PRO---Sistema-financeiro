const DB_NAME = "oficina_pro_db";
const DB_VERSION = 1;
const STATUS = {
  pending: "pendente",
  approved: "aprovado",
  rejected: "reprovado"
};
const MASTER_USER = {
  name: "MASTER",
  email: "master@oficina.local",
  password: "Master@123",
  role: "admin",
  accessLevel: "administrador"
};
const DEFAULT_ACCESS_LEVELS = {
  administrador: "Administrador",
  financeiro: "Financeiro",
  analista: "Analista"
};
const PERMISSIONS = {
  dashboard_view: "Visualizar painel",
  budgets_view: "Visualizar atendimento",
  budgets_manage: "Criar e editar orçamentos",
  budgets_approve: "Aprovar e reprovar orçamentos",
  billing_view: "Visualizar financeiro",
  billing_edit: "Editar orçamentos pelo financeiro"
};
const DEFAULT_PERMISSIONS = {
  administrador: ["dashboard_view", "budgets_view", "budgets_manage", "budgets_approve", "billing_view", "billing_edit"],
  financeiro: ["dashboard_view", "billing_view"],
  analista: ["dashboard_view", "budgets_view", "budgets_manage"]
};
const FEATURE_ALIASES = {
  dashboard: "dashboard_view",
  budgets: "budgets_view",
  billing: "billing_view"
};
const ACCESS_LEVELS_KEY = "oficina_access_levels";
const PERMISSIONS_KEY = "oficina_access_permissions";

let db;
let currentUser = null;
let budgets = [];
let users = [];
let editingBudgetId = null;
let selectedBudgetId = null;
let compactBudgetList = false;

const currency = new Intl.NumberFormat("pt-BR", {
  style: "currency",
  currency: "BRL"
});

const dateFormat = new Intl.DateTimeFormat("pt-BR");

const $ = (selector) => document.querySelector(selector);

function openDatabase() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION);

    request.onupgradeneeded = () => {
      const database = request.result;

      if (!database.objectStoreNames.contains("users")) {
        const users = database.createObjectStore("users", { keyPath: "id", autoIncrement: true });
        users.createIndex("email", "email", { unique: true });
      }

      if (!database.objectStoreNames.contains("budgets")) {
        const budgetStore = database.createObjectStore("budgets", { keyPath: "id", autoIncrement: true });
        budgetStore.createIndex("userId", "userId");
        budgetStore.createIndex("status", "status");
      }
    };

    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

function store(name, mode = "readonly") {
  return db.transaction(name, mode).objectStore(name);
}

function requestToPromise(request) {
  return new Promise((resolve, reject) => {
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

async function hashPassword(password) {
  if (!crypto.subtle) {
    let hash = 2166136261;
    for (const char of password) {
      hash ^= char.charCodeAt(0);
      hash += (hash << 1) + (hash << 4) + (hash << 7) + (hash << 8) + (hash << 24);
    }
    return `fallback-${(hash >>> 0).toString(16)}`;
  }

  const bytes = new TextEncoder().encode(password);
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return Array.from(new Uint8Array(digest)).map((byte) => byte.toString(16).padStart(2, "0")).join("");
}

async function createUser(user) {
  return requestToPromise(store("users", "readwrite").add(user));
}

async function updateUser(user) {
  return requestToPromise(store("users", "readwrite").put(user));
}

async function deleteUser(id) {
  return requestToPromise(store("users", "readwrite").delete(Number(id)));
}

async function loadAllUsers() {
  users = await requestToPromise(store("users").getAll());
  users.sort((a, b) => String(a.name).localeCompare(String(b.name), "pt-BR"));
  renderUsersTable();
}

async function findUserByEmail(email) {
  const index = store("users").index("email");
  return requestToPromise(index.get(String(email).toLowerCase().trim()));
}

async function ensureMasterUser() {
  const existing = await findUserByEmail(MASTER_USER.email);
  if (existing) {
    const normalized = {
      ...existing,
      name: existing.name || MASTER_USER.name,
      role: "admin",
      accessLevel: "administrador"
    };
    await updateUser(normalized);
    return;
  }

  await createUser({
    name: MASTER_USER.name,
    email: MASTER_USER.email,
    passwordHash: await hashPassword(MASTER_USER.password),
    role: MASTER_USER.role,
    accessLevel: MASTER_USER.accessLevel,
    createdAt: new Date().toISOString()
  });
}

async function saveBudget(budget) {
  return requestToPromise(store("budgets", "readwrite").add(budget));
}

async function updateBudget(budget) {
  return requestToPromise(store("budgets", "readwrite").put(budget));
}

async function loadBudgets() {
  const all = await requestToPromise(store("budgets").getAll());
  const visibleBudgets = canAccess("billing_view")
    ? all
    : all.filter((budget) => budget.userId === currentUser.id);

  budgets = visibleBudgets
    .sort((a, b) => new Date(b.createdAt) - new Date(a.createdAt));
  renderAll();
}

function setMessage(element, text, isSuccess = false) {
  element.textContent = text;
  element.style.color = isSuccess ? "var(--success)" : "var(--danger)";
}

function showApp() {
  $("#authView").classList.add("hidden");
  $("#appView").classList.remove("hidden");
  $("#userName").textContent = isMasterUser()
    ? `${currentUser.name} - ADMIN`
    : currentUser.name;
  applyNavigationPermissions();
  loadBudgets();
  if (canAccess("settings")) {
    loadAllUsers();
    renderPermissionMatrix();
    renderAccessLevelControls();
  }
}

function showAuth() {
  currentUser = null;
  sessionStorage.removeItem("oficina_user");
  $("#appView").classList.add("hidden");
  $("#authView").classList.remove("hidden");
}

function switchView(viewId) {
  const button = document.querySelector(`[data-view="${viewId}"]`);
  const feature = button?.dataset.feature;
  if (feature && !canAccess(feature)) {
    const firstAllowed = firstAllowedView();
    if (firstAllowed && firstAllowed !== viewId) switchView(firstAllowed);
    return;
  }

  document.querySelectorAll(".view").forEach((view) => view.classList.add("hidden"));
  document.querySelectorAll(".nav-button").forEach((button) => button.classList.remove("active"));
  $(`#${viewId}`).classList.remove("hidden");
  if (button) {
    button.classList.add("active");
  }
  if (viewId !== "settingsView") {
    $("#settingsSubmenu")?.classList.remove("is-open");
  }

  const titles = {
    dashboardView: "Painel",
    budgetView: "Atendimento / Orçamentos",
    billingView: "Financeiro / Fluxo de caixa",
    accountsPayableView: "Financeiro / Contas à pagar",
    costTableView: "Financeiro / Tabela de custos",
    settingsView: "Configurações"
  };
  $("#pageTitle").textContent = viewId === "settingsView" ? settingsSectionTitle() : titles[viewId];
  $("#newBudgetButton").classList.toggle("hidden", viewId !== "budgetView" || !canAccess("budgets_manage"));
  $("#budgetForm").classList.toggle("hidden", viewId === "budgetView" && !canAccess("budgets_manage"));
  $("#budgetLayout")?.classList.toggle("list-only", false);

  if (viewId === "settingsView") {
    loadAllUsers();
    renderPermissionMatrix();
    renderAccessLevelControls();
    if (!document.querySelector(".side-submenu-button.active")) {
      switchSettingsSection("usersSettings");
    }
  }
}

function currentAccessLevel() {
  if (!currentUser) return "analista";
  if (currentUser.role === "admin") return "administrador";
  return currentUser.accessLevel || "analista";
}

function isMasterUser() {
  return currentUser?.role === "admin";
}

function accessLevelsConfig() {
  try {
    const saved = JSON.parse(localStorage.getItem(ACCESS_LEVELS_KEY));
    return { ...DEFAULT_ACCESS_LEVELS, ...(saved || {}) };
  } catch {
    return DEFAULT_ACCESS_LEVELS;
  }
}

function saveAccessLevelsConfig(config) {
  localStorage.setItem(ACCESS_LEVELS_KEY, JSON.stringify(config));
}

function normalizePermissionList(list = []) {
  const normalized = new Set();
  list.forEach((permission) => {
    const mapped = FEATURE_ALIASES[permission] || permission;
    if (permission === "budgets") {
      normalized.add("budgets_view");
      normalized.add("budgets_manage");
      normalized.add("budgets_approve");
      return;
    }
    if (permission === "billing") {
      normalized.add("billing_view");
      normalized.add("billing_edit");
      return;
    }
    normalized.add(mapped);
  });
  return Array.from(normalized);
}

function permissionsConfig() {
  try {
    const saved = JSON.parse(localStorage.getItem(PERMISSIONS_KEY));
    const accessLevels = accessLevelsConfig();
    const config = {};
    Object.keys(accessLevels).forEach((level) => {
      config[level] = normalizePermissionList(saved?.[level] || DEFAULT_PERMISSIONS[level] || []);
    });
    return config;
  } catch {
    return DEFAULT_PERMISSIONS;
  }
}

function savePermissionsConfig(config) {
  localStorage.setItem(PERMISSIONS_KEY, JSON.stringify(config));
}

function canAccess(feature) {
  if (!currentUser) return false;
  if (feature === "settings") return currentUser.role === "admin";
  if (currentUser.role === "admin") return true;
  const normalizedFeature = FEATURE_ALIASES[feature] || feature;
  return permissionsConfig()[currentAccessLevel()]?.includes(normalizedFeature) || false;
}

function firstAllowedView() {
  return Array.from(document.querySelectorAll(".nav-button[data-view]"))
    .find((button) => canAccess(button.dataset.feature))?.dataset.view;
}

function applyNavigationPermissions() {
  document.querySelectorAll(".nav-button").forEach((button) => {
    button.classList.toggle("hidden", !canAccess(button.dataset.feature));
  });
  document.querySelectorAll(".nav-group").forEach((group) => {
    group.classList.toggle("hidden", !canAccess(group.dataset.feature));
  });

  const active = document.querySelector(".nav-button.active");
  if (!active || active.classList.contains("hidden")) {
    const view = firstAllowedView();
    if (view) switchView(view);
  } else {
    $("#newBudgetButton").classList.toggle("hidden", active.dataset.view !== "budgetView" || !canAccess("budgets_manage"));
    $("#budgetForm").classList.toggle("hidden", active.dataset.view === "budgetView" && !canAccess("budgets_manage"));
  }
}

function normalizeParts(budget) {
  if (Array.isArray(budget.parts) && budget.parts.length) {
    return budget.parts.map((part) => ({
      quantity: Number(part.quantity || 0),
      description: part.description || "",
      value: Number(part.value || 0)
    }));
  }

  if (budget.description || budget.partsValue) {
    return [{
      quantity: 1,
      description: budget.description || "Peças cadastradas no formato anterior",
      value: Number(budget.partsValue || 0)
    }];
  }

  return [];
}

function normalizeLabor(budget) {
  if (Array.isArray(budget.labor) && budget.labor.length) {
    return budget.labor.map((item) => ({
      description: item.description || "",
      value: Number(item.value || 0)
    }));
  }

  if (budget.description || budget.laborValue) {
    return [{
      description: budget.description || "Mão de obra cadastrada no formato anterior",
      value: Number(budget.laborValue || 0)
    }];
  }

  return [];
}

function partsTotal(budget) {
  return normalizeParts(budget).reduce((sum, part) => sum + (Number(part.quantity) * Number(part.value)), 0);
}

function laborTotal(budget) {
  return normalizeLabor(budget).reduce((sum, item) => sum + Number(item.value), 0);
}

function totalBudget(budget) {
  return partsTotal(budget) + laborTotal(budget);
}

function renderItemsSummary(budget) {
  const parts = normalizeParts(budget);
  const labor = normalizeLabor(budget);

  const partsText = parts.length
    ? parts.map((part) => `${part.quantity}x ${escapeHtml(part.description)} (${currency.format(Number(part.value))})`).join("<br>")
    : "Sem peças";

  const laborText = labor.length
    ? labor.map((item) => `${escapeHtml(item.description)} (${currency.format(Number(item.value))})`).join("<br>")
    : "Sem mão de obra";

  return `
    <div class="budget-meta">
      <span><strong>Peças:</strong> ${currency.format(partsTotal(budget))}</span>
      <span><strong>Mão de obra:</strong> ${currency.format(laborTotal(budget))}</span>
    </div>
    <p><strong>Peças</strong><br>${partsText}</p>
    <p><strong>Mão de obra</strong><br>${laborText}</p>
  `;
}

function renderBudgetDetail(budget) {
  const partsRows = normalizeParts(budget).map((part) => `
    <tr>
      <td>${escapeHtml(part.quantity)}</td>
      <td>${escapeHtml(part.description)}</td>
      <td>${currency.format(Number(part.value))}</td>
      <td>${currency.format(Number(part.quantity) * Number(part.value))}</td>
    </tr>
  `).join("");
  const laborRows = normalizeLabor(budget).map((item) => `
    <tr>
      <td>${escapeHtml(item.description)}</td>
      <td>${currency.format(Number(item.value))}</td>
    </tr>
  `).join("");

  return `
    <div class="detail-grid">
      <div class="detail-box"><span>Cliente</span><strong>${escapeHtml(budget.clientName)}</strong></div>
      <div class="detail-box"><span>E-mail</span><strong>${escapeHtml(budget.clientEmail)}</strong></div>
      <div class="detail-box"><span>Telefone</span><strong>${escapeHtml(budget.clientPhone || "Não informado")}</strong></div>
      <div class="detail-box"><span>Endereço</span><strong>${escapeHtml(budget.clientAddress || "Não informado")}</strong></div>
      <div class="detail-box"><span>Veículo</span><strong>${escapeHtml(budget.vehicle)} - ${escapeHtml(budget.plate)}</strong></div>
      <div class="detail-box"><span>Status</span><strong><span class="badge ${budget.status}">${budget.status}</span></strong></div>
      <div class="detail-box"><span>Total em peças</span><strong>${currency.format(partsTotal(budget))}</strong></div>
      <div class="detail-box"><span>Total em mão de obra</span><strong>${currency.format(laborTotal(budget))}</strong></div>
      <div class="detail-box"><span>Total do orçamento</span><strong>${currency.format(totalBudget(budget))}</strong></div>
      <div class="detail-box"><span>Data</span><strong>${dateFormat.format(new Date(budget.createdAt))}</strong></div>
    </div>
    <h3>Peças</h3>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Quantidade</th>
            <th>Descrição</th>
            <th>Valor unitário</th>
            <th>Total</th>
          </tr>
        </thead>
        <tbody>${partsRows || '<tr><td colspan="4">Sem peças</td></tr>'}</tbody>
      </table>
    </div>
    <h3>Mão de obra</h3>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Descrição</th>
            <th>Valor</th>
          </tr>
        </thead>
        <tbody>${laborRows || '<tr><td colspan="2">Sem mão de obra</td></tr>'}</tbody>
      </table>
    </div>
    ${budget.notes ? `<p><strong>Observações:</strong> ${escapeHtml(budget.notes)}</p>` : ""}
  `;
}

function renderAll() {
  renderMetrics();
  renderRecentBudgets();
  renderBudgetList();
  renderBilling();
}

function renderMetrics() {
  $("#pendingCount").textContent = budgets.filter((budget) => budget.status === STATUS.pending).length;
  $("#approvedCount").textContent = budgets.filter((budget) => budget.status === STATUS.approved).length;
  $("#rejectedCount").textContent = budgets.filter((budget) => budget.status === STATUS.rejected).length;

  const revenue = budgets
    .filter((budget) => budget.status === STATUS.approved)
    .reduce((sum, budget) => sum + totalBudget(budget), 0);

  $("#revenueTotal").textContent = currency.format(revenue);
}

function budgetRows(items) {
  if (!items.length) {
    return '<p class="empty">Nenhum registro encontrado.</p>';
  }

  const rows = items.map((budget) => `
    <tr>
      <td>${escapeHtml(budget.clientName)}</td>
      <td>${escapeHtml(budget.vehicle)}<br><span class="muted">${escapeHtml(budget.plate)}</span></td>
      <td><span class="badge ${budget.status}">${budget.status}</span></td>
      <td>${currency.format(totalBudget(budget))}</td>
      <td>${dateFormat.format(new Date(budget.createdAt))}</td>
    </tr>
  `).join("");

  return `
    <table>
      <thead>
        <tr>
          <th>Cliente</th>
          <th>Veículo</th>
          <th>Status</th>
          <th>Valor</th>
          <th>Data</th>
        </tr>
      </thead>
      <tbody>${rows}</tbody>
    </table>
  `;
}

function renderRecentBudgets() {
  $("#recentBudgets").innerHTML = budgetRows(budgets.slice(0, 6));
}

function renderBudgetList() {
  const filter = $("#statusFilter").value;
  const search = ($("#budgetSearch")?.value || "").toLowerCase().trim();
  const filtered = (filter === "todos" ? budgets : budgets.filter((budget) => budget.status === filter))
    .filter((budget) => {
      const searchable = [
        budget.clientName,
        budget.vehicle,
        budget.plate,
        budget.clientEmail,
        budget.clientPhone
      ].join(" ").toLowerCase();
      return !search || searchable.includes(search);
    });

  if (!filtered.length) {
    $("#budgetList").innerHTML = '<p class="empty">Nenhum orçamento para este filtro.</p>';
    return;
  }

  if (compactBudgetList) {
    $("#budgetList").classList.remove("budget-list");
    const rows = filtered.map((budget) => `
      <tr>
        <td>
          <button class="table-link" data-action="view" data-id="${budget.id}">${escapeHtml(budget.clientName)}</button>
        </td>
        <td>${escapeHtml(budget.vehicle)}<br><span class="muted">${escapeHtml(budget.plate)}</span></td>
        <td><span class="badge ${budget.status}">${budget.status}</span></td>
        <td>${currency.format(totalBudget(budget))}</td>
        <td>${dateFormat.format(new Date(budget.createdAt))}</td>
      </tr>
    `).join("");

    $("#budgetList").innerHTML = `
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Cliente</th>
              <th>Carro</th>
              <th>Status</th>
              <th>Valor</th>
              <th>Data</th>
            </tr>
          </thead>
          <tbody>${rows}</tbody>
        </table>
      </div>
    `;
    return;
  }

  $("#budgetList").classList.add("budget-list");
  $("#budgetList").innerHTML = filtered.map((budget) => `
    <article class="budget-card">
      <header>
        <div>
          <h3>${escapeHtml(budget.clientName)}</h3>
          <span class="muted">${escapeHtml(budget.vehicle)} - ${escapeHtml(budget.plate)}</span>
        </div>
        <span class="badge ${budget.status}">${budget.status}</span>
      </header>
      <div class="budget-meta">
        <span>${escapeHtml(budget.clientEmail)}</span>
        ${budget.clientPhone ? `<span>${escapeHtml(budget.clientPhone)}</span>` : ""}
        <span>${dateFormat.format(new Date(budget.createdAt))}</span>
        <strong>${currency.format(totalBudget(budget))}</strong>
      </div>
      ${renderItemsSummary(budget)}
      <div class="actions">
        <button class="action" data-action="view" data-id="${budget.id}">Visualizar</button>
        ${canAccess("budgets_manage") ? `<button class="action" data-action="edit" data-id="${budget.id}">Editar</button>` : ""}
        <button class="action" data-action="email" data-id="${budget.id}">Enviar e-mail</button>
        <button class="action" data-action="print" data-id="${budget.id}">Imprimir</button>
        ${budget.status === STATUS.pending && canAccess("budgets_approve") ? `
          <button class="action success" data-action="approve" data-id="${budget.id}">Aprovar</button>
          <button class="action danger" data-action="reject" data-id="${budget.id}">Reprovar</button>
        ` : ""}
      </div>
    </article>
  `).join("");
}

function renderBilling() {
  const approved = budgets.filter((budget) => budget.status === STATUS.approved);
  const total = approved.reduce((sum, budget) => sum + totalBudget(budget), 0);

  if (!approved.length) {
    $("#billingTable").innerHTML = '<p class="empty">Nenhum orçamento aprovado entrou no fluxo de caixa ainda.</p>';
    return;
  }

  const rows = approved.map((budget) => `
    <tr>
      <td>${escapeHtml(budget.clientName)}</td>
      <td>${escapeHtml(budget.vehicle)} - ${escapeHtml(budget.plate)}</td>
      <td>${currency.format(laborTotal(budget))}</td>
      <td>${currency.format(partsTotal(budget))}</td>
      <td>${currency.format(totalBudget(budget))}</td>
      <td>${dateFormat.format(new Date(budget.approvedAt || budget.createdAt))}</td>
      <td>
        <button class="action" data-action="view" data-id="${budget.id}">Abrir</button>
        ${canAccess("billing_edit") ? `<button class="action" data-action="edit" data-id="${budget.id}">Editar</button>` : ""}
      </td>
    </tr>
  `).join("");

  $("#billingTable").innerHTML = `
    <table>
      <thead>
        <tr>
          <th>Cliente</th>
          <th>Veículo</th>
          <th>Mão de obra</th>
          <th>Peças</th>
          <th>Total</th>
          <th>Aprovado em</th>
          <th>Ações</th>
        </tr>
      </thead>
      <tbody>${rows}</tbody>
      <tfoot>
        <tr>
          <th colspan="4">Total faturado</th>
          <th colspan="3">${currency.format(total)}</th>
        </tr>
      </tfoot>
    </table>
  `;
}

function renderUsersTable() {
  const target = $("#usersTable");
  if (!target) return;
  const accessLevels = accessLevelsConfig();
  const term = ($("#userSearch")?.value || "").toLowerCase().trim();
  const filteredUsers = users.filter((user) => {
    const searchable = [
      user.name,
      user.username,
      user.email,
      user.phone,
      accessLevels[user.accessLevel]
    ].join(" ").toLowerCase();
    return !term || searchable.includes(term);
  });

  if (!filteredUsers.length) {
    target.innerHTML = '<p class="empty">Nenhum usuário cadastrado.</p>';
    return;
  }

  const rows = filteredUsers.map((user) => {
    const isMaster = user.role === "admin";
    const isCurrent = currentUser?.id === user.id;
    return `
    <tr>
      <td>${escapeHtml(user.name)}</td>
      <td>${escapeHtml(user.username || "Não informado")}</td>
      <td>${escapeHtml(user.email)}</td>
      <td>${escapeHtml(user.phone || "Não informado")}</td>
      <td>${accessLevels[user.accessLevel || (user.role === "admin" ? "administrador" : "analista")] || "Analista"}</td>
      <td><span class="badge ${user.blocked ? "reprovado" : "aprovado"}">${user.blocked ? "bloqueado" : "ativo"}</span></td>
      <td>${isMaster ? "MASTER" : "Usuário"}</td>
      <td>
        <div class="actions compact-actions">
          <button class="action" data-user-action="password" data-id="${user.id}">Alterar senha</button>
          ${isMaster ? "" : `<button class="action ${user.blocked ? "success" : "danger"}" data-user-action="toggle-block" data-id="${user.id}">${user.blocked ? "Desbloquear" : "Bloquear"}</button>`}
          ${isMaster || isCurrent ? "" : `<button class="action danger" data-user-action="delete" data-id="${user.id}">Excluir</button>`}
        </div>
      </td>
    </tr>
  `;
  }).join("");

  target.innerHTML = `
    <table>
      <thead>
        <tr>
          <th>Nome</th>
          <th>Nome de usuário</th>
          <th>Email</th>
          <th>Telefone</th>
          <th>Nível de acesso</th>
          <th>Status</th>
          <th>Tipo</th>
          <th>Ações</th>
        </tr>
      </thead>
      <tbody>${rows}</tbody>
    </table>
  `;
}

function renderAccessLevelControls() {
  const select = $("#newUserAccessLevel");
  const list = $("#accessLevelList");
  if (!select || !list) return;

  const accessLevels = accessLevelsConfig();
  select.innerHTML = Object.entries(accessLevels)
    .map(([key, label]) => `<option value="${key}">${escapeHtml(label)}</option>`)
    .join("");

  list.innerHTML = Object.entries(accessLevels)
    .map(([key, label]) => `
      <span class="level-pill">
        ${escapeHtml(label)}
        ${DEFAULT_ACCESS_LEVELS[key] ? "" : '<small>Personalizado</small>'}
      </span>
    `).join("");
}

function renderPermissionMatrix() {
  const target = $("#permissionMatrix");
  if (!target) return;

  const permissions = permissionsConfig();
  target.innerHTML = Object.entries(accessLevelsConfig()).map(([level, label]) => `
    <article class="permission-card">
      <h3>${label}</h3>
      ${Object.entries(PERMISSIONS).map(([feature, featureLabel]) => `
        <label class="check-row">
          <input
            type="checkbox"
            data-level="${level}"
            data-feature="${feature}"
            ${permissions[level]?.includes(feature) ? "checked" : ""}
          >
          <span>${featureLabel}</span>
        </label>
      `).join("")}
    </article>
  `).join("");
}

function readPermissionMatrix() {
  const config = {};
  Object.keys(accessLevelsConfig()).forEach((level) => {
    config[level] = Array.from(document.querySelectorAll(`#permissionMatrix input[data-level="${level}"]:checked`))
      .map((input) => input.dataset.feature);
  });

  return config;
}

function slugifyAccessLevel(value) {
  return value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");
}

function switchSettingsSection(sectionId) {
  document.querySelectorAll(".settings-section").forEach((section) => section.classList.add("hidden"));
  document.querySelectorAll(".side-submenu-button").forEach((button) => button.classList.remove("active"));
  $(`#${sectionId}`).classList.remove("hidden");
  document.querySelector(`[data-settings-section="${sectionId}"]`).classList.add("active");
  $("#pageTitle").textContent = settingsSectionTitle(sectionId);
  $("#settingsSubmenu")?.classList.remove("is-open");
}

function settingsSectionTitle(sectionId = document.querySelector(".side-submenu-button.active")?.dataset.settingsSection) {
  const labels = {
    usersSettings: "Configurações / Usuários",
    accessSettings: "Configurações / Níveis de acesso"
  };
  return labels[sectionId] || "Configurações";
}

function findUserById(id) {
  return users.find((user) => user.id === Number(id));
}

async function toggleUserBlock(id) {
  const user = findUserById(id);
  if (!user || user.role === "admin") return;
  user.blocked = !user.blocked;
  user.updatedAt = new Date().toISOString();
  await updateUser(user);
  await loadAllUsers();
}

async function changeUserPassword(id) {
  const user = findUserById(id);
  if (!user) return;

  const newPassword = prompt(`Digite a nova senha para ${user.name}:`);
  if (!newPassword) return;

  if (newPassword.length < 6) {
    alert("A senha precisa ter pelo menos 6 caracteres.");
    return;
  }

  user.passwordHash = await hashPassword(newPassword);
  user.updatedAt = new Date().toISOString();
  await updateUser(user);
  await loadAllUsers();
}

async function removeUser(id) {
  const user = findUserById(id);
  if (!user || user.role === "admin" || currentUser?.id === user.id) return;

  const confirmed = confirm(`Excluir o usuário ${user.name}? Esta ação não remove orçamentos já cadastrados por ele.`);
  if (!confirmed) return;

  await deleteUser(user.id);
  await loadAllUsers();
}

function emailBudget(budget) {
  const parts = normalizeParts(budget);
  const labor = normalizeLabor(budget);
  const subject = encodeURIComponent(`Orçamento Oficina Pro - ${budget.vehicle}`);
  const body = encodeURIComponent([
    `Olá, ${budget.clientName}.`,
    "",
    "Segue o orçamento solicitado:",
    `Veículo: ${budget.vehicle}`,
    `Placa: ${budget.plate}`,
    budget.clientPhone ? `Telefone: ${budget.clientPhone}` : "",
    budget.clientAddress ? `Endereço: ${budget.clientAddress}` : "",
    "",
    "Peças:",
    ...parts.map((part) => `- ${part.quantity}x ${part.description}: ${currency.format(Number(part.quantity) * Number(part.value))}`),
    `Total em peças: ${currency.format(partsTotal(budget))}`,
    "",
    "Mão de obra:",
    ...labor.map((item) => `- ${item.description}: ${currency.format(Number(item.value))}`),
    `Total em mão de obra: ${currency.format(laborTotal(budget))}`,
    "",
    `Total: ${currency.format(totalBudget(budget))}`,
    "",
    "Status atual: pendente de aprovação.",
    budget.notes ? `Observações: ${budget.notes}` : ""
  ].filter(Boolean).join("\n"));

  window.location.href = `mailto:${budget.clientEmail}?subject=${subject}&body=${body}`;
}

function printBudget(budget) {
  const existing = document.querySelector(".print-page");
  if (existing) {
    existing.remove();
  }

  const template = $("#budgetPrintTemplate").content.cloneNode(true);
  const partsRows = normalizeParts(budget).map((part) => `
    <tr>
      <td>${escapeHtml(part.quantity)}</td>
      <td>${escapeHtml(part.description)}</td>
      <td>${currency.format(Number(part.value))}</td>
      <td>${currency.format(Number(part.quantity) * Number(part.value))}</td>
    </tr>
  `).join("");
  const laborRows = normalizeLabor(budget).map((item) => `
    <tr>
      <td>${escapeHtml(item.description)}</td>
      <td>${currency.format(Number(item.value))}</td>
    </tr>
  `).join("");

  template.querySelector("#printContent").innerHTML = `
    <p><strong>Cliente:</strong> ${escapeHtml(budget.clientName)}</p>
    <p><strong>E-mail:</strong> ${escapeHtml(budget.clientEmail)}</p>
    ${budget.clientPhone ? `<p><strong>Telefone:</strong> ${escapeHtml(budget.clientPhone)}</p>` : ""}
    ${budget.clientAddress ? `<p><strong>Endereço:</strong> ${escapeHtml(budget.clientAddress)}</p>` : ""}
    <p><strong>Veículo:</strong> ${escapeHtml(budget.vehicle)} - ${escapeHtml(budget.plate)}</p>
    <p><strong>Data:</strong> ${dateFormat.format(new Date(budget.createdAt))}</p>
    <p><strong>Status:</strong> ${budget.status}</p>
    <hr>
    <h2>Peças</h2>
    <table>
      <thead>
        <tr>
          <th>Quantidade</th>
          <th>Descrição</th>
          <th>Valor unitário</th>
          <th>Total</th>
        </tr>
      </thead>
      <tbody>${partsRows || '<tr><td colspan="4">Sem peças</td></tr>'}</tbody>
    </table>
    <p><strong>Total em peças:</strong> ${currency.format(partsTotal(budget))}</p>
    <h2>Mão de obra</h2>
    <table>
      <thead>
        <tr>
          <th>Descrição</th>
          <th>Valor</th>
        </tr>
      </thead>
      <tbody>${laborRows || '<tr><td colspan="2">Sem mão de obra</td></tr>'}</tbody>
    </table>
    <p><strong>Total em mão de obra:</strong> ${currency.format(laborTotal(budget))}</p>
    <h2>Total: ${currency.format(totalBudget(budget))}</h2>
    ${budget.notes ? `<p><strong>Observações:</strong> ${escapeHtml(budget.notes)}</p>` : ""}
    <p>Este orçamento fica pendente até a aprovação do cliente.</p>
  `;
  document.body.appendChild(template);
  window.onafterprint = () => document.querySelector(".print-page")?.remove();
  window.print();
}

async function changeBudgetStatus(id, status) {
  const budget = budgets.find((item) => item.id === Number(id));
  if (!budget) return;

  budget.status = status;
  budget.updatedAt = new Date().toISOString();
  if (status === STATUS.approved) {
    budget.approvedAt = budget.updatedAt;
  }

  await updateBudget(budget);
  await loadBudgets();
}

function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function createPartRow(part = { quantity: 1, description: "", value: "" }) {
  const row = document.createElement("div");
  row.className = "line-grid part-row";
  row.innerHTML = `
    <input class="part-quantity" type="number" min="1" step="1" value="${escapeHtml(part.quantity || 1)}">
    <input class="part-description" type="text" value="${escapeHtml(part.description)}" placeholder="Ex: Pastilha de freio">
    <input class="part-value" type="number" min="0" step="0.01" value="${escapeHtml(part.value)}">
    <button type="button" class="remove-line" title="Remover peça">×</button>
  `;
  return row;
}

function createLaborRow(item = { description: "", value: "" }) {
  const row = document.createElement("div");
  row.className = "line-grid labor-grid labor-row";
  row.innerHTML = `
    <input class="labor-description" type="text" value="${escapeHtml(item.description)}" placeholder="Ex: Troca de embreagem">
    <input class="labor-value" type="number" min="0" step="0.01" value="${escapeHtml(item.value)}">
    <button type="button" class="remove-line" title="Remover serviço">×</button>
  `;
  return row;
}

function addPartRow(part) {
  $("#partsRows").appendChild(createPartRow(part));
  updateBudgetPreview();
}

function addLaborRow(item) {
  $("#laborRows").appendChild(createLaborRow(item));
  updateBudgetPreview();
}

function readPartRows() {
  return Array.from(document.querySelectorAll(".part-row"))
    .map((row) => ({
      quantity: Number(row.querySelector(".part-quantity").value || 0),
      description: row.querySelector(".part-description").value.trim(),
      value: Number(row.querySelector(".part-value").value || 0)
    }))
    .filter((part) => part.quantity > 0 && part.description && part.value > 0);
}

function readLaborRows() {
  return Array.from(document.querySelectorAll(".labor-row"))
    .map((row) => ({
      description: row.querySelector(".labor-description").value.trim(),
      value: Number(row.querySelector(".labor-value").value || 0)
    }))
    .filter((item) => item.description && item.value > 0);
}

function hasIncompleteRows() {
  const incompletePart = Array.from(document.querySelectorAll(".part-row")).some((row) => {
    const quantity = Number(row.querySelector(".part-quantity").value || 0);
    const description = row.querySelector(".part-description").value.trim();
    const value = Number(row.querySelector(".part-value").value || 0);
    const touched = description || value > 0;
    return touched && (!description || quantity <= 0 || value <= 0);
  });

  const incompleteLabor = Array.from(document.querySelectorAll(".labor-row")).some((row) => {
    const description = row.querySelector(".labor-description").value.trim();
    const value = Number(row.querySelector(".labor-value").value || 0);
    const touched = description || value > 0;
    return touched && (!description || value <= 0);
  });

  return incompletePart || incompleteLabor;
}

function updateBudgetPreview() {
  const parts = readPartRows();
  const labor = readLaborRows();
  const partsValue = parts.reduce((sum, part) => sum + (part.quantity * part.value), 0);
  const laborValue = labor.reduce((sum, item) => sum + item.value, 0);

  $("#partsPreview").textContent = currency.format(partsValue);
  $("#laborPreview").textContent = currency.format(laborValue);
  $("#budgetPreview").textContent = currency.format(partsValue + laborValue);
}

function resetBudgetItems() {
  $("#partsRows").innerHTML = "";
  $("#laborRows").innerHTML = "";
  addPartRow();
  addLaborRow();
}

function findBudgetById(id) {
  return budgets.find((item) => item.id === Number(id));
}

function setFormMode(budget = null) {
  editingBudgetId = budget?.id || null;
  $("#budgetFormTitle").textContent = budget ? "Editar orçamento" : "Criar orçamento";
  $("#saveBudgetButton").textContent = budget ? "Salvar alterações como pendente" : "Salvar como pendente";
  $("#cancelEditButton").classList.toggle("hidden", !budget);
}

function clearBudgetForm() {
  $("#budgetForm").reset();
  resetBudgetItems();
  setFormMode();
}

function loadBudgetIntoForm(budget) {
  $("#clientName").value = budget.clientName || "";
  $("#clientEmail").value = budget.clientEmail || "";
  $("#clientPhone").value = budget.clientPhone || "";
  $("#clientAddress").value = budget.clientAddress || "";
  $("#vehicle").value = budget.vehicle || "";
  $("#plate").value = budget.plate || "";
  $("#notes").value = budget.notes || "";
  $("#partsRows").innerHTML = "";
  $("#laborRows").innerHTML = "";
  normalizeParts(budget).forEach((part) => addPartRow(part));
  normalizeLabor(budget).forEach((item) => addLaborRow(item));
  if (!document.querySelector(".part-row")) addPartRow();
  if (!document.querySelector(".labor-row")) addLaborRow();
  updateBudgetPreview();
  setFormMode(budget);
  switchView("budgetView");
  $("#clientName").focus();
}

function beginBudgetEdit(budget) {
  if (!canAccess("budgets_manage") && !canAccess("billing_edit")) return;

  if (budget.status === STATUS.approved) {
    const canEdit = confirm("Este orçamento já foi aprovado e está no financeiro. Ao alterar o orçamento, ele voltará para o status pendente e será necessário solicitar nova aprovação do cliente.");
    if (!canEdit) return;
  }

  closeBudgetModal();
  loadBudgetIntoForm(budget);
}

function openBudgetModal(budget) {
  selectedBudgetId = budget.id;
  $("#budgetModalContent").innerHTML = renderBudgetDetail(budget);
  $("#modalEditButton").classList.toggle("hidden", !(canAccess("budgets_manage") || canAccess("billing_edit")));
  $("#budgetModal").classList.remove("hidden");
}

function closeBudgetModal() {
  selectedBudgetId = null;
  $("#budgetModal").classList.add("hidden");
  $("#budgetModalContent").innerHTML = "";
}

function selectedBudget() {
  return selectedBudgetId ? findBudgetById(selectedBudgetId) : null;
}

function markParentMenu(feature) {
  document.querySelectorAll(".nav-button").forEach((button) => button.classList.remove("active"));
  document.querySelector(`[data-menu-parent="${feature}"]`)?.classList.add("active");
}

function suppressClickedSubmenu(sourceElement) {
  sourceElement?.closest(".nav-group")?.classList.add("suppress-submenu");
}

function openBudgetSection(section, sourceElement = null) {
  switchView("budgetView");
  markParentMenu("budgets");

  const isNew = section === "new";
  compactBudgetList = !isNew;
  const labels = {
    new: "Atendimento / Orçamentos / Novo orçamento",
    aprovado: "Atendimento / Orçamentos / Aprovados",
    reprovado: "Atendimento / Orçamentos / Reprovados",
    pendente: "Atendimento / Orçamentos / Pendentes"
  };
  const listTitles = {
    new: "Orçamentos cadastrados",
    aprovado: "Orçamentos aprovados",
    reprovado: "Orçamentos reprovados",
    pendente: "Orçamentos pendentes"
  };

  $("#pageTitle").textContent = labels[section] || labels.new;
  $("#budgetListTitle").textContent = listTitles[section] || listTitles.new;
  $("#statusFilter").value = isNew ? "todos" : section;
  $("#budgetSearch").value = "";
  $("#budgetSearchWrap").classList.toggle("hidden", isNew);
  $("#budgetList").classList.toggle("budget-list", isNew);
  $("#budgetForm").classList.toggle("hidden", !isNew || !canAccess("budgets_manage"));
  $("#newBudgetButton").classList.toggle("hidden", !isNew || !canAccess("budgets_manage"));
  $("#budgetLayout").classList.toggle("list-only", !isNew || !canAccess("budgets_manage"));
  renderBudgetList();
  suppressClickedSubmenu(sourceElement);
}

function openFinanceSection(section, sourceElement = null) {
  const views = {
    payable: "accountsPayableView",
    costs: "costTableView",
    cashflow: "billingView"
  };
  switchView(views[section] || "billingView");
  markParentMenu("billing");
  suppressClickedSubmenu(sourceElement);
}

function bindEvents() {
  $("#showRegister").addEventListener("click", () => {
    $("#loginForm").classList.add("hidden");
    $("#registerForm").classList.remove("hidden");
  });

  $("#showLogin").addEventListener("click", () => {
    $("#registerForm").classList.add("hidden");
    $("#loginForm").classList.remove("hidden");
  });

  $("#registerForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const email = $("#registerEmail").value.toLowerCase().trim();
    const existing = await findUserByEmail(email);

    if (existing) {
      setMessage($("#registerMessage"), "Ja existe um usuario com este e-mail.");
      return;
    }

    const user = {
      name: $("#registerName").value.trim(),
      email,
      passwordHash: await hashPassword($("#registerPassword").value),
      role: "user",
      accessLevel: "analista",
      createdAt: new Date().toISOString()
    };

    await createUser(user);
    $("#registerForm").reset();
    $("#loginEmail").value = email;
    $("#loginPassword").value = "";
    $("#registerForm").classList.add("hidden");
    $("#loginForm").classList.remove("hidden");
    setMessage($("#loginMessage"), "Usuario cadastrado. Digite sua senha para entrar.", true);
  });

  $("#loginForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const user = await findUserByEmail($("#loginEmail").value);
    const passwordHash = await hashPassword($("#loginPassword").value);

  if (!user || user.passwordHash !== passwordHash) {
      setMessage($("#loginMessage"), "E-mail ou senha invalidos.");
      return;
    }

    if (user.blocked) {
      setMessage($("#loginMessage"), "Este usuário está bloqueado. Procure o administrador.");
      return;
    }

    currentUser = {
      id: user.id,
      name: user.name,
      email: user.email,
      phone: user.phone || "",
      role: user.role || "user",
      accessLevel: user.accessLevel || (user.role === "admin" ? "administrador" : "analista")
    };
    sessionStorage.setItem("oficina_user", JSON.stringify(currentUser));
    showApp();
  });

  $("#logoutButton").addEventListener("click", showAuth);

  document.querySelectorAll(".nav-button").forEach((button) => {
    button.addEventListener("click", () => {
      if (button.dataset.menuParent) {
        return;
      }

      document.querySelectorAll(".nav-group").forEach((group) => group.classList.remove("suppress-submenu"));
      switchView(button.dataset.view);
    });
  });
  document.querySelectorAll(".nav-group").forEach((group) => group.addEventListener("mouseleave", (event) => {
    event.currentTarget.classList.remove("suppress-submenu");
  }));

  $("#newBudgetButton").addEventListener("click", () => openBudgetSection("new"));
  $("#cancelEditButton").addEventListener("click", clearBudgetForm);
  $("#statusFilter").addEventListener("change", renderBudgetList);
  $("#budgetSearch").addEventListener("input", renderBudgetList);
  $("#addPartButton").addEventListener("click", () => addPartRow());
  $("#addLaborButton").addEventListener("click", () => addLaborRow());
  document.querySelectorAll("[data-budget-section]").forEach((button) => {
    button.addEventListener("click", () => openBudgetSection(button.dataset.budgetSection, button));
  });
  document.querySelectorAll("[data-finance-section]").forEach((button) => {
    button.addEventListener("click", () => openFinanceSection(button.dataset.financeSection, button));
  });
  document.querySelectorAll(".side-submenu-button").forEach((button) => {
    if (!button.dataset.settingsSection) return;
    button.addEventListener("click", () => {
      switchView("settingsView");
      switchSettingsSection(button.dataset.settingsSection);
      suppressClickedSubmenu(button);
    });
  });
  $("#userSearch").addEventListener("input", renderUsersTable);
  $("#usersTable").addEventListener("click", async (event) => {
    const button = event.target.closest("button[data-user-action]");
    if (!button || !canAccess("settings")) return;

    if (button.dataset.userAction === "toggle-block") await toggleUserBlock(button.dataset.id);
    if (button.dataset.userAction === "password") await changeUserPassword(button.dataset.id);
    if (button.dataset.userAction === "delete") await removeUser(button.dataset.id);
  });
  $("#savePermissionsButton").addEventListener("click", () => {
    if (!canAccess("settings")) return;
    savePermissionsConfig(readPermissionMatrix());
    setMessage($("#permissionsMessage"), "Permissões salvas com sucesso.", true);
    applyNavigationPermissions();
  });

  $("#accessLevelForm").addEventListener("submit", (event) => {
    event.preventDefault();
    if (!canAccess("settings")) return;

    const label = $("#accessLevelName").value.trim();
    const key = slugifyAccessLevel(label);
    const accessLevels = accessLevelsConfig();

    if (!key) {
      setMessage($("#accessLevelMessage"), "Informe um nome válido para o nível.");
      return;
    }

    if (accessLevels[key]) {
      setMessage($("#accessLevelMessage"), "Já existe um nível de acesso com este nome.");
      return;
    }

    accessLevels[key] = label;
    saveAccessLevelsConfig(accessLevels);

    const permissions = permissionsConfig();
    permissions[key] = ["dashboard_view"];
    savePermissionsConfig(permissions);

    $("#accessLevelForm").reset();
    setMessage($("#accessLevelMessage"), "Nível de acesso criado. Ajuste as permissões abaixo.", true);
    renderAccessLevelControls();
    renderPermissionMatrix();
  });

  $("#userCreateForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!canAccess("settings")) return;

    const email = $("#newUserEmail").value.toLowerCase().trim();
    const username = $("#newUsername").value.trim().toLowerCase();
    const existing = await findUserByEmail(email);
    if (existing) {
      setMessage($("#userCreateMessage"), "Já existe um usuário com este email.");
      return;
    }

    users = await requestToPromise(store("users").getAll());
    const usernameExists = users.some((user) => String(user.username || "").toLowerCase() === username);
    if (usernameExists) {
      setMessage($("#userCreateMessage"), "Já existe um usuário com este nome de usuário.");
      return;
    }

    const accessLevel = $("#newUserAccessLevel").value;
    await createUser({
      name: $("#newUserName").value.trim(),
      username,
      email,
      phone: $("#newUserPhone").value.trim(),
      passwordHash: await hashPassword($("#newUserPassword").value),
      role: accessLevel === "administrador" ? "admin-user" : "user",
      accessLevel,
      blocked: false,
      createdAt: new Date().toISOString()
    });

    $("#userCreateForm").reset();
    setMessage($("#userCreateMessage"), "Usuário criado com a senha padrão informada.", true);
    await loadAllUsers();
  });

  $("#budgetForm").addEventListener("input", (event) => {
    if (event.target.matches(".part-quantity, .part-value, .labor-value, .part-description, .labor-description")) {
      updateBudgetPreview();
    }
  });

  $("#budgetForm").addEventListener("click", (event) => {
    const button = event.target.closest(".remove-line");
    if (!button) return;

    const rowsContainer = button.closest(".line-rows");
    button.closest(".line-grid").remove();

    if (rowsContainer.id === "partsRows" && !document.querySelector(".part-row")) addPartRow();
    if (rowsContainer.id === "laborRows" && !document.querySelector(".labor-row")) addLaborRow();
    updateBudgetPreview();
  });

  $("#budgetForm").addEventListener("reset", () => {
    setTimeout(() => {
      resetBudgetItems();
      updateBudgetPreview();
    }, 0);
  });

  $("#budgetForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    if (hasIncompleteRows()) {
      alert("Complete a descrição e o valor dos itens preenchidos antes de salvar.");
      return;
    }

    const parts = readPartRows();
    const labor = readLaborRows();

    if (!parts.length && !labor.length) {
      alert("Adicione pelo menos uma peça ou um serviço de mão de obra.");
      return;
    }

    const partsValue = parts.reduce((sum, part) => sum + (part.quantity * part.value), 0);
    const laborValue = labor.reduce((sum, item) => sum + item.value, 0);

    const originalBudget = editingBudgetId ? findBudgetById(editingBudgetId) : null;
    const now = new Date().toISOString();
    const budget = {
      ...(originalBudget || {}),
      userId: originalBudget?.userId || currentUser.id,
      clientName: $("#clientName").value.trim(),
      clientEmail: $("#clientEmail").value.toLowerCase().trim(),
      clientPhone: $("#clientPhone").value.trim(),
      clientAddress: $("#clientAddress").value.trim(),
      vehicle: $("#vehicle").value.trim(),
      plate: $("#plate").value.trim().toUpperCase(),
      parts,
      labor,
      description: "",
      laborValue,
      partsValue,
      notes: $("#notes").value.trim(),
      status: STATUS.pending,
      createdAt: originalBudget?.createdAt || now,
      updatedAt: now
    };
    delete budget.approvedAt;

    if (originalBudget) {
      await updateBudget(budget);
    } else {
      await saveBudget(budget);
    }

    clearBudgetForm();
    await loadBudgets();
  });

  $("#budgetList").addEventListener("click", async (event) => {
    const button = event.target.closest("button[data-action]");
    if (!button) return;

    const budget = budgets.find((item) => item.id === Number(button.dataset.id));
    if (!budget) return;

    if (button.dataset.action === "view") openBudgetModal(budget);
    if (button.dataset.action === "edit" && canAccess("budgets_manage")) beginBudgetEdit(budget);
    if (button.dataset.action === "email") emailBudget(budget);
    if (button.dataset.action === "print") printBudget(budget);
    if (button.dataset.action === "approve" && canAccess("budgets_approve")) await changeBudgetStatus(button.dataset.id, STATUS.approved);
    if (button.dataset.action === "reject" && canAccess("budgets_approve")) await changeBudgetStatus(button.dataset.id, STATUS.rejected);
  });

  $("#billingTable").addEventListener("click", (event) => {
    const button = event.target.closest("button[data-action]");
    if (!button) return;

    const budget = findBudgetById(button.dataset.id);
    if (!budget) return;

    if (button.dataset.action === "view") openBudgetModal(budget);
    if (button.dataset.action === "edit" && canAccess("billing_edit")) beginBudgetEdit(budget);
  });

  $("#closeBudgetModal").addEventListener("click", closeBudgetModal);
  $("#budgetModal").addEventListener("click", (event) => {
    if (event.target.id === "budgetModal") closeBudgetModal();
  });
  $("#modalEmailButton").addEventListener("click", () => {
    const budget = selectedBudget();
    if (budget) emailBudget(budget);
  });
  $("#modalPrintButton").addEventListener("click", () => {
    const budget = selectedBudget();
    if (budget) printBudget(budget);
  });
  $("#modalEditButton").addEventListener("click", () => {
    const budget = selectedBudget();
    if (budget && (canAccess("budgets_manage") || canAccess("billing_edit"))) beginBudgetEdit(budget);
  });
}

async function init() {
  db = await openDatabase();
  await ensureMasterUser();
  bindEvents();
  resetBudgetItems();

  const sessionUser = sessionStorage.getItem("oficina_user");
  if (sessionUser) {
    currentUser = JSON.parse(sessionUser);
    showApp();
  }
}

init().catch((error) => {
  console.error(error);
  alert("Nao foi possivel iniciar o banco de dados local.");
});
