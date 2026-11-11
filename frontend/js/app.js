(function () {
  "use strict";

  const pageTitles = {
    dashboard: "Portfolio dashboard",
    customers: "Customer management",
    loans: "Loan management",
    installments: "Installment management",
    payments: "Payment management",
    collections: "Collection management",
    contact_history: "Contact history",
    promises: "Promise-to-pay",
    reports: "Reports"
  };
  const navigation = [
    { key: "dashboard", label: "Dashboard", icon: "▦", href: "index.html" },
    { section: "PORTFOLIO" },
    { key: "customers", label: "Customers", icon: "♙", href: "pages/customers.html" },
    { key: "loans", label: "Loans", icon: "▤", href: "pages/loans.html" },
    { key: "installments", label: "Installments", icon: "▣", href: "pages/installments.html" },
    { key: "payments", label: "Payments", icon: "⇄", href: "pages/payments.html" },
    { section: "COLLECTIONS" },
    { key: "collections", label: "Case management", icon: "◉", href: "pages/collections.html" },
    { key: "contact_history", label: "Contact history", icon: "◷", href: "pages/contact_history.html" },
    { key: "promises", label: "Promises to pay", icon: "◇", href: "pages/promises.html" },
    { section: "INSIGHTS" },
    { key: "reports", label: "Reports", icon: "▥", href: "pages/reports.html" }
  ];

  const page = document.body.dataset.page || "dashboard";
  const root = document.body.dataset.root || "";
  const sidebar = document.getElementById("app-sidebar");
  const topbar = document.getElementById("app-topbar");

  if (sidebar) {
    sidebar.innerHTML = `
      <a class="brand" href="${root}index.html" aria-label="Meridian Collections home">
        <span class="brand-mark" aria-hidden="true">M</span>
        <span><span class="brand-title">Meridian</span><span class="brand-caption">Collections</span></span>
      </a>
      <span class="nav-caption">Workspace</span>
      <nav class="nav-list" aria-label="Workspace pages">
        ${navigation.map((item) => item.section
          ? `<span class="nav-caption">${item.section}</span>`
          : `<a class="nav-link" href="${root}${item.href}" ${item.key === page ? 'aria-current="page"' : ""}>
              <span class="nav-icon" aria-hidden="true">${item.icon}</span><span>${item.label}</span>
            </a>`).join("")}
      </nav>
      <div class="sidebar-bottom">
        <div class="demo-note"><strong><span class="live-dot"></span> LOCAL API MODE</strong>
          <p>Customers, schedules, calculated delinquency, and casework load from the local Flask API.</p>
        </div>
      </div>`;
  }

  if (topbar) {
    topbar.innerHTML = `
      <div class="topbar-left">
        <button class="menu-toggle" type="button" aria-label="Open navigation" aria-expanded="false" aria-controls="app-sidebar">☰</button>
        <div class="breadcrumb">Workspace <span aria-hidden="true">/</span> <b>${pageTitles[page] || "Workspace"}</b></div>
      </div>
      <div class="topbar-actions">
        <span class="demo-label">LOCAL API</span>
        <div class="topbar-user"><span class="avatar" aria-hidden="true">AM</span><span class="user-meta"><span class="user-name">Alex Morgan</span><span class="user-role">Collections manager</span></span></div>
      </div>`;
  }

  const sidebarToggle = document.querySelector(".menu-toggle");
  const scrim = document.querySelector(".sidebar-scrim");
  const closeSidebar = () => {
    sidebar?.classList.remove("is-open");
    scrim?.classList.remove("is-open");
    sidebarToggle?.setAttribute("aria-expanded", "false");
    document.body.classList.remove("sidebar-open");
  };
  sidebarToggle?.addEventListener("click", () => {
    const open = !sidebar.classList.contains("is-open");
    sidebar.classList.toggle("is-open", open);
    scrim?.classList.toggle("is-open", open);
    sidebarToggle.setAttribute("aria-expanded", String(open));
    document.body.classList.toggle("sidebar-open", open);
  });
  scrim?.addEventListener("click", closeSidebar);
  sidebar?.querySelectorAll(".nav-link").forEach((link) => link.addEventListener("click", closeSidebar));

  function apiStatusElement() {
    let status = document.querySelector("[data-api-status]");
    if (!status) {
      status = document.createElement("div");
      status.className = "message message-info is-visible";
      status.dataset.apiStatus = "";
      status.setAttribute("role", "status");
      document.querySelector(".page-heading")?.after(status);
    }
    return status;
  }

  function setApiState(message, type) {
    const status = apiStatusElement();
    status.textContent = message;
    status.className = `message is-visible message-${type || "info"}`;
    status.setAttribute("role", type === "error" ? "alert" : "status");
  }

  function clearApiState() {
    const status = document.querySelector("[data-api-status]");
    if (status) {
      status.textContent = "";
      status.className = "message";
    }
  }

  function showToast(message, type) {
    const region = document.querySelector(".toast-region");
    if (!region) return;
    const toast = document.createElement("div");
    toast.className = `toast${type === "error" ? " toast-error" : ""}`;
    toast.setAttribute("role", type === "error" ? "alert" : "status");
    toast.textContent = message;
    region.append(toast);
    window.setTimeout(() => toast.remove(), 3500);
  }

  function showMessage(element, message, type) {
    if (!element) return;
    element.textContent = message;
    element.className = `message is-visible message-${type || "success"}`;
  }

  function hideMessage(element) {
    if (!element) return;
    element.textContent = "";
    element.className = "message";
  }

  function filterTable(table, searchValue, statusValue) {
    if (!table) return;
    const query = (searchValue || "").trim().toLowerCase();
    const status = (statusValue || "").toLowerCase();
    const rows = Array.from(table.querySelectorAll("tbody tr:not(.empty-row)"));
    let visibleCount = 0;
    rows.forEach((row) => {
      const textMatches = !query || (row.dataset.search || row.textContent).toLowerCase().includes(query);
      const rowStatus = (row.dataset.status || "").toLowerCase();
      const statusMatches = !status || rowStatus === status;
      const visible = textMatches && statusMatches;
      row.hidden = !visible;
      if (visible) visibleCount += 1;
    });
    syncEmptyState(table, visibleCount);
    const countTarget = document.querySelector("[data-visible-count]");
    if (countTarget) countTarget.textContent = `${visibleCount} ${visibleCount === 1 ? "record" : "records"}`;
  }

  function syncEmptyState(table, visibleCount) {
    if (!table) return;
    const body = table.querySelector("tbody");
    const rows = body ? Array.from(body.querySelectorAll("tr:not(.empty-row)")) : [];
    let emptyRow = body?.querySelector(".empty-row");
    if (body && rows.length && visibleCount === 0) {
      if (!emptyRow) {
        emptyRow = document.createElement("tr");
        emptyRow.className = "empty-row";
        const cell = document.createElement("td");
        cell.colSpan = table.querySelectorAll("thead th").length || 1;
        cell.textContent = "No matching records. Try changing your search or filters.";
        emptyRow.append(cell);
        body.append(emptyRow);
      }
      emptyRow.hidden = false;
    } else if (emptyRow) {
      emptyRow.hidden = true;
    }
  }

  function showTableMessage(table, message) {
    if (!table) return;
    const body = table.querySelector("tbody");
    if (!body) return;
    body.replaceChildren();
    const row = document.createElement("tr");
    row.className = "empty-row";
    const cell = document.createElement("td");
    cell.colSpan = table.querySelectorAll("thead th").length || 1;
    cell.textContent = message;
    row.append(cell);
    body.append(row);
  }

  function formatMoney(minor, currency) {
    if (!Number.isSafeInteger(minor)) return "—";
    return new Intl.NumberFormat("en-IN", {
      style: "currency",
      currency: currency || "INR",
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    }).format(minor / 100);
  }

  function formatDate(value, includeTime) {
    if (!value) return "—";
    const parsed = new Date(value.length === 10 ? `${value}T00:00:00` : value);
    if (Number.isNaN(parsed.getTime())) return value;
    return new Intl.DateTimeFormat("en-GB", {
      day: "2-digit",
      month: "short",
      year: "numeric",
      ...(includeTime ? { hour: "2-digit", minute: "2-digit", timeZone: "UTC" } : {})
    }).format(parsed);
  }

  function statusBadge(value) {
    const normalized = String(value || "").toLowerCase();
    const className = ["active", "posted", "kept", "resolved", "connected"].includes(normalized)
      ? "badge-success"
      : ["pending", "open", "medium", "in_progress", "message_sent", "left_message"].includes(normalized)
        ? "badge-warning"
        : ["reversed", "broken", "defaulted", "high", "no_answer", "wrong_contact"].includes(normalized)
          ? "badge-danger"
          : "badge-neutral";
    const badge = document.createElement("span");
    badge.className = `badge ${className}`;
    badge.textContent = String(value || "Unknown").replaceAll("_", " ");
    return badge;
  }

  function addTextCell(row, value, className) {
    const cell = document.createElement("td");
    cell.textContent = value == null || value === "" ? "—" : String(value);
    if (className) cell.className = className;
    row.append(cell);
    return cell;
  }

  function addPrimaryCell(row, primary, secondary) {
    const cell = document.createElement("td");
    const value = document.createElement("span");
    value.className = "primary-cell";
    value.textContent = primary || "—";
    cell.append(value);
    if (secondary) {
      const note = document.createElement("small");
      note.textContent = secondary;
      cell.append(note);
    }
    row.append(cell);
    return cell;
  }

  function addBadgeCell(row, value) {
    const cell = document.createElement("td");
    cell.append(statusBadge(value));
    row.append(cell);
    return cell;
  }

  function addActionCell(row, action, label) {
    const cell = document.createElement("td");
    const button = document.createElement("button");
    button.className = "table-action";
    button.type = "button";
    button.dataset.action = action;
    button.textContent = label;
    cell.append(button);
    row.append(cell);
    return button;
  }

  document.querySelectorAll("[data-filter-table]").forEach((input) => {
    const table = document.querySelector(input.dataset.filterTable);
    const statusSelect = document.querySelector(input.dataset.statusFilter || "");
    const update = () => filterTable(table, input.value, statusSelect?.value);
    input.addEventListener("input", update);
    statusSelect?.addEventListener("change", update);
    update();
  });
  document.addEventListener("click", (event) => {
    const trigger = event.target.closest("[data-action]");
    if (!trigger) return;
    if (trigger.dataset.action === "download-report") {
      showToast("Report export is unavailable: the current API has no export endpoint.", "error");
    }
    if (trigger.dataset.action === "demo-action") {
      showToast(trigger.dataset.message || "This control is available in the demo preview.");
    }
    if (trigger.dataset.action === "show-details") {
      const dialog = document.getElementById("record-dialog");
      const body = dialog?.querySelector("[data-dialog-content]");
      const source = trigger.closest("tr");
      if (dialog && body && source) {
        const pairs = JSON.parse(source.dataset.details || "[]");
        body.innerHTML = `<div class="detail-grid">${pairs.map(([label, value]) => `
          <div class="detail-item"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>`).join("")}</div>`;
        dialog.showModal();
      }
    }
    if (trigger.dataset.action === "close-dialog") {
      trigger.closest("dialog")?.close();
    }
  });

  function escapeHtml(value) {
    return String(value).replace(/[&<>"']/g, (character) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
    })[character]);
  }

  document.querySelectorAll("[data-dialog-close]").forEach((dialog) => {
    dialog.addEventListener("click", (event) => {
      if (event.target === dialog) dialog.close();
    });
  });

  window.AppUI = {
    showToast,
    showMessage,
    hideMessage,
    filterTable,
    syncEmptyState,
    showTableMessage,
    setApiState,
    clearApiState,
    formatMoney,
    formatDate,
    statusBadge,
    addTextCell,
    addPrimaryCell,
    addBadgeCell,
    addActionCell,
    escapeHtml
  };
})();
