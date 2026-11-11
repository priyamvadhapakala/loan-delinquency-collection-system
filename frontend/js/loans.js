(function () {
  "use strict";

  const table = document.querySelector("#loan-table");
  if (!table) return;
  const search = document.querySelector('[data-filter-table="#loan-table"]');
  const statusFilter = document.querySelector("#loan-status");
  const metrics = document.querySelectorAll(".metric-grid .metric-value");

  function applyFilters() {
    AppUI.filterTable(table, search?.value, statusFilter?.value);
  }

  async function loadLoans() {
    AppUI.setApiState("Loading loan records from the Flask API…");
    AppUI.showTableMessage(table, "Loading loan records…");
    metrics.forEach((metric) => { metric.textContent = "Loading"; });
    try {
      const [loanResponse, customerResponse, delinquencyResponse] = await Promise.all([
        ApiClient.get("/loans"),
        ApiClient.get("/customers"),
        ApiClient.get("/reports/delinquency")
      ]);
      const customers = new Map(customerResponse.data.map((customer) => [
        customer.customer_id,
        `${customer.first_name} ${customer.last_name}`
      ]));
      const loans = loanResponse.data;
      const activeCount = loans.filter((loan) => loan.loan_status === "active").length;
      const overdueCount = delinquencyResponse.data.overdue_loan_count;
      [loans.length, activeCount, overdueCount, loans.length].forEach((value, index) => {
        if (metrics[index]) metrics[index].textContent = String(value);
      });

      const body = table.querySelector("tbody");
      body.replaceChildren();
      loans.forEach((loan) => {
        const row = document.createElement("tr");
        const customerName = customers.get(loan.customer_id) || "Unknown customer";
        const rate = `${(loan.annual_interest_rate_bps / 100).toFixed(2)}%`;
        row.dataset.status = loan.loan_status;
        row.dataset.search = `${loan.loan_id} ${loan.loan_reference} ${loan.customer_id} ${customerName}`.toLowerCase();
        row.dataset.details = JSON.stringify([
          ["Loan ID", loan.loan_id],
          ["Reference", loan.loan_reference],
          ["Customer", `${customerName} · ${loan.customer_id}`],
          ["Original principal", AppUI.formatMoney(loan.principal_amount_minor, loan.currency_code)],
          ["Annual rate", rate],
          ["Term", `${loan.term_months} months`],
          ["Disbursement date", AppUI.formatDate(loan.disbursement_date)],
          ["First due date", AppUI.formatDate(loan.first_due_date)],
          ["Status", loan.loan_status]
        ]);
        AppUI.addPrimaryCell(row, loan.loan_id, loan.loan_reference);
        AppUI.addPrimaryCell(row, customerName, loan.customer_id);
        AppUI.addTextCell(row, AppUI.formatMoney(loan.principal_amount_minor, loan.currency_code), "amount-cell");
        AppUI.addTextCell(row, rate);
        AppUI.addTextCell(row, `${loan.term_months} months`);
        AppUI.addTextCell(row, AppUI.formatDate(loan.first_due_date));
        AppUI.addBadgeCell(row, loan.loan_status);
        AppUI.addActionCell(row, "show-details", "View details");
        body.append(row);
      });
      if (!loans.length) AppUI.showTableMessage(table, "No loans were returned by the API.");
      const count = document.querySelector("[data-visible-count]");
      if (count) count.textContent = `${loans.length} ${loans.length === 1 ? "record" : "records"}`;
      applyFilters();
      AppUI.clearApiState();
    } catch (error) {
      AppUI.setApiState(error.message, "error");
      AppUI.showTableMessage(table, "Loan records could not be loaded.");
      metrics.forEach((metric) => { metric.textContent = "Unavailable"; });
    }
  }

  search?.addEventListener("input", applyFilters);
  statusFilter?.addEventListener("change", applyFilters);
  table.setAttribute("aria-label", "Loan records from the Flask API");
  loadLoans();
})();
