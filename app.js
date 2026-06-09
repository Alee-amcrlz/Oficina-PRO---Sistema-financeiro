const API_BASE = "/api";
const STATUS = {
  pending: "pendente",
  approved: "aprovado",
  rejected: "reprovado"
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
  budgets_delete: "Excluir orçamentos",
  inventory_view: "Visualizar estoque",
  inventory_manage: "Cadastrar e excluir peças",
  billing_view: "Visualizar financeiro",
  billing_edit: "Editar orçamentos pelo financeiro"
};
const DEFAULT_PERMISSIONS = {
  administrador: ["dashboard_view", "budgets_view", "budgets_manage", "budgets_approve", "budgets_delete", "inventory_view", "inventory_manage", "billing_view", "billing_edit"],
  financeiro: ["dashboard_view", "billing_view"],
  analista: ["dashboard_view", "budgets_view", "budgets_manage"]
};
const FEATURE_ALIASES = {
  dashboard: "dashboard_view",
  budgets: "budgets_view",
  inventory: "inventory_view",
  billing: "billing_view",
  platform: "platform"
};
const VIEW_TITLES = {
  dashboardView: "Painel",
  platformView: "Painel Master",
  budgetView: "Atendimento / Orçamentos",
  customersView: "Atendimento / Clientes e veículos",
  serviceOrdersView: "Atendimento / Ordens de serviço",
  billingView: "Financeiro / Fluxo de caixa",
  accountsPayableView: "Financeiro / Contas à pagar",
  costTableView: "Financeiro / Tabela de custos",
  inventoryView: "Gerenciamento de Estoque / Cadastro de peças",
  settingsView: "Configurações"
};
const REMEMBER_LOGIN_KEY = "oficina_remember_login";
const UI_PREFERENCES_KEY = "oficina_ui_preferences";
const SESSION_TOKEN_KEY = "oficina_session_token";
const PLAN_FEATURE_BY_PERMISSION = {
  dashboard_view: "dashboard",
  budgets_view: "budgets",
  budgets_manage: "budgets",
  budgets_approve: "budgets",
  budgets_delete: "budgets",
  billing_view: "billing",
  billing_edit: "billing",
  inventory_view: "inventory",
  inventory_manage: "inventory",
  settings: "users"
};

let currentUser = null;
let budgets = [];
let customers = [];
let vehicles = [];
let serviceOrders = [];
let inventoryParts = [];
let suppliers = [];
let payables = [];
let platformCompanies = [];
let platformSubscriptions = [];
let platformPayments = [];
let platformAudit = [];
let planCatalog = {};
let billingCycles = {};
let selectedInventoryPartId = null;
let selectedSupplierId = null;
let users = [];
let editingUserId = null;
let accessLevelsState = { ...DEFAULT_ACCESS_LEVELS };
let permissionsState = structuredClone(DEFAULT_PERMISSIONS);
let editingBudgetId = null;
let editingCustomerId = null;
let editingVehicleId = null;
let selectedBudgetId = null;
let compactBudgetList = false;
let lastZipLookup = "";
let clockTimer = null;
let uiPreferences = {
  sidebarCollapsed: false,
  darkMode: false
};

const currency = new Intl.NumberFormat("pt-BR", {
  style: "currency",
  currency: "BRL"
});

const dateFormat = new Intl.DateTimeFormat("pt-BR");

const $ = (selector) => document.querySelector(selector);

async function api(path, options = {}) {
  const token = sessionStorage.getItem(SESSION_TOKEN_KEY);
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options.headers || {})
    }
  });

  const data = await response.json();
  if (response.status === 401 && !["/auth/login", "/health"].includes(path)) {
    showAuth();
  }
  if (!response.ok) {
    throw new Error(data?.error || "Erro ao acessar o banco de dados local.");
  }
  return data;
}

async function createUser(user) {
  return api("/users", {
    method: "POST",
    body: JSON.stringify(user)
  });
}

async function updateUser(user) {
  return api(`/users/${user.id}`, {
    method: "PUT",
    body: JSON.stringify(user)
  });
}

async function deleteUser(id) {
  return api(`/users/${Number(id)}`, { method: "DELETE" });
}

async function loadAllUsers() {
  users = await api("/users");
  users.sort((a, b) => String(a.name).localeCompare(String(b.name), "pt-BR"));
  renderUsersTable();
}

async function findUserByEmail(email) {
  return api(`/users/by-email?email=${encodeURIComponent(String(email).toLowerCase().trim())}`);
}

async function loginUser(login, password) {
  return api("/auth/login", {
    method: "POST",
    body: JSON.stringify({ login, password })
  });
}

async function saveBudget(budget) {
  return api("/budgets", {
    method: "POST",
    body: JSON.stringify(budget)
  });
}

async function updateBudget(budget) {
  return api(`/budgets/${budget.id}`, {
    method: "PUT",
    body: JSON.stringify(budget)
  });
}

async function deleteBudget(id) {
  return api(`/budgets/${Number(id)}`, { method: "DELETE" });
}

async function createCustomer(customer) {
  return api("/customers", {
    method: "POST",
    body: JSON.stringify(customer)
  });
}

async function updateCustomer(customer) {
  return api(`/customers/${Number(customer.id)}`, {
    method: "PUT",
    body: JSON.stringify(customer)
  });
}

async function createVehicle(vehicle) {
  return api("/vehicles", {
    method: "POST",
    body: JSON.stringify(vehicle)
  });
}

async function updateVehicle(vehicle) {
  return api(`/vehicles/${Number(vehicle.id)}`, {
    method: "PUT",
    body: JSON.stringify(vehicle)
  });
}

async function createServiceOrderFromBudget(budgetId) {
  return api("/service-orders/from-budget", {
    method: "POST",
    body: JSON.stringify({ budgetId: Number(budgetId) })
  });
}

async function updateServiceOrder(serviceOrder) {
  return api(`/service-orders/${Number(serviceOrder.id)}`, {
    method: "PUT",
    body: JSON.stringify(serviceOrder)
  });
}

async function createInventoryPart(part) {
  return api("/parts", {
    method: "POST",
    body: JSON.stringify(part)
  });
}

async function updateInventoryPart(part) {
  return api(`/parts/${Number(part.id)}`, {
    method: "PUT",
    body: JSON.stringify(part)
  });
}

async function deleteInventoryPart(id) {
  return api(`/parts/${Number(id)}`, { method: "DELETE" });
}

async function createSupplier(supplier) {
  return api("/suppliers", {
    method: "POST",
    body: JSON.stringify(supplier)
  });
}

async function createPayable(payable) {
  return api("/payables", {
    method: "POST",
    body: JSON.stringify(payable)
  });
}

async function createPlatformCompany(company) {
  return api("/platform/companies", {
    method: "POST",
    body: JSON.stringify(company)
  });
}

async function updatePlatformSubscription(subscription) {
  return api(`/platform/subscriptions/${Number(subscription.id)}`, {
    method: "PUT",
    body: JSON.stringify(subscription)
  });
}

async function createPlatformPayment(payment) {
  return api("/platform/payments", {
    method: "POST",
    body: JSON.stringify(payment)
  });
}

async function loadPlatformAudit() {
  platformAudit = await api("/platform/audit?limit=30");
}

async function loadPlanCatalog() {
  const data = await api("/plans");
  planCatalog = Object.fromEntries((data.plans || []).map((plan) => [plan.code, plan]));
  billingCycles = data.billingCycles || {};
}

async function loadCurrentSubscription() {
  const subscription = await api("/subscription/current");
  currentUser = {
    ...currentUser,
    subscriptionStatus: subscription.status,
    plan: subscription.plan,
    currentPeriodStart: subscription.currentPeriodStart,
    currentPeriodEnd: subscription.currentPeriodEnd,
    trialEndsAt: subscription.trialEndsAt
  };
  sessionStorage.setItem("oficina_user", JSON.stringify(currentUser));
  renderSubscriptionSummary();
}

async function loadBudgets() {
  const all = await api("/budgets");
  const visibleBudgets = canAccess("billing_view")
    ? all
    : all.filter((budget) => budget.userId === currentUser.id);

  budgets = visibleBudgets
    .sort((a, b) => new Date(b.createdAt) - new Date(a.createdAt));
  renderAll();
}

async function loadCustomers() {
  customers = await api("/customers");
  vehicles = await api("/vehicles");
  renderBudgetCustomerOptions();
  renderCustomersView();
}

async function loadServiceOrders() {
  serviceOrders = await api("/service-orders");
  renderServiceOrdersView();
}

async function loadInventoryParts() {
  inventoryParts = await api("/parts");
  renderInventoryPartsTable();
}

async function loadSuppliers() {
  suppliers = await api("/suppliers");
}

async function loadPayables() {
  payables = await api("/payables?limit=5");
  renderLatestPayables();
}

async function loadPlatformDashboard() {
  if (!canAccess("platform")) return;
  [platformCompanies, platformSubscriptions, platformPayments, platformAudit] = await Promise.all([
    api("/platform/companies"),
    api("/platform/subscriptions"),
    api("/platform/payments"),
    api("/platform/audit?limit=30")
  ]);
  renderPlatformDashboard();
}

async function loadSettings() {
  const [savedAccessLevels, savedPermissions] = await Promise.all([
    api("/settings/accessLevels"),
    api("/settings/permissions")
  ]);

  accessLevelsState = { ...DEFAULT_ACCESS_LEVELS, ...(savedAccessLevels || {}) };
  permissionsState = { ...DEFAULT_PERMISSIONS, ...(savedPermissions || {}) };
}

function setMessage(element, text, isSuccess = false) {
  element.textContent = text;
  element.style.color = isSuccess ? "var(--success)" : "var(--danger)";
}

function setPageTitle(title = "Painel") {
  const normalizedTitle = title || "Painel";
  $("#pageTitle").textContent = normalizedTitle;
  document.title = `${normalizedTitle.replace(/\s*\/\s*/g, " - ")} | Oficina Pro`;
}

function loadRememberedLogin() {
  try {
    const remembered = JSON.parse(localStorage.getItem(REMEMBER_LOGIN_KEY));
    if (!remembered?.email) return;

    $("#loginEmail").value = remembered.email;
    $("#rememberLogin").checked = true;
  } catch {
    localStorage.removeItem(REMEMBER_LOGIN_KEY);
  }
}

function updateRememberedLogin(email) {
  if (!$("#rememberLogin").checked) {
    localStorage.removeItem(REMEMBER_LOGIN_KEY);
    return;
  }

  localStorage.setItem(REMEMBER_LOGIN_KEY, JSON.stringify({ email }));
}

function loadUiPreferences() {
  try {
    uiPreferences = {
      ...uiPreferences,
      ...(JSON.parse(localStorage.getItem(UI_PREFERENCES_KEY)) || {})
    };
  } catch {
    localStorage.removeItem(UI_PREFERENCES_KEY);
  }
  applyUiPreferences();
}

function saveUiPreferences() {
  localStorage.setItem(UI_PREFERENCES_KEY, JSON.stringify(uiPreferences));
}

function applyUiPreferences() {
  $("#appView")?.classList.toggle("dark-mode", uiPreferences.darkMode);
  $("#appView")?.classList.toggle("sidebar-collapsed", uiPreferences.sidebarCollapsed);

  const sidebarButton = $("#toggleSidebarButton");
  if (sidebarButton) {
    sidebarButton.title = uiPreferences.sidebarCollapsed ? "Expandir painel" : "Recolher painel";
    sidebarButton.setAttribute("aria-label", sidebarButton.title);
    sidebarButton.setAttribute("aria-expanded", String(!uiPreferences.sidebarCollapsed));
    sidebarButton.textContent = uiPreferences.sidebarCollapsed ? "→" : "←";
  }

  const themeButton = $("#toggleThemeButton");
  if (themeButton) {
    themeButton.title = uiPreferences.darkMode ? "Usar modo claro" : "Usar modo escuro";
    themeButton.setAttribute("aria-label", themeButton.title);
    themeButton.setAttribute("aria-pressed", String(uiPreferences.darkMode));
    themeButton.textContent = uiPreferences.darkMode ? "☀" : "◐";
  }
}

function toggleSidebar() {
  uiPreferences.sidebarCollapsed = !uiPreferences.sidebarCollapsed;
  applyUiPreferences();
  saveUiPreferences();
}

