(function () {
  "use strict";

  const table = document.querySelector(".table-panel .data-table");
  if (!table) return;

  function setText(selector, value) {
    const element = document.querySelector(selector);
    if (element) element.textContent = value;
  }

  function renderRecentPayments(payments, loans, customers) {
    const body = table.querySelector("tbody");
    body.replaceChildren();
    payments.slice(0, 5).forEach((payment) => {
      const loan = loans.get(payment.loan_id);
      const customer = loan && customers.get(loan.customer_id);
      const row = document.createElement("tr");
      AppUI.addPrimaryCell(row, payment.payment_id, payment.external_reference);
      AppUI.addTextCell(row, customer || "Unknown customer");
      AppUI.addTextCell(row, AppUI.formatDate(payment.received_at, true));
      AppUI.addTextCell(row, payment.payment_method.replaceAll("_", " "));
      AppUI.addTextCell(row, AppUI.formatMoney(payment.amount_minor, payment.currency_code), "amount-cell");
      AppUI.addBadgeCell(row, payment.payment_status);
      body.append(row);
    });
    if (!payments.length) AppUI.showTableMessage(table, "No payments were returned by the API.");
  }

  function formatCurrencySummary(amounts) {
    return amounts.length
      ? amounts.map((item) => AppUI.formatMoney(item.amount_minor, item.currency_code)).join(" · ")
      : "No records";
  }

  function renderDelinquency(report) {
    const metrics = document.querySelectorAll(".metric-grid .metric-value");
    if (metrics[3]) metrics[3].textContent = String(report.overdue_loan_count);
    const amount = document.querySelector(".overdue-total strong");
    if (amount) amount.textContent = formatCurrencySummary(report.total_arrears_by_currency);
    const chart = document.querySelector(".distribution-chart");
    if (!chart) return;
    chart.replaceChildren();
    const categories = report.categories;
    const counts = categories.map((item) => item.loan_count);
    const max = Math.max(1, ...counts);
    const colors = ["bar-blue", "bar-gold", "bar-orange", "bar-red"];
    categories.forEach((category, index) => {
      const row = document.createElement("div");
      row.className = "chart-row";
      const label = document.createElement("span");
      label.className = "chart-label";
      label.textContent = category.bucket === "91+" ? "91+ days" : `${category.bucket} days`;
      const track = document.createElement("div");
      track.className = "chart-track";
      const bar = document.createElement("span");
      bar.className = `chart-bar ${colors[index]}`;
      bar.style.width = `${(counts[index] / max) * 100}%`;
      track.append(bar);
      const count = document.createElement("b");
      count.textContent = String(counts[index]);
      row.append(label, track, count);
      chart.append(row);
    });
    const heading = document.querySelector(".chart-heading .muted-label");
    if (heading) heading.textContent = `${report.overdue_loan_count} overdue loans`;
  }

  async function loadDashboard() {
    AppUI.setApiState("Loading portfolio records from the Flask API…");
    AppUI.showTableMessage(table, "Loading recent payments…");
    document.querySelectorAll(".metric-grid .metric-value").forEach((value) => {
      value.textContent = "Loading";
    });
    const overdueAmount = document.querySelector(".overdue-total strong");
    if (overdueAmount) overdueAmount.textContent = "Loading";
    const chart = document.querySelector(".distribution-chart");
    if (chart) chart.textContent = "Loading delinquency data…";
    try {
      const [customerResponse, loanResponse, paymentResponse, caseResponse, delinquencyResponse] = await Promise.all([
        ApiClient.get("/customers"),
        ApiClient.get("/loans"),
        ApiClient.get("/payments"),
        ApiClient.get("/collection-cases"),
        ApiClient.get("/reports/delinquency")
      ]);
      const customers = new Map(customerResponse.data.map((customer) => [
        customer.customer_id,
        `${customer.first_name} ${customer.last_name}`
      ]));
      const loans = new Map(loanResponse.data.map((loan) => [loan.loan_id, loan]));
      const cases = caseResponse.data;
      const activeLoans = loanResponse.data.filter((loan) => loan.loan_status === "active").length;
      const activeCases = cases.filter((item) => ["open", "in_progress"].includes(item.case_status));
      const metrics = document.querySelectorAll(".metric-grid .metric-value");
      [customerResponse.data.length, loanResponse.data.length, activeLoans, 0].forEach((value, index) => {
        if (metrics[index]) metrics[index].textContent = String(value);
      });

      const trend = document.querySelector(".trend-pill");
      if (trend) trend.textContent = "Current schedule and posted allocations";
      const chartFooter = document.querySelector(".overdue-panel .panel-footer-note");
      if (chartFooter) chartFooter.textContent = "Calculated from installment schedules and active posted payment allocations.";
      renderDelinquency(delinquencyResponse.data);

      setText(".case-count strong", String(activeCases.length));
      setText(".case-count span", "active cases");
      const priorities = ["high", "medium", "low"];
      document.querySelectorAll(".case-priority-list > div").forEach((item, index) => {
        const count = activeCases.filter((record) => record.priority === priorities[index]).length;
        const value = item.querySelector("b");
        if (value) value.textContent = String(count);
      });
      renderRecentPayments(paymentResponse.data, loans, customers);
      AppUI.clearApiState();
    } catch (error) {
      AppUI.setApiState(error.message, "error");
      AppUI.showTableMessage(table, "Recent payments could not be loaded.");
      const values = document.querySelectorAll(".metric-grid .metric-value");
      values.forEach((value) => { value.textContent = "Unavailable"; });
      if (overdueAmount) overdueAmount.textContent = "Unavailable";
      if (chart) chart.textContent = "Delinquency data is unavailable from the current API.";
      setText(".case-count strong", "Unavailable");
      document.querySelectorAll(".case-priority-list b").forEach((value) => {
        value.textContent = "Unavailable";
      });
    }
  }

  loadDashboard();
})();
