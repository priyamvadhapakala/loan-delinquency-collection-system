(function () {
  "use strict";

  const dialog = document.querySelector("#payment-dialog");
  const form = document.querySelector("#payment-form");
  const table = document.querySelector("#payment-table");
  const message = document.querySelector("#payment-form-message");
  if (!dialog || !form || !table) return;

  const search = document.querySelector('[data-filter-table="#payment-table"]');
  const statusFilter = document.querySelector("#payment-status");
  const loanSelect = form.elements.namedItem("loan_id");
  const submitButton = form.querySelector('[type="submit"]');
  let loans = [];
  let customers = new Map();
  let payments = [];

  function applyFilters() {
    AppUI.filterTable(table, search?.value, statusFilter?.value);
  }

  function renderLoans() {
    loanSelect.replaceChildren(new Option("Choose a loan", ""));
    loans.forEach((loan) => {
      const customer = customers.get(loan.customer_id) || "Unknown customer";
      loanSelect.add(new Option(`${loan.loan_id} · ${customer} · ${loan.currency_code}`, loan.loan_id));
    });
  }

  function renderPayments() {
    const body = table.querySelector("tbody");
    body.replaceChildren();
    payments.forEach((payment) => {
      const loan = loans.find((item) => item.loan_id === payment.loan_id);
      const customer = loan && customers.get(loan.customer_id);
      const row = document.createElement("tr");
      row.dataset.status = payment.payment_status;
      row.dataset.search = `${payment.payment_id} ${payment.external_reference} ${payment.loan_id} ${customer || ""} ${payment.payment_method}`.toLowerCase();
      row.dataset.details = JSON.stringify([
        ["Payment ID", payment.payment_id],
        ["External reference", payment.external_reference],
        ["Loan", payment.loan_id],
        ["Customer", customer || "Unknown customer"],
        ["Received", AppUI.formatDate(payment.received_at, true)],
        ["Method", payment.payment_method.replaceAll("_", " ")],
        ["Amount", AppUI.formatMoney(payment.amount_minor, payment.currency_code)],
        ["Allocated", AppUI.formatMoney(payment.amount_allocated_minor, payment.currency_code)],
        ["Unallocated", AppUI.formatMoney(payment.amount_unallocated_minor, payment.currency_code)],
        ["Status", payment.payment_status]
      ]);
      AppUI.addPrimaryCell(row, payment.payment_id, payment.external_reference);
      AppUI.addPrimaryCell(row, customer || "Unknown customer", payment.loan_id);
      AppUI.addTextCell(row, AppUI.formatDate(payment.received_at, true));
      AppUI.addTextCell(row, payment.payment_method.replaceAll("_", " "));
      AppUI.addTextCell(row, AppUI.formatMoney(payment.amount_minor, payment.currency_code), "amount-cell");
      AppUI.addTextCell(row, AppUI.formatMoney(payment.amount_allocated_minor, payment.currency_code));
      AppUI.addBadgeCell(row, payment.payment_status);
      AppUI.addActionCell(row, "show-details", "View");
      body.append(row);
    });
    if (!payments.length) AppUI.showTableMessage(table, "No payments were returned by the API.");
    const metrics = document.querySelectorAll(".metric-grid .metric-value");
    const posted = payments.filter((payment) => payment.payment_status === "posted").length;
    const methods = new Set(payments.map((payment) => payment.payment_method)).size;
    const currencies = [...new Set(payments.map((payment) => payment.currency_code))].join(", ");
    [payments.length, posted, methods, currencies || "No records"].forEach((value, index) => {
      if (metrics[index]) metrics[index].textContent = String(value);
    });
    const count = document.querySelector("[data-visible-count]");
    if (count) count.textContent = `${payments.length} ${payments.length === 1 ? "record" : "records"}`;
    applyFilters();
  }

  async function loadPayments() {
    AppUI.setApiState("Loading payment history from the Flask API…");
    AppUI.showTableMessage(table, "Loading payment history…");
    document.querySelectorAll(".metric-grid .metric-value").forEach((metric) => {
      metric.textContent = "Loading";
    });
    try {
      const [paymentResponse, loanResponse, customerResponse] = await Promise.all([
        ApiClient.get("/payments"),
        ApiClient.get("/loans"),
        ApiClient.get("/customers")
      ]);
      payments = paymentResponse.data;
      loans = loanResponse.data;
      customers = new Map(customerResponse.data.map((customer) => [
        customer.customer_id,
        `${customer.first_name} ${customer.last_name}`
      ]));
      renderLoans();
      renderPayments();
      AppUI.clearApiState();
    } catch (error) {
      AppUI.setApiState(error.message, "error");
      AppUI.showTableMessage(table, "Payment history could not be loaded.");
      submitButton.disabled = true;
      document.querySelectorAll(".metric-grid .metric-value").forEach((metric) => {
        metric.textContent = "Unavailable";
      });
    }
  }

  document.querySelector('[data-action="add-payment"]')?.addEventListener("click", () => {
    form.reset();
    AppUI.hideMessage(message);
    dialog.showModal();
    loanSelect.focus();
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    AppUI.hideMessage(message);
    if (!form.reportValidity()) return;

    const values = Object.fromEntries(new FormData(form).entries());
    const amountMatch = /^(\d+)(?:\.(\d{1,2}))?$/.exec(values.amount.trim());
    if (!amountMatch) {
      AppUI.showMessage(message, "Enter an amount with no more than two decimal places.", "error");
      return;
    }
    const amountMinor = Number(amountMatch[1]) * 100 + Number((amountMatch[2] || "").padEnd(2, "0"));
    if (!Number.isSafeInteger(amountMinor) || amountMinor <= 0) {
      AppUI.showMessage(message, "Enter a valid positive payment amount.", "error");
      return;
    }
    const date = new Date(`${values.date}T00:00:00Z`);
    if (Number.isNaN(date.getTime())) {
      AppUI.showMessage(message, "Enter a valid received date.", "error");
      return;
    }
    const methodMap = {
      "Bank transfer": "bank_transfer",
      "Debit card": "debit_card",
      Cash: "cash",
      "Mobile wallet": "mobile_wallet",
      "Direct debit": "direct_debit"
    };
    const payment = {
      loan_id: values.loan_id,
      amount_minor: amountMinor,
      payment_method: methodMap[values.method],
      external_reference: values.reference.trim(),
      received_at: `${values.date}T00:00:00Z`
    };
    submitButton.disabled = true;
    try {
      await ApiClient.post("/payments", payment);
      await loadPayments();
      dialog.close();
      AppUI.showToast("Payment recorded by the API.");
    } catch (error) {
      AppUI.showMessage(message, error.message, "error");
    } finally {
      submitButton.disabled = false;
    }
  });

  search?.addEventListener("input", applyFilters);
  statusFilter?.addEventListener("change", applyFilters);
  table.setAttribute("aria-label", "Payment history from the Flask API");
  loadPayments();
})();
