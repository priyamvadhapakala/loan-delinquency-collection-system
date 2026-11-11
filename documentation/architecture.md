# Architecture

## Overview

The application is a local three-layer system:

1. A semantic HTML/CSS/JavaScript frontend served as static files.
2. A Flask REST API that validates requests and delegates to service modules.
3. A SQLite database accessed through parameterized SQL.

The frontend uses `frontend/js/api.js` for Fetch requests and shares layout,
navigation, validation helpers, and notifications through `frontend/js/app.js`.
Page modules render API records into the existing tables and forms. The
frontend does not calculate authoritative balances, arrears, priorities, or
compliance decisions.

## Backend request flow

`backend/app/__init__.py` creates the Flask app, registers routes, configures
JSON errors, and grants CORS only to `http://127.0.0.1:5500`. Route modules in
`backend/app/routes/` map HTTP methods and paths to the service layer.
`backend/app/services/` owns input validation and business transactions.
`backend/app/utils/database.py` manages SQLite connections and transaction
boundaries; `backend/app/utils/migrations.py` performs additive, idempotent
schema upgrades at first connection.

The application uses SQLite foreign keys, `CHECK` constraints, indexes, and
triggers to protect identity, schedule, allocation, and history invariants.
Amounts are integer minor units, timestamps are UTC, and SQL parameters are
bound rather than interpolated from request values.

## Main service responsibilities

- Customer, loan, installment, payment, and collection services expose the
  core records and workflows.
- `business_service.py` calculates balances and delinquency from schedules and
  active posted allocations, creates/prioritizes collection cases, validates
  case lifecycle changes, and writes audit events.
- `compliance_service.py` enforces explicit contact settings, records contact
  decisions, manages dispute/hardship/debt status, and validates promises.
- `anomaly_service.py` detects five defined anomaly types from transaction and
  compliance records. Ground-truth labels are stored in a separate table and
  are not read by the detector.

## Calculation and lifecycle rules

- An installment is overdue when its due date is strictly before the selected
  `as_of` date and it still has unpaid scheduled principal or interest.
- Days past due are measured from the oldest unpaid overdue installment.
- Arrears sum the remaining amounts of overdue installments. Outstanding
  balance includes remaining scheduled principal and interest, including
  future installments.
- Active allocations for posted payments reduce installment balances.
- Delinquency buckets are `current`, `1-30`, `31-60`, `61-90`, and `91+` days.
- Case creation requires positive arrears and is idempotent while an active
  case already exists. Priority is low below 31 DPD, medium at 31–60, and high
  at 61 or more.
- Case lifecycle transitions are validated and recorded in the audit log.
- A payment can contribute to at most one eligible promise. When promise
  windows overlap, evidence is allocated by earliest due date, then promise
  timestamp and ID. Only payments after the promise timestamp qualify. This is
  a deterministic application rule, not a financial servicing standard.

## Contact policy

This is a neutral, test-only policy and is not legal compliance certification.
Contact attempts are denied when a customer's timezone or allowed hours are
missing. Configured hours are checked in the configured IANA timezone.
Weekend and holiday contact are denied unless explicitly permitted; a date is
treated as a holiday only when explicitly configured. Channel restrictions
apply only if an allowed-channel list was explicitly saved. Both permitted
and denied attempts are audited. Denied attempts are retained in the audit
table and are not represented as successful contact-history records.

## Schema evolution and data preservation

`database/schema.sql` defines the ten core business tables. Additive runtime
migrations add the contact configuration columns and tables for account
status, audit events, configured holidays, anomaly records, and separate
ground-truth labels. Migrations use `IF NOT EXISTS`/column checks, do not drop
tables or rewrite existing business rows, and run in the current database
connection before API services use the database.

Tests copy the existing SQLite database into isolated temporary files before
applying migrations and inserting synthetic test data. The project database
is therefore not a test fixture.

## Data flow

1. The browser requests a JSON endpoint with the shared API client.
2. Flask validates and routes the request to a service.
3. The service reads or updates records within SQLite transactions; audit
   events are written alongside relevant changes.
4. The frontend renders the returned state and shows success/error feedback.

No background scheduler runs. Promise evaluation and anomaly detection are
explicit API operations; viewing the anomaly report also runs a repeat-safe
detection pass.

## Security and deployment boundaries

This build is designed for local development with synthetic data. It does not
provide user authentication, role-based authorization, CSRF defenses, secret
management, production hosting configuration, or legal compliance assurance.
Keep the API bound to loopback during development, use only synthetic records,
and do not expose it to untrusted networks.
