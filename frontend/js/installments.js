(function () {
  "use strict";

  const table = document.querySelector("#installment-table");
  if (!table) return;
  const search = document.querySelector('[data-filter-table="#installment-table"]');
  const statusFilter = document.querySelector("#installment-status");

  function applyFilters() {
    AppUI.filterTable(table, search?.value, statusFilter?.value);
  }

  async function loadInstallments() {
    AppUI.setApiState("Loading installment schedules from the Flask API…");
    AppUI.showTableMessage(table, "Loading installment schedules…");
    document.querySelectorAll(".metric-grid .metric-value").forEach((metric) => {
      metric.textContent = "Loading";
    });
    try {
      const response = await ApiClient.get("/installments");
      const installments = response.data;
      const counts = { paid: 0, partial: 0, unpaid: 0 };
      installments.forEach((item) => {
        const remaining = item.remaining_principal_minor + item.remaining_interest_minor;
        const paid = item.paid_principal_minor + item.paid_interest_minor;
        const status = remaining === 0 ? "paid" : paid > 0 ? "partial" : "unpaid";
        counts[status] += 1;
      });
      const metrics = document.querySelectorAll(".metric-grid .metric-value");
      [installments.length, counts.paid, counts.partial, counts.unpaid].forEach((value, index) => {
        if (metrics[index]) metrics[index].textContent = String(value);
      });

      const body = table.querySelector("tbody");
      body.replaceChildren();
      installments.forEach((item) => {
        const scheduled = item.scheduled_principal_minor + item.scheduled_interest_minor;
        const paid = item.paid_principal_minor + item.paid_interest_minor;
        const outstanding = item.remaining_principal_minor + item.remaining_interest_minor;
        const status = outstanding === 0 ? "paid" : paid > 0 ? "partial" : "unpaid";
        const row = document.createElement("tr");
        row.dataset.status = status;
        row.dataset.search = `${item.installment_id} ${item.loan_id} ${item.installment_number} ${item.due_date}`.toLowerCase();
        AppUI.addPrimaryCell(row, item.installment_id, `Installment ${item.installment_number}`);
        AppUI.addTextCell(row, item.loan_id);
        AppUI.addTextCell(row, AppUI.formatDate(item.due_date));
        AppUI.addTextCell(row, AppUI.formatMoney(scheduled), "amount-cell");
        AppUI.addTextCell(row, AppUI.formatMoney(paid));
        AppUI.addTextCell(row, AppUI.formatMoney(outstanding));
        AppUI.addBadgeCell(row, status === "partial" ? "Partially paid" : status);
        body.append(row);
      });
      if (!installments.length) AppUI.showTableMessage(table, "No installments were returned by the API.");
      const count = document.querySelector("[data-visible-count]");
      if (count) count.textContent = `${installments.length} ${installments.length === 1 ? "record" : "records"}`;
      applyFilters();
      AppUI.clearApiState();
    } catch (error) {
      AppUI.setApiState(error.message, "error");
      AppUI.showTableMessage(table, "Installment schedules could not be loaded.");
      document.querySelectorAll(".metric-grid .metric-value").forEach((metric) => {
        metric.textContent = "Unavailable";
      });
    }
  }

  search?.addEventListener("input", applyFilters);
  statusFilter?.addEventListener("change", applyFilters);
  table.setAttribute("aria-label", "Installment schedules from the Flask API");
  loadInstallments();
})();