function toggleTheme() {
  uiPreferences.darkMode = !uiPreferences.darkMode;
  applyUiPreferences();
  saveUiPreferences();
}

async function showApp() {
  $("#authView").classList.add("hidden");
  $("#appView").classList.remove("hidden");
  $("#userName").textContent = isMasterUser()
    ? `${currentUser.name} - ADMIN`
    : currentUser.name;
  applyUiPreferences();
  startSidebarClock();
  await loadPlanCatalog();
  await loadCurrentSubscription();
  await loadSettings();
  applyNavigationPermissions();
  setPageTitle("Painel");
  if (canAccess("inventory")) {
    loadInventoryParts();
    loadSuppliers();
  }
  if (canAccess("billing")) {
    loadPayables();
  }
  if (canAccess("budgets")) {
    loadBudgets();
    loadCustomers();
    loadServiceOrders();
  }
  if (canAccess("platform")) {
    loadPlatformDashboard();
  }
  if (canAccess("settings")) {
    loadAllUsers();
    renderPermissionMatrix();
    renderAccessLevelControls();
  }
}

function showAuth() {
  currentUser = null;
  sessionStorage.removeItem("oficina_user");
  sessionStorage.removeItem(SESSION_TOKEN_KEY);
  $("#appView").classList.add("hidden");
  $("#authView").classList.remove("hidden");
  document.title = "Entrar | Oficina Pro";
}

function formatSidebarClock(date = new Date()) {
  const pad = (value) => String(value).padStart(2, "0");
  const day = pad(date.getDate());
  const month = pad(date.getMonth() + 1);
  const year = String(date.getFullYear()).slice(-2);
  const hours = pad(date.getHours());
  const minutes = pad(date.getMinutes());
  const seconds = pad(date.getSeconds());
  return `${day}/${month}/${year} ${hours}:${minutes}:${seconds}`;
}

function sidebarGreeting(date = new Date()) {
  const hour = date.getHours();
  if (hour < 12) return "Bom dia";
  if (hour < 18) return "Boa tarde";
  return "Boa noite";
}

function startSidebarClock() {
  const clock = $("#sidebarClock");
  const greeting = $("#sidebarGreeting");
  if (!clock) return;

  const tick = () => {
    const now = new Date();
    clock.textContent = formatSidebarClock(now);
    if (greeting) greeting.textContent = sidebarGreeting(now);
  };
  tick();
  if (!clockTimer) {
    clockTimer = setInterval(tick, 1000);
  }
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

  setPageTitle(viewId === "settingsView" ? settingsSectionTitle() : VIEW_TITLES[viewId]);
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

  if (viewId === "platformView") {
    loadPlatformDashboard();
  }

  if (viewId === "customersView") {
    loadCustomers();
  }

  if (viewId === "serviceOrdersView") {
    loadServiceOrders();
  }
}

function currentAccessLevel() {
  if (!currentUser) return "analista";
  if (currentUser.role === "admin") return "administrador";
  return currentUser.accessLevel || "analista";
}

function isMasterUser() {
  return Boolean(currentUser?.isPlatformAdmin);
}

function currentPlan() {
  return currentUser?.plan || planCatalog[currentUser?.subscriptionPlan] || planCatalog.trial || {
    code: "trial",
    name: "Teste",
    features: ["dashboard", "budgets"],
    limits: { users: 1 },
    prices: {}
  };
}

function subscriptionAllowsWrite() {
  if (currentUser?.isPlatformAdmin) return true;
  return ["trial", "active"].includes(currentUser?.subscriptionStatus);
}

function planAllows(feature) {
  if (currentUser?.isPlatformAdmin) return true;
  const mapped = PLAN_FEATURE_BY_PERMISSION[feature] || FEATURE_ALIASES[feature] || feature;
  return (currentPlan().features || []).includes(mapped);
}

function accessLevelsConfig() {
  return { ...DEFAULT_ACCESS_LEVELS, ...(accessLevelsState || {}) };
}

function saveAccessLevelsConfig(config) {
  accessLevelsState = { ...config };
  api("/settings/accessLevels", {
    method: "PUT",
    body: JSON.stringify(accessLevelsState)
  }).catch((error) => console.error(error));
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
  const accessLevels = accessLevelsConfig();
  const saved = permissionsState || {};
  const config = {};
  Object.keys(accessLevels).forEach((level) => {
    config[level] = normalizePermissionList(saved?.[level] || DEFAULT_PERMISSIONS[level] || []);
    if (level === "administrador" && !config[level].includes("budgets_delete")) {
      config[level].push("budgets_delete");
    }
    if (level === "administrador") {
      ["inventory_view", "inventory_manage"].forEach((permission) => {
        if (!config[level].includes(permission)) config[level].push(permission);
      });
    }
  });
  return config;
}

function savePermissionsConfig(config) {
  permissionsState = { ...config };
  api("/settings/permissions", {
    method: "PUT",
    body: JSON.stringify(permissionsState)
  }).catch((error) => console.error(error));
}

function canAccess(feature) {
  if (!currentUser) return false;
  if (feature === "platform") return Boolean(currentUser.isPlatformAdmin);
  if (!planAllows(feature)) return false;
  if (feature === "settings") return currentUser.role === "admin";
  if (currentUser.role === "admin") return true;
  const normalizedFeature = FEATURE_ALIASES[feature] || feature;
  if (!planAllows(normalizedFeature)) return false;
  return permissionsConfig()[currentAccessLevel()]?.includes(normalizedFeature) || false;
}

function canApproveBudget(budget) {
  if (!budget || budget.status !== STATUS.pending) return false;
  return canAccess("budgets_approve") || (canAccess("budgets_manage") && budget.userId === currentUser?.id);
}

function canDeleteBudget(budget) {
  return Boolean(budget) && canAccess("budgets_delete");
}

