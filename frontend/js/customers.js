(function () {
  "use strict";

  const table = document.querySelector("#customer-table");
  const dialog = document.querySelector("#customer-dialog");
  const form = document.querySelector("#customer-form");
  const message = document.querySelector("#customer-form-message");
  const title = document.querySelector("#customer-dialog-title");
  const search = document.querySelector('[data-filter-table="#customer-table"]');
  const statusFilter = document.querySelector("#customer-status-filter");
  if (!table || !dialog || !form) return;

  let customers = [];
  let loanCounts = new Map();

  function applyFilters() {
    AppUI.filterTable(table, search?.value, statusFilter?.value);
  }

  function renderRows() {
    const body = table.querySelector("tbody");
    body.replaceChildren();
    customers.forEach((customer) => {
      const fullName = `${customer.first_name} ${customer.last_name}`;
      const row = document.createElement("tr");
      row.dataset.status = customer.customer_status;
      row.dataset.search = `${fullName} ${customer.customer_id} ${customer.email} ${customer.phone || ""}`.toLowerCase();
      row.dataset.details = JSON.stringify([
        ["Customer ID", customer.customer_id],
        ["Name", fullName],
        ["Email", customer.email],
        ["Phone", customer.phone || "—"],
        ["Customer status", customer.customer_status],
        ["Loan count", loanCounts.get(customer.customer_id) || 0]
      ]);
      AppUI.addPrimaryCell(row, fullName, `Customer since ${AppUI.formatDate(customer.created_at)}`);
      AppUI.addTextCell(row, customer.customer_id);
      AppUI.addTextCell(row, customer.email);
      AppUI.addTextCell(row, customer.phone);
      AppUI.addTextCell(row, loanCounts.get(customer.customer_id) || 0);
      AppUI.addBadgeCell(row, customer.customer_status);
      AppUI.addActionCell(row, "show-details", "View");
      const editButton = AppUI.addActionCell(row, "edit-customer", "Edit");
      editButton.dataset.customerId = customer.customer_id;
      body.append(row);
    });
    if (!customers.length) AppUI.showTableMessage(table, "No customers were returned by the API.");
    applyFilters();
    const count = document.querySelector("[data-visible-count]");
    if (count) count.textContent = `${customers.length} ${customers.length === 1 ? "record" : "records"}`;
  }

  async function loadCustomers() {
    AppUI.setApiState("Loading customer records from the Flask API…");
    AppUI.showTableMessage(table, "Loading customer records…");
    try {
      const [customerResponse, loanResponse] = await Promise.all([
        ApiClient.get("/customers"),
        ApiClient.get("/loans")
      ]);
      customers = customerResponse.data;
      loanCounts = loanResponse.data.reduce((counts, loan) => {
        counts.set(loan.customer_id, (counts.get(loan.customer_id) || 0) + 1);
        return counts;
      }, new Map());
      renderRows();
      AppUI.clearApiState();
    } catch (error) {
      AppUI.setApiState(error.message, "error");
      AppUI.showTableMessage(table, "Customer records could not be loaded.");
    }
  }

  function setField(name, value) {
    const field = form.elements.namedItem(name);
    if (field) field.value = value || "";
  }

  function openForm(customer) {
    AppUI.hideMessage(message);
    form.reset();
    if (customer) {
      setField("customer_id", customer.customer_id);
      setField("first_name", customer.first_name);
      setField("last_name", customer.last_name);
      setField("email", customer.email);
      setField("phone", customer.phone);
      setField("customer_status", customer.customer_status);
      title.textContent = `Edit ${customer.customer_id}`;
    } else {
      setField("customer_status", "active");
      title.textContent = "Add customer";
    }
    dialog.showModal();
    form.elements.namedItem("first_name").focus();
  }

  document.addEventListener("click", (event) => {
    const trigger = event.target.closest("[data-action]");
    if (!trigger) return;
    if (trigger.dataset.action === "add-customer") openForm(null);
    if (trigger.dataset.action === "edit-customer") {
      const customer = customers.find((item) => item.customer_id === trigger.dataset.customerId);
      if (customer) openForm(customer);
    }
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    AppUI.hideMessage(message);
    if (!form.reportValidity()) return;

    const values = Object.fromEntries(new FormData(form).entries());
    const customer = {
      first_name: values.first_name.trim(),
      last_name: values.last_name.trim(),
      email: values.email.trim(),
      phone: values.phone.trim() || null,
      customer_status: values.customer_status
    };
    const existingId = values.customer_id;
    const submitButton = form.querySelector('[type="submit"]');
    submitButton.disabled = true;
    try {
      if (existingId) {
        await ApiClient.patch(`/customers/${encodeURIComponent(existingId)}`, customer);
      } else {
        await ApiClient.post("/customers", customer);
      }
      await loadCustomers();
      dialog.close();
      AppUI.showToast(existingId ? "Customer updated." : "Customer added.");
    } catch (error) {
      AppUI.showMessage(message, error.message, "error");
    } finally {
      submitButton.disabled = false;
    }
  });

  search?.addEventListener("input", applyFilters);
  statusFilter?.addEventListener("change", applyFilters);
  loadCustomers();
})();
