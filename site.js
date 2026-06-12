const currency = new Intl.NumberFormat("pt-BR", {
  style: "currency",
  currency: "BRL"
});

const featureLabels = {
  dashboard: "Painel",
  budgets: "Orçamentos",
  billing: "Financeiro",
  inventory: "Estoque",
  users: "Usuários",
  advanced_reports: "Relatórios avançados",
  priority_support: "Suporte prioritário"
};

let publicPlans = [];
let billingCycles = {};

function qs(selector) {
  return document.querySelector(selector);
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

async function loadPlans() {
  const response = await fetch("/api/public/plans", { headers: { Accept: "application/json" } });
  if (!response.ok) {
    throw new Error("Não foi possível carregar os planos.");
  }
  const data = await response.json();
  publicPlans = data.plans || [];
  billingCycles = data.billingCycles || {};
  return data;
}

function planPrice(plan, cycle = "monthly") {
  const value = plan?.prices?.[cycle] ?? plan?.currentPrice ?? 0;
  return currency.format(Number(value || 0));
}

function planUrl(plan, cycle = "monthly") {
  return `assinar.html?plano=${encodeURIComponent(plan.code)}&ciclo=${encodeURIComponent(cycle)}`;
}

function renderPlansGrid() {
  const container = qs("#plansGrid");
  if (!container) return;
  if (!publicPlans.length) {
    container.innerHTML = '<article class="plan-card loading">Planos indisponíveis no momento.</article>';
    return;
  }
  container.innerHTML = publicPlans.map((plan) => {
    const highlight = plan.code === "profissional" ? " highlight" : "";
    const features = (plan.features || []).slice(0, 5).map((feature) => (
      `<li>${escapeHtml(featureLabels[feature] || feature)}</li>`
    )).join("");
    return `
      <article class="plan-card${highlight}">
        <div>
          <div class="plan-title-row">
            <h3>${escapeHtml(plan.name)}</h3>
            ${plan.code === "profissional" ? '<span class="plan-tag">Mais escolhido</span>' : ""}
          </div>
          <p>${escapeHtml(plan.description)}</p>
        </div>
        <div class="plan-price">
          <strong>${escapeHtml(planPrice(plan, "monthly"))}</strong>
          <span>/mês</span>
        </div>
        <ul class="plan-features">${features}</ul>
        <a class="button button-primary" href="${planUrl(plan, "monthly")}">Escolher ${escapeHtml(plan.name)}</a>
      </article>
    `;
  }).join("");
}

function selectedParams() {
  const params = new URLSearchParams(window.location.search);
  const cycleAliases = {
    annual: "yearly",
    anual: "yearly",
    quarterly: "quarterly",
    trimestral: "quarterly",
    mensal: "monthly"
  };
  const rawCycle = params.get("ciclo") || params.get("cycle") || "monthly";
  return {
    plan: params.get("plano") || params.get("plan") || "profissional",
    cycle: cycleAliases[rawCycle] || rawCycle
  };
}

function renderSignupOptions() {
  const planSelect = qs("#leadPlan");
  const cycleSelect = qs("#leadCycle");
  if (!planSelect || !cycleSelect) return;

  const selected = selectedParams();
  planSelect.innerHTML = publicPlans.map((plan) => (
    `<option value="${escapeHtml(plan.code)}">${escapeHtml(plan.name)}</option>`
  )).join("");
  cycleSelect.innerHTML = Object.entries(billingCycles).map(([value, label]) => (
    `<option value="${escapeHtml(value)}">${escapeHtml(label)}</option>`
  )).join("");
  planSelect.value = publicPlans.some((plan) => plan.code === selected.plan) ? selected.plan : "profissional";
  cycleSelect.value = billingCycles[selected.cycle] ? selected.cycle : "monthly";
  renderSelectedPlanPreview();
}

function renderSelectedPlanPreview() {
  const preview = qs("#selectedPlanPreview");
  const planSelect = qs("#leadPlan");
  const cycleSelect = qs("#leadCycle");
  if (!preview || !planSelect || !cycleSelect) return;
  const plan = publicPlans.find((item) => item.code === planSelect.value) || publicPlans[0];
  const cycle = cycleSelect.value || "monthly";
  if (!plan) {
    preview.innerHTML = "";
    return;
  }
  preview.innerHTML = `
    <span class="eyebrow">Plano selecionado</span>
    <h3>${escapeHtml(plan.name)}</h3>
    <p>${escapeHtml(plan.description)}</p>
    <div class="plan-price">
      <strong>${escapeHtml(planPrice(plan, cycle))}</strong>
      <span>${escapeHtml(billingCycles[cycle] || "")}</span>
    </div>
  `;
}

async function submitLead(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const status = qs("#leadMessageStatus");
  const button = form.querySelector("button[type='submit']");
  const payload = {
    name: qs("#leadName").value,
    email: qs("#leadEmail").value,
    phone: qs("#leadPhone").value,
    companyName: qs("#leadCompany").value,
    plan: qs("#leadPlan").value,
    billingCycle: qs("#leadCycle").value,
    message: qs("#leadMessage").value,
    source: "site-divulgacao",
    website: qs("#leadWebsite").value
  };

  status.className = "form-status";
  status.textContent = "Enviando interesse...";
  button.disabled = true;
  try {
    const response = await fetch("/api/public/leads", {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(payload)
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(data.error || "Não foi possível registrar seu interesse.");
    }
    status.className = "form-status success";
    status.textContent = "Interesse registrado. Nossa equipe acompanha pelo Painel Master.";
    form.reset();
    renderSignupOptions();
  } catch (error) {
    status.className = "form-status error";
    status.textContent = error.message;
  } finally {
    button.disabled = false;
  }
}

async function init() {
  try {
    await loadPlans();
    renderPlansGrid();
    renderSignupOptions();
  } catch (error) {
    const container = qs("#plansGrid");
    if (container) {
      container.innerHTML = `<article class="plan-card loading">${escapeHtml(error.message)}</article>`;
    }
    const status = qs("#leadMessageStatus");
    if (status) {
      status.className = "form-status error";
      status.textContent = error.message;
    }
  }

  qs("#leadForm")?.addEventListener("submit", submitLead);
  qs("#leadPlan")?.addEventListener("change", renderSelectedPlanPreview);
  qs("#leadCycle")?.addEventListener("change", renderSelectedPlanPreview);
}

init();