function canGenerateServiceOrder(budget) {
  return Boolean(budget) && budget.status === STATUS.approved && canAccess("budgets_manage");
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
      id: part.id ? Number(part.id) : null,
      quantity: Number(part.quantity || 0),
      code: part.code || "",
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

function isDateInCurrentMonth(value) {
  const date = new Date(value);
  const now = new Date();

  return !Number.isNaN(date.getTime())
    && date.getFullYear() === now.getFullYear()
    && date.getMonth() === now.getMonth();
}

function budgetBillingDate(budget) {
  return budget.approvedAt || budget.createdAt;
}

function budgetVehicleTitle(budget) {
  return [budget.vehicleBrand, budget.vehicleModel].filter(Boolean).join(" ") || budget.vehicle || "Não informado";
}

function budgetAddressText(budget) {
  const address = [budget.clientStreet || budget.clientAddress, budget.clientNumber].filter(Boolean).join(", ");
  return [
    address,
    budget.clientDistrict && `Bairro ${budget.clientDistrict}`,
    budget.clientState,
    budget.clientZip && `CEP ${budget.clientZip}`
  ].filter(Boolean).join(" - ") || "Não informado";
}

function serviceOrderStatusLabel(status) {
  const labels = {
    aberta: "aberta",
    em_andamento: "em andamento",
    aguardando_peca: "aguardando peça",
    concluida: "concluída",
    entregue: "entregue"
  };
  return labels[status] || status || "aberta";
}

function serviceOrderBadgeClass(status) {
  if (status === "concluida" || status === "entregue") return "aprovado";
  if (status === "em_andamento") return "trial";
  if (status === "aguardando_peca") return "pendente";
  return "neutral";
}

function serviceOrderVehicleTitle(order) {
  return [order.vehicleBrand, order.vehicleModel].filter(Boolean).join(" ") || "Veículo não informado";
}

function formatZip(value) {
  const digits = String(value).replace(/\D/g, "").slice(0, 8);
  return digits.length > 5 ? `${digits.slice(0, 5)}-${digits.slice(5)}` : digits;
}

function formatVehicleKm(value) {
  const sanitized = sanitizeVehicleKmInput(value);
  if (sanitized.includes(".")) return sanitized;

  const digits = sanitized.replace(/\D/g, "");
  if (digits.length <= 3) return digits;

  return `${digits.slice(0, -3)}.${digits.slice(-3)}`;
}

function sanitizeVehicleKmInput(value) {
  const cleaned = String(value).replace(/[^\d.]/g, "");
  const [integerPart, ...decimalParts] = cleaned.split(".");
  if (!cleaned.includes(".")) return integerPart;

  const decimalPart = decimalParts.join("").replace(/\D/g, "").slice(0, 3);
  return `${integerPart}.${decimalPart}`;
}

function isValidVehicleKm(value) {
  return /^[0-9]+\.[0-9]{3}$/.test(String(value).trim());
}

function isValidBrazilianPlate(plate) {
  return /^[A-Z]{3}[0-9][A-Z0-9][0-9]{2}$/.test(String(plate).toUpperCase().trim());
}

function setAddressLookupState(message = "", isError = false) {
  const messageElement = $("#zipMessage");
  if (!messageElement) return;

  setMessage(messageElement, message, !isError);
}

async function lookupAddressByZip() {
  const zip = $("#clientZip").value.replace(/\D/g, "");
  if (zip.length !== 8) {
    setAddressLookupState("");
    return;
  }
  if (zip === lastZipLookup) return;

  lastZipLookup = zip;
  setAddressLookupState("Buscando endereço...", false);

  try {
    const response = await fetch(`https://viacep.com.br/ws/${zip}/json/`);
    if (!response.ok) throw new Error("zip_lookup_failed");

    const data = await response.json();
    if (data.erro) {
      setAddressLookupState("CEP não encontrado. Preencha o endereço manualmente.", true);
      return;
    }

    $("#clientZip").value = data.cep || formatZip(zip);
    $("#clientStreet").value = data.logradouro || "";
    $("#clientDistrict").value = data.bairro || "";
    $("#clientState").value = data.uf || "";
    setAddressLookupState("Endereço preenchido pelo CEP.", false);

    if (data.logradouro) {
      $("#clientNumber").focus();
    }
  } catch {
    setAddressLookupState("Não foi possível consultar o CEP agora. Preencha manualmente.", true);
  }
}

function renderItemsSummary(budget) {
  const parts = normalizeParts(budget);
  const labor = normalizeLabor(budget);

  const partsText = parts.length
    ? parts.map((part) => `${part.quantity}x ${part.code ? `${escapeHtml(part.code)} - ` : ""}${escapeHtml(part.description)} (${currency.format(Number(part.value))})`).join("<br>")
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
      <td>${escapeHtml(part.code || "-")}</td>
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
      <div class="detail-box"><span>Nome Completo</span><strong>${escapeHtml(budget.clientName)}</strong></div>
      <div class="detail-box"><span>E-mail</span><strong>${escapeHtml(budget.clientEmail || "Não informado")}</strong></div>
      <div class="detail-box"><span>Telefone</span><strong>${escapeHtml(budget.clientPhone || "Não informado")}</strong></div>
      <div class="detail-box"><span>Endereço</span><strong>${escapeHtml(budgetAddressText(budget))}</strong></div>
      <div class="detail-box"><span>Marca</span><strong>${escapeHtml(budget.vehicleBrand || "Não informado")}</strong></div>
      <div class="detail-box"><span>Modelo</span><strong>${escapeHtml(budget.vehicleModel || budget.vehicle || "Não informado")}</strong></div>
      <div class="detail-box"><span>Ano</span><strong>${escapeHtml(budget.vehicleYear || "Não informado")}</strong></div>
      <div class="detail-box"><span>Placa</span><strong>${escapeHtml(budget.plate || "Não informado")}</strong></div>
      <div class="detail-box"><span>Cor</span><strong>${escapeHtml(budget.vehicleColor || "Não informado")}</strong></div>
      <div class="detail-box"><span>KM</span><strong>${escapeHtml(budget.vehicleKm || "Não informado")}</strong></div>
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
            <th>Código</th>
            <th>Descrição</th>
            <th>Valor unitário</th>
            <th>Total</th>
          </tr>
        </thead>
        <tbody>${partsRows || '<tr><td colspan="5">Sem peças</td></tr>'}</tbody>
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
  renderCustomersView();
  renderServiceOrdersView();
  renderInventoryPartsTable();
  renderBilling();
}

function renderMetrics() {
  const pendingBudgets = budgets.filter((budget) => budget.status === STATUS.pending);
  const approvedBudgets = budgets.filter((budget) => budget.status === STATUS.approved);
  const rejectedBudgets = budgets.filter((budget) => budget.status === STATUS.rejected);

  $("#pendingCount").textContent = pendingBudgets.length;
  $("#approvedCount").textContent = approvedBudgets.length;
  $("#rejectedCount").textContent = rejectedBudgets.length;

  const revenue = approvedBudgets
    .filter((budget) => isDateInCurrentMonth(budgetBillingDate(budget)))
    .reduce((sum, budget) => sum + totalBudget(budget), 0);
  const forecast = [...approvedBudgets, ...pendingBudgets]
    .reduce((sum, budget) => sum + totalBudget(budget), 0);

  $("#revenueTotal").textContent = currency.format(revenue);
  $("#forecastTotal").textContent = currency.format(forecast);
  renderDashboardChart(revenue, forecast);
}

function renderDashboardChart(revenue, forecast) {
  const maximum = Math.max(revenue, forecast, 1);
  const items = [
    { label: "Faturamento mês", value: revenue, className: "current" },
    { label: "Faturamento previsto", value: forecast, className: "forecast" }
  ];

  $("#dashboardChart").innerHTML = items.map((item) => {
    const width = (item.value / maximum) * 100;

    return `
      <div class="chart-row">
        <div class="chart-label">
          <span>${item.label}</span>
          <strong>${currency.format(item.value)}</strong>
        </div>
        <div class="chart-track" aria-label="${item.label}: ${currency.format(item.value)}">
          <span class="chart-bar ${item.className}" style="width: ${width}%"></span>
        </div>
      </div>
    `;
  }).join("");
}

function budgetRows(items) {
  if (!items.length) {
    return '<p class="empty">Nenhum registro encontrado.</p>';
  }

  const rows = items.map((budget) => `
    <tr>
      <td>${escapeHtml(budget.clientName)}</td>
      <td>${escapeHtml(budgetVehicleTitle(budget))}<br><span class="muted">${escapeHtml(budget.plate)}</span></td>
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

function subscriptionLabel(status) {
  const labels = {
    trial: "teste",
    active: "ativa",
    past_due: "em atraso",
    canceled: "cancelada"
  };
  return labels[status] || status || "sem status";
}

function subscriptionBadgeClass(status) {
  if (status === "active") return "aprovado";
  if (status === "trial") return "trial";
  if (status === "past_due") return "pendente";
  if (status === "canceled") return "reprovado";
  return "neutral";
}

function formatOptionalDate(value) {
  if (!value) return "Não informado";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Não informado";
  return dateFormat.format(date);
}

function planFeatureLabel(feature) {
  const labels = {
    dashboard: "Painel",
    budgets: "Orçamentos",
    billing: "Financeiro",
    inventory: "Estoque",
    users: "Usuários",
    advanced_reports: "Relatórios avançados",
    priority_support: "Suporte prioritário"
  };
  return labels[feature] || feature;
}

function renderSubscriptionSummary() {
  const container = $("#subscriptionSummary");
  if (!container || !currentUser || currentUser.isPlatformAdmin) {
    if (container) container.classList.add("hidden");
    return;
  }

  const plan = currentPlan();
  const status = currentUser.subscriptionStatus || "trial";
  const blocked = !subscriptionAllowsWrite();
  const periodEnd = currentUser.currentPeriodEnd || currentUser.trialEndsAt;
  const features = (plan.features || [])
    .map((feature) => `<span class="chip">${escapeHtml(planFeatureLabel(feature))}</span>`)
    .join("");

  container.classList.remove("hidden");
  container.innerHTML = `
    <div class="panel-head">
      <div>
        <h2>Minha assinatura</h2>
        <p class="muted">${escapeHtml(plan.description || "Plano atual da oficina.")}</p>
      </div>
      <span class="badge ${subscriptionBadgeClass(status)}">${escapeHtml(subscriptionLabel(status))}</span>
    </div>
    <div class="subscription-grid">
      <div>
        <span>Plano</span>
        <strong>${escapeHtml(plan.name || plan.code)}</strong>
      </div>
      <div>
        <span>Ciclo</span>
        <strong>${escapeHtml(plan.billingCycleLabel || billingCycles[plan.billingCycle] || "Mensal")}</strong>
      </div>
      <div>
        <span>Valor</span>
        <strong>${currency.format(Number(plan.currentPrice || 0))}</strong>
      </div>
      <div>
        <span>Usuários</span>
        <strong>Até ${escapeHtml(plan.limits?.users || 1)}</strong>
      </div>
      <div>
        <span>Próximo marco</span>
        <strong>${formatOptionalDate(periodEnd)}</strong>
      </div>
    </div>
    <div class="chip-list">${features}</div>
    ${blocked ? '<p class="message plan-warning">Assinatura irregular. Você pode consultar dados, mas alterações ficam bloqueadas até regularização.</p>' : ""}
  `;
}

function renderPlatformDashboard() {
  if (!canAccess("platform")) return;

  const active = platformCompanies.filter((company) => company.subscriptionStatus === "active");
  const trial = platformCompanies.filter((company) => company.subscriptionStatus === "trial");
  const alerts = platformCompanies.filter((company) => ["past_due", "canceled"].includes(company.subscriptionStatus));
  const approvedBudgets = platformCompanies.reduce((sum, company) => sum + Number(company.approvedBudgetCount || 0), 0);

  $("#platformCompanyCount").textContent = platformCompanies.length;
  $("#platformActiveCount").textContent = active.length;
  $("#platformTrialCount").textContent = trial.length;
  $("#platformAlertCount").textContent = alerts.length;
  $("#platformApprovedBudgetCount").textContent = approvedBudgets;
  renderPlatformActionOptions();
  renderPlatformCompaniesTable();
  renderPlatformPaymentsTable();
  renderPlatformAuditTable();
}

function dateInputValue(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return date.toISOString().slice(0, 10);
}

function selectedPlatformCompany(selectId) {
  const id = Number($(`#${selectId}`)?.value || 0);
  return platformCompanies.find((company) => Number(company.id) === id) || null;
}

function renderPlatformActionOptions() {
  const options = platformCompanies.map((company) => `
    <option value="${company.id}">${escapeHtml(company.name)} - ${escapeHtml(subscriptionLabel(company.subscriptionStatus))}</option>
  `).join("");

  ["platformSubscriptionCompany", "platformPaymentCompany"].forEach((selectId) => {
    const select = $(`#${selectId}`);
    if (!select) return;
    const currentValue = select.value;
    select.innerHTML = options || '<option value="">Nenhuma oficina</option>';
    if (currentValue && Array.from(select.options).some((option) => option.value === currentValue)) {
      select.value = currentValue;
    }
  });

  fillPlatformSubscriptionForm(selectedPlatformCompany("platformSubscriptionCompany") || platformCompanies[0]);
}

function fillPlatformSubscriptionForm(company) {
  if (!company) return;
  $("#platformSubscriptionCompany").value = company.id;
  $("#platformSubscriptionPlan").value = company.plan || "trial";
  $("#platformSubscriptionBillingCycle").value = company.billingCycle || "monthly";
  $("#platformSubscriptionStatus").value = company.subscriptionStatus || "trial";
  $("#platformPeriodStart").value = dateInputValue(company.currentPeriodStart);
  $("#platformPeriodEnd").value = dateInputValue(company.currentPeriodEnd);
  $("#platformTrialEndsAt").value = dateInputValue(company.trialEndsAt);
}

function filteredPlatformCompanies() {
  const status = $("#platformStatusFilter")?.value || "todos";
  const plan = $("#platformPlanFilter")?.value || "todos";
  const search = ($("#platformSearchFilter")?.value || "").trim().toLowerCase();

  return platformCompanies.filter((company) => {
    const matchesStatus = status === "todos" || company.subscriptionStatus === status;
    const matchesPlan = plan === "todos" || company.plan === plan;
    const searchable = [
      company.name,
      company.document,
      company.phone,
      company.id
    ].map((value) => String(value || "").toLowerCase()).join(" ");
    const matchesSearch = !search || searchable.includes(search);
    return matchesStatus && matchesPlan && matchesSearch;
  });
}

function renderPlatformCompaniesTable() {
  const container = $("#platformCompaniesTable");
  if (!container) return;

  if (!platformCompanies.length) {
    container.innerHTML = '<p class="empty">Nenhuma oficina cadastrada.</p>';
    return;
  }

  const filteredCompanies = filteredPlatformCompanies();
  const filteredCount = $("#platformFilteredCount");
  if (filteredCount) {
    filteredCount.textContent = `${filteredCompanies.length} de ${platformCompanies.length} oficinas`;
  }

  if (!filteredCompanies.length) {
    container.innerHTML = '<p class="empty">Nenhuma oficina encontrada com os filtros atuais.</p>';
    return;
  }

  const rows = filteredCompanies.map((company) => `
    <tr>
      <td>
        <strong>${escapeHtml(company.name)}</strong><br>
        <span class="muted">ID ${escapeHtml(company.id)}</span>
      </td>
      <td>${escapeHtml(company.plan || "Não definido")}</td>
      <td>${escapeHtml(billingCycles[company.billingCycle] || "Mensal")}</td>
      <td><span class="badge ${subscriptionBadgeClass(company.subscriptionStatus)}">${escapeHtml(subscriptionLabel(company.subscriptionStatus))}</span></td>
      <td>${escapeHtml(company.userCount || 0)}</td>
      <td>${escapeHtml(company.budgetCount || 0)}</td>
      <td>${escapeHtml(company.approvedBudgetCount || 0)}</td>
      <td>${formatOptionalDate(company.currentPeriodEnd || company.trialEndsAt)}</td>
      <td>${formatOptionalDate(company.lastPaymentAt)}</td>
    </tr>
  `).join("");

  container.innerHTML = `
    <table>
      <thead>
        <tr>
          <th>Oficina</th>
          <th>Plano</th>
          <th>Ciclo</th>
          <th>Status</th>
          <th>Usuários</th>
          <th>Orçamentos</th>
          <th>Aprovados</th>
          <th>Próximo marco</th>
          <th>Último pagamento</th>
        </tr>
      </thead>
      <tbody>${rows}</tbody>
    </table>
  `;
}

function auditActionLabel(action) {
  const labels = {
    "company.create": "Oficina criada",
    "subscription.create": "Assinatura criada",
    "subscription.update": "Assinatura atualizada",
    "payment.create": "Pagamento registrado"
  };
  return labels[action] || action || "Ação";
}

function auditDetailsText(details = {}) {
  if (details.after) {
    const before = details.before || {};
    return `${before.plan || "sem plano"} / ${before.status || "sem status"} -> ${details.after.plan || "sem plano"} / ${details.after.status || "sem status"}`;
  }
  if (details.amount !== undefined) {
    return `${currency.format(Number(details.amount || 0))} - ${details.status || "sem status"}`;
  }
  if (details.companyName) {
    return `${details.companyName} - ${details.plan || "sem plano"} / ${details.status || "sem status"}`;
  }
  return "Sem detalhes";
}

function renderPlatformAuditTable() {
  const container = $("#platformAuditTable");
  if (!container) return;

  if (!platformAudit.length) {
    container.innerHTML = '<p class="empty">Nenhuma ação master registrada ainda.</p>';
    return;
  }

  const rows = platformAudit.map((item) => `
    <tr>
      <td>${formatOptionalDate(item.createdAt)}</td>
      <td>${escapeHtml(auditActionLabel(item.action))}</td>
      <td>${escapeHtml(item.targetCompanyName || "Plataforma")}</td>
      <td>${escapeHtml(item.actorEmail || "Não informado")}</td>
      <td>${escapeHtml(auditDetailsText(item.details))}</td>
    </tr>
  `).join("");

  container.innerHTML = `
    <table>
      <thead>
        <tr>
          <th>Data</th>
          <th>Ação</th>
          <th>Oficina</th>
          <th>Operador</th>
          <th>Detalhes</th>
        </tr>
      </thead>
      <tbody>${rows}</tbody>
    </table>
  `;
}

function renderPlatformPaymentsTable() {
  const container = $("#platformPaymentsTable");
  if (!container) return;

  if (!platformPayments.length) {
    container.innerHTML = '<p class="empty">Nenhum pagamento registrado ainda.</p>';
    return;
  }

  const rows = platformPayments.map((payment) => `
    <tr>
      <td>${escapeHtml(payment.companyName || "Empresa")}</td>
      <td>${escapeHtml(payment.subscriptionPlan || "Não definido")}</td>
      <td>${currency.format(Number(payment.amount || 0))}</td>
      <td><span class="badge ${subscriptionBadgeClass(payment.status)}">${escapeHtml(payment.status || "pending")}</span></td>
      <td>${formatOptionalDate(payment.paidAt)}</td>
      <td>${escapeHtml(payment.provider || "Manual")}</td>
    </tr>
  `).join("");

  container.innerHTML = `
    <table>
      <thead>
        <tr>
          <th>Oficina</th>
          <th>Plano</th>
          <th>Valor</th>
          <th>Status</th>
          <th>Pago em</th>
          <th>Provedor</th>
        </tr>
      </thead>
      <tbody>${rows}</tbody>
    </table>
  `;
}

function clearPlatformCompanyForm() {
  $("#platformCompanyForm")?.reset();
  setMessage($("#platformCompanyMessage"), "");
}

function renderCustomerOptions() {
  const select = $("#vehicleCustomer");
  if (!select) return;
  const currentValue = select.value;
  select.innerHTML = customers.map((customer) => `
    <option value="${customer.id}">${escapeHtml(customer.name)}${customer.phone ? ` - ${escapeHtml(customer.phone)}` : ""}</option>
  `).join("") || '<option value="">Cadastre um cliente primeiro</option>';
  if (currentValue && Array.from(select.options).some((option) => option.value === currentValue)) {
    select.value = currentValue;
  }
}

function renderBudgetCustomerOptions() {
  const customerSelect = $("#budgetCustomerSelect");
  const vehicleSelect = $("#budgetVehicleSelect");
  if (!customerSelect || !vehicleSelect) return;

  const currentCustomer = customerSelect.value;
  customerSelect.innerHTML = '<option value="">Novo cliente ou busca manual</option>' + customers.map((customer) => `
    <option value="${customer.id}">${escapeHtml(customer.name)}${customer.phone ? ` - ${escapeHtml(customer.phone)}` : ""}</option>
  `).join("");
  if (currentCustomer && Array.from(customerSelect.options).some((option) => option.value === currentCustomer)) {
    customerSelect.value = currentCustomer;
  }

  renderBudgetVehicleOptions();
}

function renderBudgetVehicleOptions(customerId = $("#budgetCustomerSelect")?.value || "") {
  const vehicleSelect = $("#budgetVehicleSelect");
  if (!vehicleSelect) return;
  const currentVehicle = vehicleSelect.value;
  const scopedVehicles = customerId
    ? vehicles.filter((vehicle) => Number(vehicle.customerId) === Number(customerId))
    : vehicles;

  vehicleSelect.innerHTML = '<option value="">Novo veículo ou busca manual</option>' + scopedVehicles.map((vehicle) => `
    <option value="${vehicle.id}">${escapeHtml(vehicle.plate || "Sem placa")} - ${escapeHtml([vehicle.brand, vehicle.model].filter(Boolean).join(" ") || "Veículo")}</option>
  `).join("");
  if (currentVehicle && Array.from(vehicleSelect.options).some((option) => option.value === currentVehicle)) {
    vehicleSelect.value = currentVehicle;
  }
}

function fillBudgetCustomerFields(customer) {
  if (!customer) return;
  $("#clientName").value = customer.name || "";
  $("#clientEmail").value = customer.email || "";
  $("#clientPhone").value = customer.phone || "";
  $("#clientZip").value = customer.zip || "";
  $("#clientStreet").value = customer.street || "";
  $("#clientNumber").value = customer.number || "";
  $("#clientDistrict").value = customer.district || "";
  $("#clientState").value = customer.state || "";
}

function fillBudgetVehicleFields(vehicle) {
  if (!vehicle) return;
  $("#vehicleBrand").value = vehicle.brand || "";
  $("#vehicleModel").value = vehicle.model || "";
  $("#vehicleYear").value = vehicle.year || "";
  $("#plate").value = vehicle.plate || "";
  $("#vehicleColor").value = vehicle.color || "";
  $("#vehicleKm").value = vehicle.km || "";
  if (vehicle.customerId) {
    $("#budgetCustomerSelect").value = vehicle.customerId;
    renderBudgetVehicleOptions(vehicle.customerId);
    $("#budgetVehicleSelect").value = vehicle.id;
    const customer = customers.find((item) => Number(item.id) === Number(vehicle.customerId));
    fillBudgetCustomerFields(customer);
  }
}

function findCustomerByContact() {
  const email = $("#clientEmail").value.toLowerCase().trim();
  const phone = $("#clientPhone").value.trim();
  return customers.find((customer) => (
    (email && String(customer.email || "").toLowerCase() === email)
    || (phone && String(customer.phone || "") === phone)
  ));
}

function findVehicleByPlateInput() {
  const plate = $("#plate").value.toUpperCase().replace(/[^A-Z0-9]/g, "");
  return vehicles.find((vehicle) => String(vehicle.plate || "").toUpperCase().replace(/[^A-Z0-9]/g, "") === plate);
}

function renderCustomersTable() {
  const container = $("#customersTable");
  if (!container) return;
  if (!customers.length) {
    container.innerHTML = '<p class="empty">Nenhum cliente cadastrado ainda.</p>';
    return;
  }

  const rows = customers.map((customer) => `
    <tr>
      <td><button class="table-link" data-action="edit-customer" data-id="${customer.id}">${escapeHtml(customer.name)}</button></td>
      <td>${escapeHtml(customer.phone || "Não informado")}</td>
      <td>${escapeHtml(customer.email || "Não informado")}</td>
      <td>${escapeHtml(customer.vehicleCount || 0)}</td>
      <td>${escapeHtml(customer.serviceOrderCount || 0)}</td>
      <td>${escapeHtml([customer.street, customer.number, customer.district, customer.state].filter(Boolean).join(", ") || "Não informado")}</td>
    </tr>
  `).join("");

  container.innerHTML = `
    <table>
      <thead>
        <tr>
          <th>Cliente</th>
          <th>Telefone</th>
          <th>E-mail</th>
          <th>Veículos</th>
          <th>OS</th>
          <th>Endereço</th>
        </tr>
      </thead>
      <tbody>${rows}</tbody>
    </table>
  `;
}

function renderVehiclesTable() {
  const container = $("#vehiclesTable");
  if (!container) return;
  if (!vehicles.length) {
    container.innerHTML = '<p class="empty">Nenhum veículo cadastrado ainda.</p>';
    return;
  }

  const rows = vehicles.map((vehicle) => `
    <tr>
      <td><button class="table-link" data-action="edit-vehicle" data-id="${vehicle.id}">${escapeHtml(vehicle.plate || "Sem placa")}</button></td>
      <td>${escapeHtml([vehicle.brand, vehicle.model].filter(Boolean).join(" ") || "Não informado")}</td>
      <td>${escapeHtml(vehicle.year || "Não informado")}</td>
      <td>${escapeHtml(vehicle.color || "Não informado")}</td>
      <td>${escapeHtml(vehicle.km || "Não informado")}</td>
      <td>${escapeHtml(vehicle.customerName || "Não informado")}</td>
    </tr>
  `).join("");

  container.innerHTML = `
    <table>
      <thead>
        <tr>
          <th>Placa</th>
          <th>Veículo</th>
          <th>Ano</th>
          <th>Cor</th>
          <th>KM</th>
          <th>Cliente</th>
        </tr>
      </thead>
      <tbody>${rows}</tbody>
    </table>
  `;
}

function renderCustomersView() {
  renderCustomerOptions();
  renderBudgetCustomerOptions();
  renderCustomersTable();
  renderVehiclesTable();
}

function clearCustomerForm() {
  editingCustomerId = null;
  $("#customerForm")?.reset();
  $("#customerFormTitle").textContent = "Cadastrar cliente";
  setMessage($("#customerMessage"), "");
}

function fillCustomerForm(customer) {
  editingCustomerId = customer.id;
  $("#customerFormTitle").textContent = "Editar cliente";
  $("#customerName").value = customer.name || "";
  $("#customerPhone").value = customer.phone || "";
  $("#customerEmail").value = customer.email || "";
  $("#customerZip").value = customer.zip || "";
  $("#customerStreet").value = customer.street || "";
  $("#customerNumber").value = customer.number || "";
  $("#customerDistrict").value = customer.district || "";
  $("#customerState").value = customer.state || "";
  $("#customerNotes").value = customer.notes || "";
  setMessage($("#customerMessage"), "");
}

function clearVehicleForm() {
  editingVehicleId = null;
  $("#vehicleForm")?.reset();
  $("#vehicleFormTitle").textContent = "Cadastrar veículo";
  renderCustomerOptions();
  setMessage($("#vehicleMessage"), "");
}

function fillVehicleForm(vehicle) {
  editingVehicleId = vehicle.id;
  $("#vehicleFormTitle").textContent = "Editar veículo";
  renderCustomerOptions();
  $("#vehicleCustomer").value = vehicle.customerId || "";
  $("#customerVehicleBrand").value = vehicle.brand || "";
  $("#customerVehicleModel").value = vehicle.model || "";
  $("#customerVehicleYear").value = vehicle.year || "";
  $("#customerVehiclePlate").value = vehicle.plate || "";
  $("#customerVehicleColor").value = vehicle.color || "";
  $("#customerVehicleKm").value = vehicle.km || "";
  $("#vehicleNotes").value = vehicle.notes || "";
  setMessage($("#vehicleMessage"), "");
}

function renderServiceOrdersView() {
  const container = $("#serviceOrdersTable");
  if (!container) return;
  const filter = $("#serviceOrderStatusFilter")?.value || "todos";
  const filtered = filter === "todos"
    ? serviceOrders
    : serviceOrders.filter((order) => order.status === filter);

  if (!filtered.length) {
    container.innerHTML = '<p class="empty">Nenhuma ordem de serviço para este filtro.</p>';
    return;
  }

  const statusOptions = ["aberta", "em_andamento", "aguardando_peca", "concluida", "entregue"];
  const rows = filtered.map((order) => `
    <tr>
      <td><strong>${escapeHtml(order.number)}</strong><br><span class="muted">Orçamento ${escapeHtml(order.budgetId || "manual")}</span></td>
      <td>${escapeHtml(order.customerName || "Cliente")}</td>
      <td>${escapeHtml(serviceOrderVehicleTitle(order))}<br><span class="muted">${escapeHtml(order.vehiclePlate || "")}</span></td>
      <td>
        <span class="badge ${serviceOrderBadgeClass(order.status)}">${escapeHtml(serviceOrderStatusLabel(order.status))}</span>
      </td>
      <td>${escapeHtml(order.priority || "normal")}</td>
      <td>${formatOptionalDate(order.entryDate)}</td>
      <td>${formatOptionalDate(order.expectedDeliveryDate)}</td>
      <td>${currency.format(Number(order.totalAmount || 0))}</td>
      <td>
        <select class="compact-select" data-action="change-service-order-status" data-id="${order.id}">
          ${statusOptions.map((status) => `<option value="${status}" ${order.status === status ? "selected" : ""}>${serviceOrderStatusLabel(status)}</option>`).join("")}
        </select>
      </td>
    </tr>
  `).join("");

  container.innerHTML = `
    <table>
      <thead>
        <tr>
          <th>OS</th>
          <th>Cliente</th>
          <th>Veículo</th>
          <th>Status</th>
          <th>Prioridade</th>
          <th>Entrada</th>
          <th>Previsão</th>
          <th>Total</th>
          <th>Atualizar</th>
        </tr>
      </thead>
      <tbody>${rows}</tbody>
    </table>
  `;
}

function renderBudgetList() {
  const filter = $("#statusFilter").value;
  const search = ($("#budgetSearch")?.value || "").toLowerCase().trim();
  const filtered = (filter === "todos" ? budgets : budgets.filter((budget) => budget.status === filter))
    .filter((budget) => {
      const searchable = [
        budget.clientName,
        budgetVehicleTitle(budget),
        budget.plate,
        budget.clientEmail,
        budget.clientPhone,
        budget.clientZip,
        budget.clientDistrict,
        budget.clientState
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
        <td>${escapeHtml(budgetVehicleTitle(budget))}<br><span class="muted">${escapeHtml(budget.plate)}</span></td>
        <td><span class="badge ${budget.status}">${budget.status}</span></td>
        <td>${currency.format(totalBudget(budget))}</td>
        <td>${dateFormat.format(new Date(budget.createdAt))}</td>
        <td>
          <div class="actions compact-actions">
            <button class="action" data-action="view" data-id="${budget.id}">Abrir</button>
            ${canAccess("budgets_manage") ? `<button class="action" data-action="edit" data-id="${budget.id}">Editar</button>` : ""}
            ${canApproveBudget(budget) ? `
              <button class="action success" data-action="approve" data-id="${budget.id}">Aprovar</button>
              <button class="action danger" data-action="reject" data-id="${budget.id}">Reprovar</button>
            ` : ""}
            ${canGenerateServiceOrder(budget) ? `<button class="action success" data-action="create-os" data-id="${budget.id}">Gerar OS</button>` : ""}
            ${canDeleteBudget(budget) ? `<button class="action danger" data-action="delete" data-id="${budget.id}">Excluir</button>` : ""}
          </div>
        </td>
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
              <th>Ações</th>
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
          <span class="muted">${escapeHtml(budgetVehicleTitle(budget))} - ${escapeHtml(budget.plate)}</span>
        </div>
        <span class="badge ${budget.status}">${budget.status}</span>
      </header>
      <div class="budget-meta">
        ${budget.clientEmail ? `<span>${escapeHtml(budget.clientEmail)}</span>` : ""}
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
        ${canApproveBudget(budget) ? `
          <button class="action success" data-action="approve" data-id="${budget.id}">Aprovar</button>
          <button class="action danger" data-action="reject" data-id="${budget.id}">Reprovar</button>
        ` : ""}
        ${canGenerateServiceOrder(budget) ? `<button class="action success" data-action="create-os" data-id="${budget.id}">Gerar OS</button>` : ""}
        ${canDeleteBudget(budget) ? `<button class="action danger" data-action="delete" data-id="${budget.id}">Excluir</button>` : ""}
      </div>
    </article>
  `).join("");
}

function renderInventoryPartsTable() {
  const container = $("#partsInventoryTable");
  if (!container) return;

  const search = ($("#partSearch")?.value || "").toLowerCase().trim();
  const filtered = inventoryParts.filter((part) => {
    const searchable = [
      part.code,
      part.brand,
      part.description,
      part.serialNumber
    ].join(" ").toLowerCase();
    return !search || searchable.includes(search);
  });

  if (!filtered.length) {
    container.innerHTML = '<p class="empty">Nenhuma peça cadastrada.</p>';
    return;
  }

  const rows = filtered.map((part) => `
    <tr>
      <td><strong>${escapeHtml(part.code)}</strong></td>
      <td>${escapeHtml(part.brand)}</td>
      <td>${escapeHtml(part.description)}</td>
      <td>${currency.format(Number(part.costPrice || 0))}</td>
      <td>${currency.format(Number(part.salePrice || 0))}</td>
      <td>${escapeHtml(part.stockQuantity ?? 0)}</td>
      <td>${escapeHtml(part.serialNumber || "Não informado")}</td>
      <td>
        ${canAccess("inventory_manage") ? `
          <button type="button" class="action" data-part-action="select" data-id="${part.id}">Selecionar</button>
          <button type="button" class="action danger" data-part-action="delete" data-id="${part.id}">Excluir</button>
        ` : ""}
      </td>
    </tr>
  `).join("");

  container.innerHTML = `
    <table>
      <thead>
        <tr>
          <th>Código</th>
          <th>Marca</th>
          <th>Descrição</th>
          <th>Custo</th>
          <th>Venda</th>
          <th>Estoque</th>
          <th>Número de série</th>
          <th>Ações</th>
        </tr>
      </thead>
      <tbody>${rows}</tbody>
    </table>
  `;
}

function supplierDisplayName(supplier) {
  return supplier?.tradeName || supplier?.corporateName || "Fornecedor";
}

function renderSupplierSuggestions(term = "") {
  const container = $("#supplierSuggestions");
  if (!container) return;

  const search = String(term || "").toLowerCase().trim();
  if (!search) {
    container.classList.add("hidden");
    container.innerHTML = "";
    return;
  }

  const matches = suppliers
    .filter((supplier) => [
      supplier.cnpj,
      supplier.corporateName,
      supplier.tradeName,
      supplier.phone,
      supplier.sellerName
    ].join(" ").toLowerCase().includes(search))
    .slice(0, 8);

  if (!matches.length) {
    container.innerHTML = '<p class="empty">Fornecedor novo. Preencha os dados abaixo.</p>';
    container.classList.remove("hidden");
    return;
  }

  container.innerHTML = matches.map((supplier) => `
    <button type="button" class="part-suggestion" data-supplier-id="${supplier.id}">
      <strong>${escapeHtml(supplierDisplayName(supplier))}</strong>
      <span>${escapeHtml(supplier.cnpj)} - ${escapeHtml(supplier.corporateName)}</span>
    </button>
  `).join("");
  container.classList.remove("hidden");
}

function selectSupplier(supplier) {
  if (!supplier) return;

  selectedSupplierId = supplier.id;
  $("#supplierSearch").value = `${supplierDisplayName(supplier)} - ${supplier.cnpj}`;
  $("#supplierCnpj").value = supplier.cnpj || "";
  $("#supplierCorporateName").value = supplier.corporateName || "";
  $("#supplierTradeName").value = supplier.tradeName || "";
  $("#supplierPhone").value = supplier.phone || "";
  $("#supplierSellerName").value = supplier.sellerName || "";
  $("#supplierSuggestions").classList.add("hidden");
}

function clearSupplierSelection() {
  selectedSupplierId = null;
}

function clearPayableForm() {
  selectedSupplierId = null;
  $("#payableForm").reset();
  $("#payableEntryDate").value = new Date().toISOString().slice(0, 10);
  $("#supplierSuggestions").classList.add("hidden");
  $("#supplierSuggestions").innerHTML = "";
  setMessage($("#payableMessage"), "");
}

function renderLatestPayables() {
  const container = $("#latestPayablesTable");
  if (!container) return;

  if (!payables.length) {
    container.innerHTML = '<p class="empty">Nenhuma compra cadastrada ainda.</p>';
    return;
  }

  const rows = payables.slice(0, 5).map((payable) => `
    <tr>
      <td>${escapeHtml(payable.description)}</td>
      <td>${escapeHtml(payable.supplierName)}</td>
      <td>${escapeHtml(payable.category)}</td>
      <td>${currency.format(Number(payable.amount || 0))}</td>
      <td>${dateFormat.format(new Date(`${payable.entryDate}T00:00:00`))}</td>
      <td>${dateFormat.format(new Date(`${payable.competenceDate}T00:00:00`))}</td>
      <td>${escapeHtml(payable.invoiceNumber || "Não informado")}</td>
    </tr>
  `).join("");

  container.innerHTML = `
    <table>
      <thead>
        <tr>
          <th>Descrição</th>
          <th>Fornecedor</th>
          <th>Categoria</th>
          <th>Valor</th>
          <th>Data</th>
          <th>Competência</th>
          <th>Nota fiscal</th>
        </tr>
      </thead>
      <tbody>${rows}</tbody>
    </table>
  `;
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
      <td>${escapeHtml(budgetVehicleTitle(budget))} - ${escapeHtml(budget.plate)}</td>
      <td>${currency.format(laborTotal(budget))}</td>
      <td>${currency.format(partsTotal(budget))}</td>
      <td>${currency.format(totalBudget(budget))}</td>
      <td>${dateFormat.format(new Date(budgetBillingDate(budget)))}</td>
      <td>
        <button class="action" data-action="view" data-id="${budget.id}">Abrir</button>
        ${canAccess("billing_edit") ? `<button class="action" data-action="edit" data-id="${budget.id}">Editar</button>` : ""}
        ${canDeleteBudget(budget) ? `<button class="action danger" data-action="delete" data-id="${budget.id}">Excluir</button>` : ""}
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
          <button class="action" data-user-action="select" data-id="${user.id}">Selecionar</button>
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
  setPageTitle(settingsSectionTitle(sectionId));
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

function fillUserForm(user) {
  if (!user) return;

  editingUserId = user.id;
  $("#userFormTitle").textContent = "Editar usuário";
  $("#saveUserButton").textContent = "Salvar alterações";
  $("#clearUserFormButton").classList.remove("hidden");
  $("#newUserName").value = user.name || "";
  $("#newUsername").value = user.username || "";
  $("#newUserEmail").value = user.email || "";
  $("#newUserPhone").value = user.phone || "";
  $("#newUserPassword").value = "";
  $("#newUserPassword").placeholder = "Preencha somente para resetar a senha";
  $("#newUserAccessLevel").value = user.accessLevel || (user.role === "admin" ? "administrador" : "analista");
  setMessage($("#userCreateMessage"), "Usuário selecionado para edição.", true);
  $("#newUserName").focus();
}

function clearUserForm() {
  editingUserId = null;
  $("#userCreateForm").reset();
  $("#userFormTitle").textContent = "Criação de Usuário";
  $("#saveUserButton").textContent = "Criar usuário";
  $("#clearUserFormButton").classList.add("hidden");
  $("#newUserPassword").placeholder = "";
  setMessage($("#userCreateMessage"), "");
}

function openUserLookupModal() {
  $("#userSearch").value = "";
  renderUsersTable();
  $("#userLookupModal").classList.remove("hidden");
  $("#userSearch").focus();
}

function closeUserLookupModal() {
  $("#userLookupModal").classList.add("hidden");
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

  user.password = newPassword;
  user.updatedAt = new Date().toISOString();
  await updateUser(user);
  delete user.password;
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
  if (!budget.clientEmail) {
    alert("Este orçamento não possui e-mail cadastrado para o cliente.");
    return;
  }

  const parts = normalizeParts(budget);
  const labor = normalizeLabor(budget);
  const subject = encodeURIComponent(`Orçamento Oficina Pro - ${budgetVehicleTitle(budget)}`);
  const body = encodeURIComponent([
    `Olá, ${budget.clientName}.`,
    "",
    "Segue o orçamento solicitado:",
    `Veículo: ${budgetVehicleTitle(budget)}`,
    budget.vehicleYear ? `Ano: ${budget.vehicleYear}` : "",
    `Placa: ${budget.plate}`,
    budget.vehicleColor ? `Cor: ${budget.vehicleColor}` : "",
    budget.vehicleKm ? `KM: ${budget.vehicleKm}` : "",
    budget.clientPhone ? `Telefone: ${budget.clientPhone}` : "",
    `Endereço: ${budgetAddressText(budget)}`,
    "",
    "Peças:",
    ...parts.map((part) => `- ${part.quantity}x ${part.code ? `${part.code} - ` : ""}${part.description}: ${currency.format(Number(part.quantity) * Number(part.value))}`),
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
      <td>${escapeHtml(part.code || "-")}</td>
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
    <p><strong>Nome Completo:</strong> ${escapeHtml(budget.clientName)}</p>
    ${budget.clientEmail ? `<p><strong>E-mail:</strong> ${escapeHtml(budget.clientEmail)}</p>` : ""}
    ${budget.clientPhone ? `<p><strong>Telefone:</strong> ${escapeHtml(budget.clientPhone)}</p>` : ""}
    <p><strong>Endereço:</strong> ${escapeHtml(budgetAddressText(budget))}</p>
    <p><strong>Veículo:</strong> ${escapeHtml(budgetVehicleTitle(budget))} - ${escapeHtml(budget.plate)}</p>
    ${budget.vehicleYear ? `<p><strong>Ano:</strong> ${escapeHtml(budget.vehicleYear)}</p>` : ""}
    ${budget.vehicleColor ? `<p><strong>Cor:</strong> ${escapeHtml(budget.vehicleColor)}</p>` : ""}
    ${budget.vehicleKm ? `<p><strong>KM:</strong> ${escapeHtml(budget.vehicleKm)}</p>` : ""}
    <p><strong>Data:</strong> ${dateFormat.format(new Date(budget.createdAt))}</p>
    <p><strong>Status:</strong> ${budget.status}</p>
    <hr>
    <h2>Peças</h2>
    <table>
      <thead>
        <tr>
          <th>Quantidade</th>
          <th>Código</th>
          <th>Descrição</th>
          <th>Valor unitário</th>
          <th>Total</th>
        </tr>
      </thead>
      <tbody>${partsRows || '<tr><td colspan="5">Sem peças</td></tr>'}</tbody>
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

  if (status === STATUS.approved && budget.status !== STATUS.approved) {
    const stockMessage = await discountBudgetPartsFromInventory(budget);
    if (stockMessage) {
      alert(stockMessage);
      return;
    }
  }

  budget.status = status;
  budget.updatedAt = new Date().toISOString();
  if (status === STATUS.approved) {
    budget.approvedAt = budget.updatedAt;
  } else {
    delete budget.approvedAt;
  }

  await updateBudget(budget);
  await loadBudgets();
  closeBudgetModal();
}

async function discountBudgetPartsFromInventory(budget) {
  await loadInventoryParts();
  const parts = normalizeParts(budget).filter((part) => part.id || part.code);
  const grouped = new Map();

  parts.forEach((part) => {
    const key = part.id ? `id:${part.id}` : `code:${String(part.code).toLowerCase()}`;
    const current = grouped.get(key) || { ...part, quantity: 0 };
    current.quantity += Number(part.quantity || 0);
    grouped.set(key, current);
  });

  const updates = [];
  for (const part of grouped.values()) {
    const inventoryPart = part.id
      ? inventoryParts.find((item) => item.id === Number(part.id))
      : findInventoryPartByCode(part.code);

    if (!inventoryPart) {
      return `A peça ${part.code || part.description} não foi encontrada no estoque.`;
    }

    const currentStock = Number(inventoryPart.stockQuantity || 0);
    if (currentStock < part.quantity) {
      return `Estoque insuficiente para ${inventoryPart.code} - ${inventoryPart.description}. Disponível: ${currentStock}. Necessário: ${part.quantity}.`;
    }

    updates.push({
      ...inventoryPart,
      stockQuantity: currentStock - part.quantity,
      updatedAt: new Date().toISOString()
    });
  }

  for (const part of updates) {
    await updateInventoryPart(part);
  }
  await loadInventoryParts();
  return "";
}

async function removeBudget(id) {
  const budget = budgets.find((item) => item.id === Number(id));
  if (!canDeleteBudget(budget)) return;

  const confirmed = confirm(`Excluir o orçamento de ${budget.clientName}? Esta ação não pode ser desfeita.`);
  if (!confirmed) return;

  await deleteBudget(budget.id);
  await loadBudgets();
  closeBudgetModal();
}

async function generateServiceOrderFromBudget(budget) {
  if (!canGenerateServiceOrder(budget)) return;
  const order = await createServiceOrderFromBudget(budget.id);
  await Promise.all([loadCustomers(), loadServiceOrders()]);
  closeBudgetModal();
  switchView("serviceOrdersView");
  markParentMenu("budgets");
  setPageTitle("Atendimento / Ordens de serviço");
  alert(`Ordem de serviço ${order.number} gerada para ${budget.clientName}.`);
}

function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function createPartRow(part = { quantity: 1, code: "", description: "", value: "" }) {
  const row = document.createElement("div");
  row.className = "line-grid part-row";
  row.innerHTML = `
    <input class="part-quantity" type="number" min="1" step="1" value="${escapeHtml(part.quantity || 1)}">
    <input class="part-code" type="text" value="${escapeHtml(part.code || "")}" placeholder="Código">
    <div class="part-search-wrap">
      <input class="part-description" type="text" value="${escapeHtml(part.description)}" placeholder="Ex: Pastilha de freio" autocomplete="off">
      <div class="part-suggestions hidden"></div>
    </div>
    <input class="part-value" type="number" min="0" step="0.01" value="${escapeHtml(part.value)}">
    <button type="button" class="remove-line" title="Remover peça">×</button>
  `;
  if (part.id) row.dataset.partId = part.id;
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

function partMatchesSearch(part, query) {
  const normalized = query.toLowerCase().trim();
  if (!normalized) return false;
  return [part.code, part.description, part.brand, part.serialNumber]
    .join(" ")
    .toLowerCase()
    .includes(normalized);
}

function matchingInventoryParts(query) {
  return inventoryParts
    .filter((part) => partMatchesSearch(part, query))
    .slice(0, 8);
}

function closePartSuggestions(row) {
  row.querySelector(".part-suggestions")?.classList.add("hidden");
}

function renderPartSuggestions(row, query) {
  const suggestions = row.querySelector(".part-suggestions");
  if (!suggestions) return;

  const matches = matchingInventoryParts(query);
  if (!matches.length) {
    suggestions.innerHTML = '<div class="part-suggestion-empty">Nenhuma peça encontrada</div>';
    suggestions.classList.remove("hidden");
    return;
  }

  suggestions.innerHTML = matches.map((part) => `
    <button type="button" class="part-suggestion" data-id="${part.id}">
      <strong>${escapeHtml(part.code)}</strong>
      <span>${escapeHtml(part.description)}</span>
      <small>${escapeHtml(part.brand)} • ${currency.format(Number(part.salePrice || 0))}</small>
    </button>
  `).join("");
  suggestions.classList.remove("hidden");
}

function selectInventoryPart(row, part) {
  if (!row || !part) return;
  row.dataset.partId = part.id;
  row.querySelector(".part-code").value = part.code || "";
  row.querySelector(".part-description").value = part.description || "";
  row.querySelector(".part-value").value = Number(part.salePrice || 0).toFixed(2);
  closePartSuggestions(row);
  updateBudgetPreview();
}

function findInventoryPartByCode(code) {
  const normalized = String(code || "").trim().toLowerCase();
  return inventoryParts.find((part) => String(part.code || "").toLowerCase() === normalized);
}

function calculateSalePrice(costPrice) {
  return Number((Number(costPrice || 0) * 1.6).toFixed(2));
}

function updatePartSalePriceFromCost() {
  const salePrice = calculateSalePrice($("#partCostPrice").value);
  $("#partSalePrice").value = salePrice ? salePrice.toFixed(2) : "";
}

function fillPartForm(part) {
  selectedInventoryPartId = part?.id || null;
  $("#partBrand").value = part?.brand || "";
  $("#partCodePreview").value = part?.code || "";
  $("#partDescription").value = part?.description || "";
  $("#partCostPrice").value = part ? Number(part.costPrice || 0).toFixed(2) : "";
  $("#partSalePrice").value = part ? Number(part.salePrice || calculateSalePrice(part.costPrice)).toFixed(2) : "";
  $("#partStockQuantity").value = "";
  $("#partSerialNumber").value = part?.serialNumber || "";
  $("#partStockQuantity").focus();
}

function clearPartForm() {
  selectedInventoryPartId = null;
  $("#partCreateForm").reset();
  $("#partCodePreview").value = "";
  $("#partSalePrice").value = "";
  setMessage($("#partCreateMessage"), "");
}

function openPartLookupModal() {
  $("#partSearch").value = "";
  renderInventoryPartsTable();
  $("#partLookupModal").classList.remove("hidden");
  $("#partSearch").focus();
}

function closePartLookupModal() {
  $("#partLookupModal").classList.add("hidden");
}

function isPartRowComplete(row) {
  const quantity = Number(row.querySelector(".part-quantity").value || 0);
  const description = row.querySelector(".part-description").value.trim();
  const value = Number(row.querySelector(".part-value").value || 0);
  return quantity > 0 && description && value > 0;
}

function isLaborRowComplete(row) {
  const description = row.querySelector(".labor-description").value.trim();
  const value = Number(row.querySelector(".labor-value").value || 0);
  return description && value > 0;
}

function readPartRows() {
  return Array.from(document.querySelectorAll(".part-row"))
    .map((row) => ({
      id: row.dataset.partId ? Number(row.dataset.partId) : null,
      quantity: Number(row.querySelector(".part-quantity").value || 0),
      code: row.querySelector(".part-code").value.trim(),
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
    const code = row.querySelector(".part-code").value.trim();
    const description = row.querySelector(".part-description").value.trim();
    const value = Number(row.querySelector(".part-value").value || 0);
    const touched = code || description || value > 0;
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
  renderBudgetCustomerOptions();
  setAddressLookupState("");
  lastZipLookup = "";
  resetBudgetItems();
  setFormMode();
}

function loadBudgetIntoForm(budget) {
  $("#budgetCustomerSelect").value = "";
  $("#budgetVehicleSelect").value = "";
  $("#clientName").value = budget.clientName || "";
  $("#clientEmail").value = budget.clientEmail || "";
  $("#clientPhone").value = budget.clientPhone || "";
  $("#clientZip").value = budget.clientZip || "";
  $("#clientStreet").value = budget.clientStreet || budget.clientAddress || "";
  $("#clientNumber").value = budget.clientNumber || "";
  $("#clientDistrict").value = budget.clientDistrict || "";
  $("#clientState").value = budget.clientState || "";
  $("#vehicleBrand").value = budget.vehicleBrand || "";
  $("#vehicleModel").value = budget.vehicleModel || budget.vehicle || "";
  $("#vehicleYear").value = budget.vehicleYear || "";
  $("#plate").value = budget.plate || "";
  $("#vehicleColor").value = budget.vehicleColor || "";
  $("#vehicleKm").value = budget.vehicleKm || "";
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
  $("#modalApproveButton").classList.toggle("hidden", !canApproveBudget(budget));
  $("#modalRejectButton").classList.toggle("hidden", !canApproveBudget(budget));
  $("#modalCreateOsButton").classList.toggle("hidden", !canGenerateServiceOrder(budget));
  $("#modalDeleteButton").classList.toggle("hidden", !canDeleteBudget(budget));
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
  const group = sourceElement?.closest(".nav-group");
  if (!group) return;

  group.classList.add("suppress-submenu");
  sourceElement.blur();
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

  setPageTitle(labels[section] || labels.new);
  $("#budgetListTitle").textContent = listTitles[section] || listTitles.new;
  const showCreateForm = isNew && canAccess("budgets_manage");
  $("#statusFilter").value = isNew ? "todos" : section;
  $("#budgetSearch").value = "";
  $("#budgetSearchWrap").classList.toggle("hidden", isNew);
  $("#budgetList").classList.toggle("budget-list", isNew);
  $("#budgetForm").classList.toggle("hidden", !showCreateForm);
  $("#budgetListPanel").classList.toggle("hidden", showCreateForm);
  $("#newBudgetButton").classList.toggle("hidden", !showCreateForm);
  $("#budgetLayout").classList.toggle("list-only", !showCreateForm);
  $("#budgetLayout").classList.toggle("form-only", showCreateForm);
  renderBudgetList();
  suppressClickedSubmenu(sourceElement);
}

function openOperationsView(viewId, sourceElement = null) {
  switchView(viewId);
  markParentMenu("budgets");
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

function openInventorySection(sourceElement = null) {
  switchView("inventoryView");
  markParentMenu("inventory");
  setPageTitle("Gerenciamento de Estoque / Cadastro de peças");
  $("#partCreateForm").classList.toggle("hidden", !canAccess("inventory_manage"));
  renderInventoryPartsTable();
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
      password: $("#registerPassword").value,
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
    const login = $("#loginEmail").value.toLowerCase().trim();
    const password = $("#loginPassword").value;
    let result = null;
    try {
      result = await loginUser(login, password);
    } catch (error) {
      setMessage($("#loginMessage"), error.message);
      return;
    }

    const user = result.user;
    sessionStorage.setItem(SESSION_TOKEN_KEY, result.token);
    currentUser = {
      id: user.id,
      name: user.name,
      email: user.email,
      phone: user.phone || "",
      role: user.role || "user",
      accessLevel: user.accessLevel || (user.role === "admin" ? "administrador" : "analista"),
      isPlatformAdmin: Boolean(user.isPlatformAdmin)
    };
    updateRememberedLogin(login);
    sessionStorage.setItem("oficina_user", JSON.stringify(currentUser));
    await showApp();
  });

  $("#logoutButton").addEventListener("click", async () => {
    try {
      await api("/auth/logout", { method: "POST" });
    } catch {
      // Mesmo se o servidor já tiver descartado a sessão, a saída local deve continuar.
    }
    showAuth();
  });

  $("#refreshPlatformButton")?.addEventListener("click", loadPlatformDashboard);
  $("#clearPlatformCompanyFormButton")?.addEventListener("click", clearPlatformCompanyForm);
  ["platformStatusFilter", "platformPlanFilter", "platformSearchFilter"].forEach((id) => {
    $(`#${id}`)?.addEventListener("input", renderPlatformCompaniesTable);
    $(`#${id}`)?.addEventListener("change", renderPlatformCompaniesTable);
  });
  $("#platformSubscriptionCompany")?.addEventListener("change", (event) => {
    const company = platformCompanies.find((item) => Number(item.id) === Number(event.target.value));
    fillPlatformSubscriptionForm(company);
  });
  $("#platformSubscriptionForm")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!canAccess("platform")) return;

    const company = selectedPlatformCompany("platformSubscriptionCompany");
    if (!company?.subscriptionId) {
      setMessage($("#platformSubscriptionMessage"), "Selecione uma oficina com assinatura.");
      return;
    }

    try {
      await updatePlatformSubscription({
        id: company.subscriptionId,
        plan: $("#platformSubscriptionPlan").value,
        billingCycle: $("#platformSubscriptionBillingCycle").value,
        status: $("#platformSubscriptionStatus").value,
        currentPeriodStart: $("#platformPeriodStart").value,
        currentPeriodEnd: $("#platformPeriodEnd").value,
        trialEndsAt: $("#platformTrialEndsAt").value,
        updatedAt: new Date().toISOString()
      });
      setMessage($("#platformSubscriptionMessage"), "Assinatura atualizada com sucesso.", true);
      await loadPlatformDashboard();
    } catch (error) {
      setMessage($("#platformSubscriptionMessage"), error.message);
    }
  });
  $("#platformPaymentForm")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!canAccess("platform")) return;

    const company = selectedPlatformCompany("platformPaymentCompany");
    if (!company?.id) {
      setMessage($("#platformPaymentMessage"), "Selecione uma oficina.");
      return;
    }

    const now = new Date().toISOString();
    try {
      await createPlatformPayment({
        companyId: company.id,
        subscriptionId: company.subscriptionId || null,
        provider: $("#platformPaymentProvider").value.trim() || "manual",
        amount: Number($("#platformPaymentAmount").value || 0),
        status: $("#platformPaymentStatus").value,
        paidAt: $("#platformPaymentPaidAt").value,
        createdAt: now,
        updatedAt: now
      });
      $("#platformPaymentForm").reset();
      $("#platformPaymentProvider").value = "manual";
      setMessage($("#platformPaymentMessage"), "Pagamento registrado com sucesso.", true);
      await loadPlatformDashboard();
    } catch (error) {
      setMessage($("#platformPaymentMessage"), error.message);
    }
  });
  $("#platformCompanyForm")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!canAccess("platform")) return;

    const payload = {
      companyName: $("#platformCompanyName").value.trim(),
      document: $("#platformCompanyDocument").value.trim(),
      phone: $("#platformCompanyPhone").value.trim(),
      plan: $("#platformCompanyPlan").value,
      billingCycle: $("#platformCompanyBillingCycle").value,
      status: $("#platformCompanyStatus").value,
      ownerName: $("#platformOwnerName").value.trim(),
      ownerEmail: $("#platformOwnerEmail").value.toLowerCase().trim(),
      ownerUsername: $("#platformOwnerUsername").value.trim().toLowerCase(),
      ownerPhone: $("#platformOwnerPhone").value.trim(),
      ownerPassword: $("#platformOwnerPassword").value
    };

    try {
      await createPlatformCompany(payload);
      clearPlatformCompanyForm();
      setMessage($("#platformCompanyMessage"), "Oficina cadastrada com sucesso.", true);
      await loadPlatformDashboard();
    } catch (error) {
      setMessage($("#platformCompanyMessage"), error.message);
    }
  });

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
  document.addEventListener("click", (event) => {
    if (event.target.closest(".part-row")) return;
    document.querySelectorAll(".part-row").forEach(closePartSuggestions);
  });

  $("#newBudgetButton").addEventListener("click", () => openBudgetSection("new"));
  $("#toggleSidebarButton").addEventListener("click", toggleSidebar);
  $("#toggleThemeButton").addEventListener("click", toggleTheme);
  $("#cancelEditButton").addEventListener("click", clearBudgetForm);
  $("#statusFilter").addEventListener("change", renderBudgetList);
  $("#budgetSearch").addEventListener("input", renderBudgetList);
  $("#budgetCustomerSelect")?.addEventListener("change", (event) => {
    const customerId = event.target.value;
    const customer = customers.find((item) => Number(item.id) === Number(customerId));
    fillBudgetCustomerFields(customer);
    $("#budgetVehicleSelect").value = "";
    renderBudgetVehicleOptions(customerId);
  });
  $("#budgetVehicleSelect")?.addEventListener("change", (event) => {
    const vehicle = vehicles.find((item) => Number(item.id) === Number(event.target.value));
    fillBudgetVehicleFields(vehicle);
  });
  $("#serviceOrderStatusFilter")?.addEventListener("change", renderServiceOrdersView);
  $("#clearCustomerFormButton")?.addEventListener("click", clearCustomerForm);
  $("#clearVehicleFormButton")?.addEventListener("click", clearVehicleForm);
  $("#customerForm")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!canAccess("budgets_manage")) return;
    const payload = {
      id: editingCustomerId,
      name: $("#customerName").value.trim(),
      phone: $("#customerPhone").value.trim(),
      email: $("#customerEmail").value.toLowerCase().trim(),
      zip: $("#customerZip").value.trim(),
      street: $("#customerStreet").value.trim(),
      number: $("#customerNumber").value.trim(),
      district: $("#customerDistrict").value.trim(),
      state: $("#customerState").value.toUpperCase().trim(),
      notes: $("#customerNotes").value.trim()
    };
    try {
      editingCustomerId ? await updateCustomer(payload) : await createCustomer(payload);
      clearCustomerForm();
      setMessage($("#customerMessage"), "Cliente salvo com sucesso.", true);
      await loadCustomers();
    } catch (error) {
      setMessage($("#customerMessage"), error.message);
    }
  });
  $("#vehicleForm")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!canAccess("budgets_manage")) return;
    const payload = {
      id: editingVehicleId,
      customerId: Number($("#vehicleCustomer").value || 0),
      brand: $("#customerVehicleBrand").value.trim(),
      model: $("#customerVehicleModel").value.trim(),
      year: $("#customerVehicleYear").value.trim(),
      plate: $("#customerVehiclePlate").value.toUpperCase().trim(),
      color: $("#customerVehicleColor").value.trim(),
      km: $("#customerVehicleKm").value.trim(),
      notes: $("#vehicleNotes").value.trim()
    };
    try {
      editingVehicleId ? await updateVehicle(payload) : await createVehicle(payload);
      clearVehicleForm();
      setMessage($("#vehicleMessage"), "Veículo salvo com sucesso.", true);
      await loadCustomers();
    } catch (error) {
      setMessage($("#vehicleMessage"), error.message);
    }
  });
  $("#customersTable")?.addEventListener("click", (event) => {
    const button = event.target.closest("[data-action]");
    if (!button) return;
    if (button.dataset.action === "edit-customer") {
      const customer = customers.find((item) => Number(item.id) === Number(button.dataset.id));
      if (customer) fillCustomerForm(customer);
    }
  });
  $("#vehiclesTable")?.addEventListener("click", (event) => {
    const button = event.target.closest("[data-action]");
    if (!button) return;
    if (button.dataset.action === "edit-vehicle") {
      const vehicle = vehicles.find((item) => Number(item.id) === Number(button.dataset.id));
      if (vehicle) fillVehicleForm(vehicle);
    }
  });
  $("#serviceOrdersTable")?.addEventListener("change", async (event) => {
    const select = event.target.closest("[data-action='change-service-order-status']");
    if (!select) return;
    const order = serviceOrders.find((item) => Number(item.id) === Number(select.dataset.id));
    if (!order) return;
    try {
      await updateServiceOrder({ ...order, status: select.value });
      await loadServiceOrders();
    } catch (error) {
      alert(error.message);
    }
  });
  $("#addPartButton").addEventListener("click", () => addPartRow());
  $("#addLaborButton").addEventListener("click", () => addLaborRow());
  document.querySelectorAll("[data-budget-section]").forEach((button) => {
    button.addEventListener("click", () => openBudgetSection(button.dataset.budgetSection, button));
  });
  document.querySelectorAll(".side-submenu-button[data-view]").forEach((button) => {
    button.addEventListener("click", () => openOperationsView(button.dataset.view, button));
  });
  document.querySelectorAll("[data-finance-section]").forEach((button) => {
    button.addEventListener("click", () => openFinanceSection(button.dataset.financeSection, button));
  });
  document.querySelectorAll("[data-inventory-section]").forEach((button) => {
    button.addEventListener("click", () => openInventorySection(button));
  });
  document.querySelectorAll(".side-submenu-button").forEach((button) => {
    if (!button.dataset.settingsSection) return;
    button.addEventListener("click", () => {
      switchView("settingsView");
      switchSettingsSection(button.dataset.settingsSection);
      suppressClickedSubmenu(button);
    });
  });
  $("#openUserLookupButton").addEventListener("click", openUserLookupModal);
  $("#clearUserFormButton").addEventListener("click", clearUserForm);
  $("#userSearch").addEventListener("input", renderUsersTable);
  $("#closeUserLookupModal").addEventListener("click", closeUserLookupModal);
  $("#userLookupModal").addEventListener("click", (event) => {
    if (event.target.id === "userLookupModal") closeUserLookupModal();
  });
  $("#partSearch").addEventListener("input", renderInventoryPartsTable);
  $("#openPartLookupButton").addEventListener("click", openPartLookupModal);
  $("#closePartLookupModal").addEventListener("click", closePartLookupModal);
  $("#partLookupModal").addEventListener("click", (event) => {
    if (event.target.id === "partLookupModal") closePartLookupModal();
  });
  $("#clearPartFormButton").addEventListener("click", clearPartForm);
  $("#partCostPrice").addEventListener("input", updatePartSalePriceFromCost);
  $("#partCodePreview").addEventListener("blur", () => {
    const part = findInventoryPartByCode($("#partCodePreview").value);
    if (part) {
      fillPartForm(part);
      setMessage($("#partCreateMessage"), "Peça carregada. Informe a quantidade de entrada para somar ao estoque.", true);
    }
  });
  $("#partCreateForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!canAccess("inventory_manage")) return;

    updatePartSalePriceFromCost();
    const existingPart = selectedInventoryPartId
      ? inventoryParts.find((item) => item.id === Number(selectedInventoryPartId))
      : findInventoryPartByCode($("#partCodePreview").value);
    const quantityEntry = Number($("#partStockQuantity").value || 0);
    const payload = {
      brand: $("#partBrand").value.trim(),
      code: $("#partCodePreview").value.trim(),
      description: $("#partDescription").value.trim(),
      costPrice: Number($("#partCostPrice").value || 0),
      salePrice: Number($("#partSalePrice").value || 0),
      stockQuantity: quantityEntry,
      serialNumber: $("#partSerialNumber").value.trim(),
      updatedAt: new Date().toISOString()
    };

    if (existingPart) {
      await updateInventoryPart({
        ...existingPart,
        ...payload,
        code: existingPart.code,
        stockQuantity: Number(existingPart.stockQuantity || 0) + quantityEntry,
        createdAt: existingPart.createdAt
      });
    } else {
      await createInventoryPart({
        ...payload,
        code: "",
        createdAt: new Date().toISOString()
      });
    }

    clearPartForm();
    setMessage($("#partCreateMessage"), existingPart ? "Entrada registrada no estoque." : "Peça cadastrada com sucesso.", true);
    await loadInventoryParts();
  });
  $("#supplierSearch").addEventListener("input", (event) => {
    clearSupplierSelection();
    renderSupplierSuggestions(event.target.value);
  });
  $("#supplierSuggestions").addEventListener("click", (event) => {
    const button = event.target.closest("[data-supplier-id]");
    if (!button) return;

    const supplier = suppliers.find((item) => item.id === Number(button.dataset.supplierId));
    selectSupplier(supplier);
  });
  $("#supplierCnpj").addEventListener("input", () => {
    clearSupplierSelection();
  });
  $("#payableForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!canAccess("billing_view")) return;

    const now = new Date().toISOString();
    let supplier = selectedSupplierId
      ? suppliers.find((item) => item.id === Number(selectedSupplierId))
      : suppliers.find((item) => String(item.cnpj || "").replace(/\D/g, "") === $("#supplierCnpj").value.replace(/\D/g, ""));

    if (!supplier) {
      supplier = await createSupplier({
        cnpj: $("#supplierCnpj").value.trim(),
        corporateName: $("#supplierCorporateName").value.trim(),
        tradeName: $("#supplierTradeName").value.trim(),
        phone: $("#supplierPhone").value.trim(),
        sellerName: $("#supplierSellerName").value.trim(),
        createdAt: now,
        updatedAt: now
      });
      await loadSuppliers();
    }

    await createPayable({
      description: $("#payableDescription").value.trim(),
      entryDate: $("#payableEntryDate").value,
      competenceDate: $("#payableCompetenceDate").value,
      category: $("#payableCategory").value,
      invoiceNumber: $("#payableInvoiceNumber").value.trim(),
      supplierId: supplier.id,
      supplierCnpj: supplier.cnpj,
      supplierName: supplierDisplayName(supplier),
      amount: Number($("#payableAmount").value || 0),
      notes: $("#payableNotes").value.trim(),
      createdAt: now,
      updatedAt: now
    });

    clearPayableForm();
    setMessage($("#payableMessage"), "Compra cadastrada com sucesso.", true);
    await loadPayables();
  });
  $("#clearPayableFormButton").addEventListener("click", clearPayableForm);
  $("#partsInventoryTable").addEventListener("click", async (event) => {
    const button = event.target.closest("button[data-part-action]");
    if (!button || !canAccess("inventory_manage")) return;

    const part = inventoryParts.find((item) => item.id === Number(button.dataset.id));
    if (!part) return;

    if (button.dataset.partAction === "select") {
      fillPartForm(part);
      setMessage($("#partCreateMessage"), "Peça selecionada. Informe a quantidade de entrada para somar ao estoque.", true);
      closePartLookupModal();
      return;
    }

    const confirmed = confirm(`Excluir a peça ${part.code} - ${part.description}?`);
    if (!confirmed) return;

    await deleteInventoryPart(part.id);
    await loadInventoryParts();
  });
  $("#usersTable").addEventListener("click", async (event) => {
    const button = event.target.closest("button[data-user-action]");
    if (!button || !canAccess("settings")) return;

    if (button.dataset.userAction === "select") {
      const user = findUserById(button.dataset.id);
      fillUserForm(user);
      closeUserLookupModal();
      return;
    }

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
    const password = $("#newUserPassword").value;
    const selectedUser = editingUserId ? findUserById(editingUserId) : null;
    const isEditingUser = Boolean(editingUserId);
    const existing = await findUserByEmail(email);
    if (existing && existing.id !== editingUserId) {
      setMessage($("#userCreateMessage"), "Já existe um usuário com este email.");
      return;
    }

    users = await api("/users");
    const usernameExists = users.some((user) => user.id !== editingUserId && String(user.username || "").toLowerCase() === username);
    if (usernameExists) {
      setMessage($("#userCreateMessage"), "Já existe um usuário com este nome de usuário.");
      return;
    }

    if (!isEditingUser && password.length < 6) {
      setMessage($("#userCreateMessage"), "Informe uma senha com pelo menos 6 caracteres.");
      return;
    }

    if (isEditingUser && password && password.length < 6) {
      setMessage($("#userCreateMessage"), "A nova senha precisa ter pelo menos 6 caracteres.");
      return;
    }

    const accessLevel = $("#newUserAccessLevel").value;
    const payload = {
      ...(selectedUser || {}),
      name: $("#newUserName").value.trim(),
      username,
      email,
      phone: $("#newUserPhone").value.trim(),
      ...(password ? { password } : {}),
      role: selectedUser?.role === "admin" ? "admin" : (accessLevel === "administrador" ? "admin-user" : "user"),
      accessLevel,
      blocked: selectedUser?.blocked || false,
      createdAt: selectedUser?.createdAt || new Date().toISOString(),
      updatedAt: new Date().toISOString()
    };

    if (isEditingUser) {
      await updateUser(payload);
      if (currentUser?.id === payload.id) {
        currentUser = {
          id: payload.id,
          name: payload.name,
          email: payload.email,
          phone: payload.phone || "",
          role: payload.role || "user",
          accessLevel: payload.accessLevel,
          isPlatformAdmin: Boolean(payload.isPlatformAdmin)
        };
        sessionStorage.setItem("oficina_user", JSON.stringify(currentUser));
      }
    } else {
      await createUser(payload);
    }

    clearUserForm();
    setMessage($("#userCreateMessage"), isEditingUser ? "Usuário atualizado com sucesso." : "Usuário criado com sucesso.", true);
    await loadAllUsers();
  });

  $("#budgetForm").addEventListener("input", (event) => {
    if (event.target.matches(".part-quantity, .part-value, .labor-value, .part-description, .part-code, .labor-description")) {
      updateBudgetPreview();
    }

    if (event.target.matches(".part-description")) {
      const row = event.target.closest(".part-row");
      delete row.dataset.partId;
      renderPartSuggestions(row, event.target.value);
    }

    if (event.target.matches(".part-code")) {
      const row = event.target.closest(".part-row");
      delete row.dataset.partId;
      const part = findInventoryPartByCode(event.target.value);
      if (part) {
        selectInventoryPart(row, part);
      } else {
        renderPartSuggestions(row, event.target.value);
      }
    }

    if (event.target.matches("#clientZip")) {
      const previousValue = event.target.value;
      event.target.value = formatZip(previousValue);
      const zip = event.target.value.replace(/\D/g, "");
      if (zip.length < 8) lastZipLookup = "";
      if (zip.length === 8) lookupAddressByZip();
    }

    if (event.target.matches("#vehicleKm")) {
      event.target.value = sanitizeVehicleKmInput(event.target.value);
    }

    if (event.target.matches("#plate, #clientState")) {
      event.target.value = event.target.value.toUpperCase();
    }
  });

  $("#budgetForm").addEventListener("focusin", (event) => {
    if (!event.target.matches(".part-description, .part-code")) return;
    const row = event.target.closest(".part-row");
    renderPartSuggestions(row, event.target.value);
  });

  $("#plate").addEventListener("blur", () => {
    $("#plate").value = $("#plate").value.toUpperCase();
    const vehicle = findVehicleByPlateInput();
    if (vehicle) fillBudgetVehicleFields(vehicle);
  });

  ["clientEmail", "clientPhone"].forEach((id) => {
    $(`#${id}`)?.addEventListener("blur", () => {
      if ($("#budgetCustomerSelect").value) return;
      const customer = findCustomerByContact();
      if (!customer) return;
      $("#budgetCustomerSelect").value = customer.id;
      fillBudgetCustomerFields(customer);
      renderBudgetVehicleOptions(customer.id);
    });
  });

  $("#vehicleKm").addEventListener("blur", () => {
    $("#vehicleKm").value = formatVehicleKm($("#vehicleKm").value);
  });

  $("#budgetForm").addEventListener("keydown", (event) => {
    if (event.key !== "Enter" || event.target.tagName === "TEXTAREA") return;

    const partRow = event.target.closest(".part-row");
    if (partRow && isPartRowComplete(partRow)) {
      event.preventDefault();
      addPartRow();
      document.querySelector("#partsRows .part-row:last-child .part-description").focus();
      return;
    }

    const laborRow = event.target.closest(".labor-row");
    if (laborRow && isLaborRowComplete(laborRow)) {
      event.preventDefault();
      addLaborRow();
      document.querySelector("#laborRows .labor-row:last-child .labor-description").focus();
    }
  });

  $("#budgetForm").addEventListener("click", (event) => {
    const suggestion = event.target.closest(".part-suggestion");
    if (suggestion) {
      const row = suggestion.closest(".part-row");
      const part = inventoryParts.find((item) => item.id === Number(suggestion.dataset.id));
      selectInventoryPart(row, part);
      return;
    }

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

    const plate = $("#plate").value.trim().toUpperCase();
    if (!isValidBrazilianPlate(plate)) {
      alert("Informe uma placa válida no formato Mercosul (ABC1D23) ou antigo (ABC1234).");
      $("#plate").focus();
      return;
    }

    const vehicleKm = formatVehicleKm($("#vehicleKm").value);
    $("#vehicleKm").value = vehicleKm;
    if (!isValidVehicleKm(vehicleKm)) {
      alert("Informe o KM com números e três dígitos após o ponto. Exemplo: 310.635.");
      $("#vehicleKm").focus();
      return;
    }

    const partsValue = parts.reduce((sum, part) => sum + (part.quantity * part.value), 0);
    const laborValue = labor.reduce((sum, item) => sum + item.value, 0);
    const vehicleBrand = $("#vehicleBrand").value.trim();
    const vehicleModel = $("#vehicleModel").value.trim();
    const vehicleYear = $("#vehicleYear").value.trim();
    const clientStreet = $("#clientStreet").value.trim();
    const clientNumber = $("#clientNumber").value.trim();

    const originalBudget = editingBudgetId ? findBudgetById(editingBudgetId) : null;
    const now = new Date().toISOString();
    const budget = {
      ...(originalBudget || {}),
      userId: originalBudget?.userId || currentUser.id,
      clientName: $("#clientName").value.trim(),
      clientEmail: $("#clientEmail").value.toLowerCase().trim(),
      clientPhone: $("#clientPhone").value.trim(),
      clientZip: $("#clientZip").value.trim(),
      clientStreet,
      clientNumber,
      clientAddress: [clientStreet, clientNumber].filter(Boolean).join(", "),
      clientDistrict: $("#clientDistrict").value.trim(),
      clientState: $("#clientState").value.trim().toUpperCase(),
      vehicleBrand,
      vehicleModel,
      vehicleYear,
      vehicle: [vehicleBrand, vehicleModel].filter(Boolean).join(" "),
      plate,
      vehicleColor: $("#vehicleColor").value.trim(),
      vehicleKm,
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
    openBudgetSection("pendente");
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
    if (button.dataset.action === "approve" && canApproveBudget(budget)) await changeBudgetStatus(button.dataset.id, STATUS.approved);
    if (button.dataset.action === "reject" && canApproveBudget(budget)) await changeBudgetStatus(button.dataset.id, STATUS.rejected);
    if (button.dataset.action === "create-os" && canGenerateServiceOrder(budget)) await generateServiceOrderFromBudget(budget);
    if (button.dataset.action === "delete" && canDeleteBudget(budget)) await removeBudget(button.dataset.id);
  });

  $("#billingTable").addEventListener("click", async (event) => {
    const button = event.target.closest("button[data-action]");
    if (!button) return;

    const budget = findBudgetById(button.dataset.id);
    if (!budget) return;

    if (button.dataset.action === "view") openBudgetModal(budget);
    if (button.dataset.action === "edit" && canAccess("billing_edit")) beginBudgetEdit(budget);
    if (button.dataset.action === "delete" && canDeleteBudget(budget)) await removeBudget(button.dataset.id);
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
  $("#modalApproveButton").addEventListener("click", async () => {
    const budget = selectedBudget();
    if (canApproveBudget(budget)) await changeBudgetStatus(budget.id, STATUS.approved);
  });
  $("#modalRejectButton").addEventListener("click", async () => {
    const budget = selectedBudget();
    if (canApproveBudget(budget)) await changeBudgetStatus(budget.id, STATUS.rejected);
  });
  $("#modalCreateOsButton").addEventListener("click", async () => {
    const budget = selectedBudget();
    if (canGenerateServiceOrder(budget)) await generateServiceOrderFromBudget(budget);
  });
  $("#modalDeleteButton").addEventListener("click", async () => {
    const budget = selectedBudget();
    if (canDeleteBudget(budget)) await removeBudget(budget.id);
  });
}

async function init() {
  await api("/health");
  loadUiPreferences();
  loadRememberedLogin();
  bindEvents();
  resetBudgetItems();
  clearPayableForm();

  const sessionUser = sessionStorage.getItem("oficina_user");
  const sessionToken = sessionStorage.getItem(SESSION_TOKEN_KEY);
  if (sessionUser && sessionToken) {
    currentUser = JSON.parse(sessionUser);
    currentUser.isPlatformAdmin = Boolean(currentUser.isPlatformAdmin);
    try {
      await showApp();
    } catch (error) {
      console.warn(error);
      showAuth();
    }
  }
}

init().catch((error) => {
  console.error(error);
  alert("Nao foi possivel iniciar o banco SQLite local. Abra o sistema pelo server.py.");
});
