(function () {
  "use strict";

  const page = document.body.dataset.page;
  const caseTable = document.querySelector("#case-table");
  const contactTable = document.querySelector("#contact-table");
  const promiseTable = document.querySelector("#promise-table");

  function filterExtended(table, search, filters) {
    if (!table) return;
    const query = (search?.value || "").trim().toLowerCase();
    const rows = Array.from(table.querySelectorAll("tbody tr:not(.empty-row)"));
    let visible = 0;
    rows.forEach((row) => {
      const textMatches = !query || (row.dataset.search || row.textContent).toLowerCase().includes(query);
      const matches = filters.every(({ element, key }) => !element?.value || row.dataset[key] === element.value);
      row.hidden = !(textMatches && matches);
      if (!row.hidden) visible += 1;
    });
    AppUI.syncEmptyState(table, visible);
    const count = document.querySelector("[data-visible-count]");
    if (count) count.textContent = `${visible} ${visible === 1 ? "record" : "records"}`;
  }

  function renderCases(cases, customers) {
    const body = caseTable.querySelector("tbody");
    body.replaceChildren();
    cases.forEach((item) => {
      const customer = customers.get(item.customer_id) || "Unknown customer";
      const row = document.createElement("tr");
      row.dataset.status = item.case_status;
      row.dataset.priority = item.priority;
      row.dataset.search = `${item.case_id} ${item.customer_id} ${customer} ${item.loan_id} ${item.priority}`.toLowerCase();
      row.dataset.details = JSON.stringify([
        ["Case ID", item.case_id],
        ["Customer", `${customer} · ${item.customer_id}`],
        ["Loan", item.loan_id],
        ["Opened", AppUI.formatDate(item.opened_at, true)],
        ["Priority", item.priority],
        ["Status", item.case_status],
        ["Source", item.case_source],
        ["Days past due", item.days_past_due],
        ["Arrears", AppUI.formatMoney(item.arrears_amount_minor, item.currency_code)],
        ["Dispute", item.account_status?.dispute_status || "clear"],
        ["Hardship", item.account_status?.hardship_status || "none"],
        ["Debt status", item.account_status?.debt_status || "unverified"]
      ]);
      AppUI.addPrimaryCell(row, item.case_id, `Opened ${AppUI.formatDate(item.opened_at)}`);
      AppUI.addPrimaryCell(row, customer, item.customer_id);
      AppUI.addTextCell(row, item.loan_id);
      AppUI.addTextCell(row, `${item.days_past_due} days`);
      AppUI.addTextCell(row, AppUI.formatMoney(item.arrears_amount_minor, item.currency_code), "amount-cell");
      AppUI.addBadgeCell(row, item.priority);
      AppUI.addBadgeCell(row, item.case_status);
      const statusCell = document.createElement("td");
      statusCell.className = "account-status-controls";
      [
        ["dispute_status", "Dispute", [["clear", "Clear"], ["disputed", "Disputed"], ["resolved", "Resolved"]]],
        ["hardship_status", "Hardship", [["none", "None"], ["active", "Active"], ["resolved", "Resolved"]]],
        ["debt_status", "Debt", [["unverified", "Unverified"], ["confirmed", "Confirmed"]]]
      ].forEach(([field, label, options]) => {
        const select = document.createElement("select");
        select.className = "account-status-select";
        select.dataset.loanId = item.loan_id;
        select.dataset.field = field;
        select.dataset.currentValue = item.account_status?.[field] || options[0][0];
        select.setAttribute("aria-label", `${label} status for ${item.loan_id}`);
        options.forEach(([value, text]) => select.add(new Option(text, value, false, value === select.dataset.currentValue)));
        statusCell.append(select);
      });
      row.append(statusCell);
      const control = document.createElement("td");
      const select = document.createElement("select");
      select.className = "status-select";
      select.setAttribute("aria-label", `Update status for ${item.case_id}`);
      [
        ["open", "Open"],
        ["in_progress", "In progress"],
        ["resolved", "Resolved"],
        ["closed", "Closed"]
      ].forEach(([value, label]) => {
        const option = new Option(label, value, false, value === item.case_status);
        select.add(option);
      });
      select.dataset.caseId = item.case_id;
      select.dataset.currentStatus = item.case_status;
      control.append(select);
      row.append(control);
      body.append(row);
    });
    if (!cases.length) AppUI.showTableMessage(caseTable, "No collection cases were returned by the API.");
    const active = cases.filter((item) => ["open", "in_progress"].includes(item.case_status));
    const metricValues = document.querySelectorAll(".metric-grid .metric-value");
    [
      active.length,
      active.filter((item) => item.priority === "high").length,
      active.filter((item) => item.case_status === "in_progress").length,
      cases.filter((item) => item.case_status === "resolved").length
    ].forEach((value, index) => {
      if (metricValues[index]) metricValues[index].textContent = String(value);
    });
    filterExtended(caseTable, document.querySelector('[data-filter-table="#case-table"]'), [
      { element: document.querySelector("#case-status-filter"), key: "status" },
      { element: document.querySelector("#case-priority-filter"), key: "priority" }
    ]);
  }

  function renderContacts(cases, customers) {
    const body = contactTable.querySelector("tbody");
    body.replaceChildren();
    const records = cases.flatMap((item) => item.contact_attempts.map((attempt) => ({
      ...attempt,
      case_id: item.case_id,
      customer_id: item.customer_id
    }))).sort((a, b) => String(b.attempted_at).localeCompare(String(a.attempted_at)));
    records.forEach((attempt) => {
      const customer = customers.get(attempt.customer_id) || "Unknown customer";
      const row = document.createElement("tr");
      row.dataset.status = attempt.outcome;
      row.dataset.channel = attempt.channel;
      row.dataset.search = `${customer} ${attempt.customer_id} ${attempt.case_id} ${attempt.channel} ${attempt.outcome} ${attempt.notes || ""}`.toLowerCase();
      AppUI.addPrimaryCell(row, AppUI.formatDate(attempt.attempted_at, true), attempt.attempted_at);
      AppUI.addPrimaryCell(row, customer, attempt.customer_id);
      AppUI.addTextCell(row, attempt.case_id);
      AppUI.addBadgeCell(row, attempt.channel);
      AppUI.addBadgeCell(row, attempt.outcome);
      AppUI.addTextCell(row, attempt.notes);
      body.append(row);
    });
    if (!records.length) AppUI.showTableMessage(contactTable, "No contact attempts are available in the returned collection cases.");
    const count = document.querySelector("[data-visible-count]");
    if (count) count.textContent = `${records.length} ${records.length === 1 ? "record" : "records"}`;
    const stats = document.querySelectorAll(".detail-item strong");
    if (stats[0]) stats[0].textContent = String(records.length);
    if (stats[1]) stats[1].textContent = [...new Set(records.map((item) => item.channel))].join(" · ") || "None";
    if (stats[2]) stats[2].textContent = String(records.filter((item) => item.outcome === "connected").length);
    filterExtended(contactTable, document.querySelector('[data-filter-table="#contact-table"]'), [
      { element: document.querySelector("#contact-outcome"), key: "status" },
      { element: document.querySelector("#contact-channel"), key: "channel" }
    ]);
  }

  function populateOptions(select, records, valueOf, labelOf, placeholder) {
    if (!select) return;
    select.replaceChildren(new Option(placeholder, ""));
    records.forEach((record) => select.add(new Option(labelOf(record), valueOf(record))));
  }

  function renderPromises(records, customers) {
    const body = promiseTable.querySelector("tbody");
    body.replaceChildren();
    records.forEach((promise) => {
      const customer = customers.get(promise.customer_id) || "Unknown customer";
      const row = document.createElement("tr");
      row.dataset.status = promise.promise_status;
      row.dataset.search = `${promise.promise_id} ${customer} ${promise.case_id} ${promise.loan_id}`.toLowerCase();
      AppUI.addPrimaryCell(row, promise.promise_id, promise.case_id);
      AppUI.addPrimaryCell(row, customer, promise.loan_id);
      AppUI.addTextCell(row, AppUI.formatDate(promise.due_date));
      AppUI.addTextCell(row, AppUI.formatMoney(promise.amount_minor, promise.currency_code), "amount-cell");
      AppUI.addTextCell(row, AppUI.formatDate(promise.promised_at, true));
      AppUI.addBadgeCell(row, promise.promise_status);
      AppUI.addTextCell(row, AppUI.formatDate(promise.resolved_at, true));
      const actionCell = document.createElement("td");
      if (promise.promise_status === "pending") {
        const select = document.createElement("select");
        select.className = "promise-status-select";
        select.dataset.promiseId = promise.promise_id;
        select.dataset.currentStatus = promise.promise_status;
        select.setAttribute("aria-label", `Update ${promise.promise_id}`);
        select.add(new Option("Update status…", ""));
        [["kept", "Kept"], ["broken", "Broken"], ["cancelled", "Cancelled"]]
          .forEach(([value, label]) => select.add(new Option(label, value)));
        actionCell.append(select);
      } else {
        actionCell.textContent = "Resolved";
      }
      row.append(actionCell);
      body.append(row);
    });
    if (!records.length) AppUI.showTableMessage(promiseTable, "No promise records are available.");
    const counts = ["pending", "kept", "broken"].map((status) =>
      records.filter((item) => item.promise_status === status).length
    );
    const metrics = document.querySelectorAll(".metric-grid .metric-value");
    const currencies = [...new Set(records.map((item) => item.currency_code))].join(", ");
    [...counts, currencies || "No records"].forEach((value, index) => {
      if (metrics[index]) metrics[index].textContent = String(value);
    });
    const count = document.querySelector("[data-visible-count]");
    if (count) count.textContent = `${records.length} ${records.length === 1 ? "record" : "records"}`;
    filterExtended(promiseTable, document.querySelector('[data-filter-table="#promise-table"]'), [
      { element: document.querySelector("#promise-status"), key: "status" }
    ]);
  }

  function setReportStat(cardIndex, statIndex, value) {
    const card = document.querySelectorAll(".reports-grid > .panel")[cardIndex];
    const stat = card?.querySelectorAll(".report-stat")[statIndex]?.querySelector("strong");
    if (stat) stat.textContent = value;
  }

  function formatCurrencyAmounts(records, amountField, currencyField) {
    return records.map((record) => AppUI.formatMoney(
      record[amountField],
      record[currencyField]
    )).join(" · ") || "No records";
  }

  function renderAnomalies(report) {
    const table = document.querySelector("#anomaly-table");
    if (!table) return;
    const body = table.querySelector("tbody");
    body.replaceChildren();
    (report.records || []).forEach((item) => {
      const row = document.createElement("tr");
      AppUI.addTextCell(row, item.anomaly_type.replaceAll("_", " "));
      AppUI.addTextCell(row, item.record_reference);
      AppUI.addTextCell(row, item.reason);
      AppUI.addBadgeCell(row, item.detection_status);
      AppUI.addTextCell(row, AppUI.formatDate(item.last_detected_at, true));
      body.append(row);
    });
    if (!(report.records || []).length) AppUI.showTableMessage(table, "No anomalies were detected.");
    const summary = document.querySelector("[data-anomaly-summary]");
    if (summary) summary.textContent = `${report.active_count} active finding(s) as of ${report.as_of}. Ground-truth labels used: ${report.ground_truth_used ? "yes" : "no"}.`;
  }

  function renderReports(customers, loans, payments, cases, delinquency, anomalies) {
    const activeLoans = loans.filter((loan) => loan.loan_status === "active").length;
    const postedPayments = payments.filter((payment) => payment.payment_status === "posted").length;
    const high = cases.filter((item) => item.priority === "high").length;
    const medium = cases.filter((item) => item.priority === "medium").length;
    const low = cases.filter((item) => item.priority === "low").length;

    const categories = new Map(delinquency.categories.map((item) => [item.bucket, item]));
    const overdueCard = document.querySelectorAll(".reports-grid > .panel")[0];
    overdueCard?.querySelector(".badge")?.replaceChildren(document.createTextNode(`${delinquency.overdue_loan_count} overdue loans`));
    setReportStat(0, 0, formatCurrencyAmounts(delinquency.total_arrears_by_currency, "amount_minor", "currency_code"));
    ["1-30", "31-60", "61-90", "91+"].forEach((bucket, index) => {
      const category = categories.get(bucket);
      setReportStat(0, index + 1, `${category.loan_count} loans · ${formatCurrencyAmounts(category.arrears_by_currency, "amount_minor", "currency_code")}`);
    });
    const overdueNote = overdueCard?.querySelector(".report-note");
    if (overdueNote) overdueNote.textContent = `Calculated from installment schedules and posted allocations as of ${delinquency.as_of}.`;
    const paymentCard = document.querySelectorAll(".reports-grid > .panel")[1];
    paymentCard?.querySelector(".badge")?.replaceChildren(document.createTextNode("API records"));
    setReportStat(1, 0, String(payments.length));
    setReportStat(1, 1, String(postedPayments));
    setReportStat(1, 2, String(new Set(payments.map((item) => item.payment_method)).size));
    setReportStat(1, 3, [...new Set(payments.map((item) => item.currency_code))].join(", ") || "No records");

    const caseCard = document.querySelectorAll(".reports-grid > .panel")[2];
    caseCard?.querySelector(".badge")?.replaceChildren(document.createTextNode(`${cases.length} cases`));
    setReportStat(2, 0, String(high));
    setReportStat(2, 1, String(medium));
    setReportStat(2, 2, String(low));
    setReportStat(2, 3, String(cases.length));

    setReportStat(3, 0, delinquency.as_of);
    setReportStat(3, 1, "Local Flask API");
    setReportStat(3, 2, "Connected");
    setReportStat(3, 3, "Schedule + posted allocations");
    const contextNote = document.querySelectorAll(".reports-grid > .panel")[3]?.querySelector(".report-note");
    if (contextNote) contextNote.textContent = `API returned ${customers.length} customers, ${loans.length} loans (${activeLoans} active), ${payments.length} payments, and ${cases.length} collection cases.`;
    const countLabel = document.querySelector(".filter-bar .table-count");
    if (countLabel) countLabel.textContent = "Current API records";
    renderAnomalies(anomalies);
  }

  function renderContactAudit(events) {
    const table = document.querySelector("#contact-audit-table");
    if (!table) return;
    const body = table.querySelector("tbody");
    body.replaceChildren();
    const attempts = events.filter((item) => item.action === "contact_attempt");
    attempts.forEach((item) => {
      const row = document.createElement("tr");
      AppUI.addTextCell(row, AppUI.formatDate(item.event_at, true));
      AppUI.addTextCell(row, item.entity_id);
      AppUI.addBadgeCell(row, item.outcome);
      AppUI.addTextCell(row, item.action);
      AppUI.addTextCell(row, item.reason);
      body.append(row);
    });
    if (!attempts.length) AppUI.showTableMessage(table, "No contact attempts have been audited.");
    return attempts.length;
  }

  function showFormMessage(element, message, type) {
    if (!element) return;
    element.textContent = message;
    element.className = `message is-visible message-${type}`;
  }

  async function loadContactPreference(customerId) {
    const form = document.querySelector("#contact-preference-form");
    if (!form || !customerId) return;
    try {
      const response = await ApiClient.get(`/customers/${encodeURIComponent(customerId)}/contact-preference`);
      const preference = response.data;
      ["timezone", "allowed_contact_start", "allowed_contact_end", "preferred_channel",
        "consent_status", "contact_window"].forEach((field) => {
        form.elements.namedItem(field).value = preference?.[field] || (
          field === "preferred_channel" ? "phone" : field === "consent_status" ? "granted" : field === "contact_window" ? "any" : ""
        );
      });
      form.elements.namedItem("allowed_channels").value = preference?.allowed_channels?.join(", ") || "";
      form.elements.namedItem("weekend_contact_allowed").checked = Boolean(preference?.weekend_contact_allowed);
      form.elements.namedItem("holiday_contact_allowed").checked = Boolean(preference?.holiday_contact_allowed);
      showFormMessage(
        document.querySelector("#contact-preference-message"),
        preference ? "Existing settings loaded; saving updates this customer's configuration." : "No settings are configured. Complete timezone and hours before any contact attempt.",
        "info"
      );
    } catch (error) {
      showFormMessage(document.querySelector("#contact-preference-message"), error.message, "error");
    }
  }

  async function loadPageData() {
    const isCases = page === "collections";
    const isContacts = page === "contact_history";
    const isPromises = page === "promises";
    const isReports = page === "reports";
    const table = isCases ? caseTable : isContacts ? contactTable : isPromises ? promiseTable : null;
    AppUI.setApiState("Loading collection data from the Flask API…");
    if (table) AppUI.showTableMessage(table, "Loading records…");
    if (table) {
      document.querySelectorAll(".metric-grid .metric-value").forEach((metric) => {
        metric.textContent = "Loading";
      });
    }
    if (isContacts) {
      document.querySelectorAll(".detail-item strong").forEach((value) => {
        value.textContent = "Loading";
      });
    }
    if (isReports) {
      document.querySelectorAll(".reports-grid .report-stat strong").forEach((value) => {
        value.textContent = "Loading";
      });
    }
    try {
      const caseResponse = await ApiClient.get("/collection-cases");
      const customerResponse = isCases || isContacts || isPromises
        ? await ApiClient.get("/customers")
        : { data: [] };
      const customers = new Map(customerResponse.data.map((customer) => [
        customer.customer_id,
        `${customer.first_name} ${customer.last_name}`
      ]));
      if (isCases) renderCases(caseResponse.data, customers);
      if (isCases) {
        const [loansResponse, delinquencyResponse] = await Promise.all([
          ApiClient.get("/loans"),
          ApiClient.get("/delinquency")
        ]);
        const balances = new Map(delinquencyResponse.data.map((item) => [item.loan_id, item]));
        populateOptions(
          document.querySelector("#case-loan"),
          loansResponse.data.filter((loan) => (balances.get(loan.loan_id)?.arrears_amount_minor || 0) > 0),
          (loan) => loan.loan_id,
          (loan) => {
            const balance = balances.get(loan.loan_id);
            return `${loan.loan_id} · ${customers.get(loan.customer_id) || loan.customer_id} · ${AppUI.formatMoney(balance.arrears_amount_minor, balance.currency_code)}`;
          },
          "Choose an overdue loan"
        );
      }
      if (isContacts) {
        const [auditResponse] = await Promise.all([
          ApiClient.get("/audit-events?entity_type=collection_case")
        ]);
        renderContacts(caseResponse.data, customers);
        const auditedCount = renderContactAudit(auditResponse.data);
        const stats = document.querySelectorAll(".detail-item strong");
        if (stats[3]) stats[3].textContent = String(auditedCount);
        populateOptions(
          document.querySelector("#contact-customer"),
          customerResponse.data,
          (customer) => customer.customer_id,
          (customer) => `${customer.first_name} ${customer.last_name} · ${customer.customer_id}`,
          "Choose customer"
        );
        populateOptions(
          document.querySelector("#contact-case"),
          caseResponse.data.filter((item) => ["open", "in_progress"].includes(item.case_status)),
          (item) => item.case_id,
          (item) => `${item.case_id} · ${customers.get(item.customer_id) || item.customer_id}`,
          "Choose active case"
        );
      }
      if (isPromises) {
        const promiseResponse = await ApiClient.get("/promises");
        renderPromises(promiseResponse.data, customers);
        populateOptions(
          document.querySelector("#promise-case"),
          caseResponse.data.filter((item) => ["open", "in_progress"].includes(item.case_status)),
          (item) => item.case_id,
          (item) => `${item.case_id} · ${customers.get(item.customer_id) || item.customer_id}`,
          "Choose active case"
        );
      }
      if (isReports) {
        const [loans, payments, customersResult, delinquency, anomalyReport] = await Promise.all([
          ApiClient.get("/loans"),
          ApiClient.get("/payments"),
          ApiClient.get("/customers"),
          ApiClient.get("/reports/delinquency"),
          ApiClient.get("/reports/anomalies")
        ]);
        renderReports(customersResult.data, loans.data, payments.data, caseResponse.data, delinquency.data, anomalyReport.data);
      }
      AppUI.clearApiState();
    } catch (error) {
      AppUI.setApiState(error.message, "error");
      if (table) AppUI.showTableMessage(table, "Records could not be loaded from the API.");
      document.querySelectorAll(".metric-grid .metric-value").forEach((metric) => {
        metric.textContent = "Unavailable";
      });
      if (isContacts) {
        document.querySelectorAll(".detail-item strong").forEach((value) => {
          value.textContent = "Unavailable";
        });
        const summary = document.querySelector("[data-anomaly-summary]");
        if (summary) summary.textContent = "Contact history or audit records could not be loaded.";
      }
      if (page === "reports") {
        document.querySelectorAll(".reports-grid .report-stat strong").forEach((value) => {
          value.textContent = "Unavailable";
        });
        const note = document.querySelector(".reports-grid .report-note");
        if (note) note.textContent = "The API could not be reached. Report values are unavailable.";
        const summary = document.querySelector("[data-anomaly-summary]");
        if (summary) summary.textContent = "Anomaly report is unavailable because the API request failed.";
      }
    }
  }

  if (caseTable) {
    const search = document.querySelector('[data-filter-table="#case-table"]');
    const filters = [
      { element: document.querySelector("#case-status-filter"), key: "status" },
      { element: document.querySelector("#case-priority-filter"), key: "priority" }
    ];
    [search, ...filters.map((filter) => filter.element)].forEach((control) =>
      control?.addEventListener("input", () => filterExtended(caseTable, search, filters))
    );
    filters.forEach(({ element }) => element?.addEventListener("change", () => filterExtended(caseTable, search, filters)));
    caseTable.addEventListener("change", async (event) => {
      const accountSelect = event.target.closest(".account-status-select");
      if (accountSelect) {
        const previous = accountSelect.dataset.currentValue;
        accountSelect.disabled = true;
        try {
          await ApiClient.put(`/loans/${encodeURIComponent(accountSelect.dataset.loanId)}/account-status`, {
            [accountSelect.dataset.field]: accountSelect.value
          });
          AppUI.showToast("Account status updated and audited.");
          await loadPageData();
        } catch (error) {
          accountSelect.value = previous;
          AppUI.showToast(error.message, "error");
        } finally {
          accountSelect.disabled = false;
        }
        return;
      }
      const select = event.target.closest(".status-select");
      if (!select) return;
      const previous = select.dataset.currentStatus || select.value;
      select.disabled = true;
      try {
        const response = await ApiClient.patch(`/collection-cases/${encodeURIComponent(select.dataset.caseId)}`, {
          case_status: select.value
        });
        select.dataset.currentStatus = response.data.case_status;
        AppUI.showToast("Collection case status updated.");
        await loadPageData();
      } catch (error) {
        select.value = previous;
        AppUI.showToast(error.message, "error");
      } finally {
        select.disabled = false;
      }
    });
  }

  document.querySelector("#collection-case-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    const button = form.querySelector('button[type="submit"]');
    button.disabled = true;
    try {
      await ApiClient.post("/collection-cases", {
        loan_id: data.get("loan_id"),
        case_source: data.get("case_source")
      });
      showFormMessage(document.querySelector("#collection-case-message"), "Collection case created or existing active case returned.", "success");
      await loadPageData();
    } catch (error) {
      showFormMessage(document.querySelector("#collection-case-message"), error.message, "error");
    } finally {
      button.disabled = false;
    }
  });

  const contactSearch = document.querySelector('[data-filter-table="#contact-table"]');
  const contactFilters = [
    { element: document.querySelector("#contact-outcome"), key: "status" },
    { element: document.querySelector("#contact-channel"), key: "channel" }
  ];
  [contactSearch, ...contactFilters.map((filter) => filter.element)].forEach((control) =>
    control?.addEventListener("input", () => filterExtended(contactTable, contactSearch, contactFilters))
  );
  contactFilters.forEach(({ element }) => element?.addEventListener("change", () =>
    filterExtended(contactTable, contactSearch, contactFilters)
  ));

  const promiseSearch = document.querySelector('[data-filter-table="#promise-table"]');
  const promiseStatus = document.querySelector("#promise-status");
  promiseSearch?.addEventListener("input", () => filterExtended(promiseTable, promiseSearch, [
    { element: promiseStatus, key: "status" }
  ]));
  promiseStatus?.addEventListener("change", () => filterExtended(promiseTable, promiseSearch, [
    { element: promiseStatus, key: "status" }
  ]));

  document.querySelector("#contact-customer")?.addEventListener("change", (event) => {
    loadContactPreference(event.target.value);
  });

  document.querySelector("#contact-preference-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    const channelsText = String(data.get("allowed_channels") || "").trim();
    const payload = {
      timezone: String(data.get("timezone")).trim(),
      allowed_contact_start: data.get("allowed_contact_start"),
      allowed_contact_end: data.get("allowed_contact_end"),
      preferred_channel: data.get("preferred_channel"),
      consent_status: data.get("consent_status"),
      contact_window: data.get("contact_window"),
      weekend_contact_allowed: data.has("weekend_contact_allowed"),
      holiday_contact_allowed: data.has("holiday_contact_allowed"),
      allowed_channels: channelsText ? channelsText.split(",").map((item) => item.trim()).filter(Boolean) : null
    };
    const customerId = data.get("customer_id");
    const button = form.querySelector('button[type="submit"]');
    button.disabled = true;
    try {
      await ApiClient.put(`/customers/${encodeURIComponent(customerId)}/contact-preference`, payload);
      showFormMessage(document.querySelector("#contact-preference-message"), "Contact settings saved. Timezone and allowed hours are now explicitly configured.", "success");
    } catch (error) {
      showFormMessage(document.querySelector("#contact-preference-message"), error.message, "error");
    } finally {
      button.disabled = false;
    }
  });

  document.querySelector("#contact-attempt-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    const localInput = String(data.get("attempted_at") || "");
    const payload = {
      attempted_at: `${localInput}:00Z`,
      channel: data.get("channel"),
      outcome: data.get("outcome"),
      notes: String(data.get("notes") || "").trim() || null
    };
    const button = form.querySelector('button[type="submit"]');
    button.disabled = true;
    try {
      await ApiClient.post(`/collection-cases/${encodeURIComponent(data.get("case_id"))}/contact-attempts`, payload);
      showFormMessage(document.querySelector("#contact-attempt-message"), "Contact attempt was permitted and recorded.", "success");
      form.reset();
    } catch (error) {
      showFormMessage(document.querySelector("#contact-attempt-message"), error.message, "error");
    } finally {
      button.disabled = false;
      await loadPageData();
    }
  });

  document.querySelector("#contact-holiday-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    const holidayDate = data.get("holiday_date");
    const button = form.querySelector('button[type="submit"]');
    button.disabled = true;
    try {
      await ApiClient.post(`/contact-holidays/${encodeURIComponent(holidayDate)}`, {
        label: String(data.get("label")).trim()
      });
      showFormMessage(document.querySelector("#contact-holiday-message"), "Test holiday configured and audit event recorded.", "success");
      form.reset();
    } catch (error) {
      showFormMessage(document.querySelector("#contact-holiday-message"), error.message, "error");
    } finally {
      button.disabled = false;
    }
  });

  document.querySelector("#promise-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    const amount = Number(data.get("amount_minor"));
    const payload = {
      promised_at: new Date().toISOString().replace(/\.\d{3}Z$/, "Z"),
      due_date: data.get("due_date"),
      amount_minor: amount
    };
    const button = form.querySelector('button[type="submit"]');
    button.disabled = true;
    try {
      await ApiClient.post(`/collection-cases/${encodeURIComponent(data.get("case_id"))}/promises`, payload);
      showFormMessage(document.querySelector("#promise-form-message"), "Promise recorded and validated against current arrears.", "success");
      form.reset();
      await loadPageData();
    } catch (error) {
      showFormMessage(document.querySelector("#promise-form-message"), error.message, "error");
    } finally {
      button.disabled = false;
    }
  });

  promiseTable?.addEventListener("change", async (event) => {
    const select = event.target.closest(".promise-status-select");
    if (!select || !select.value) return;
    const requestedStatus = select.value;
    select.disabled = true;
    try {
      await ApiClient.patch(`/promises/${encodeURIComponent(select.dataset.promiseId)}`, {
        promise_status: requestedStatus
      });
      AppUI.showToast("Promise status updated.");
      await loadPageData();
    } catch (error) {
      select.value = "";
      AppUI.showToast(error.message, "error");
    } finally {
      select.disabled = false;
    }
  });

  document.querySelector('[data-action="evaluate-promises"]')?.addEventListener("click", async () => {
    try {
      const response = await ApiClient.post("/promises/evaluate", {});
      AppUI.showToast(`${response.data.evaluated.length} overdue promise(s) evaluated.`);
      await loadPageData();
    } catch (error) {
      AppUI.showToast(error.message, "error");
    }
  });

  document.querySelector('[data-action="detect-anomalies"]')?.addEventListener("click", async (event) => {
    const button = event.currentTarget;
    button.disabled = true;
    try {
      await ApiClient.post("/anomalies/detect", {});
      const report = await ApiClient.get("/reports/anomalies");
      renderAnomalies(report.data);
      AppUI.showToast("Anomaly detection completed.");
    } catch (error) {
      AppUI.showToast(error.message, "error");
    } finally {
      button.disabled = false;
    }
  });

  const reportType = document.querySelector("#report-type");
  reportType?.addEventListener("change", () => {
    const cards = Array.from(document.querySelectorAll(".reports-grid > .panel"));
    cards.forEach((card, index) => {
      const type = ["overdue", "payments", "collections", "portfolio"][index];
      card.hidden = reportType.value !== "portfolio" && type !== reportType.value;
    });
  });

  loadPageData();
})();
