# Loan Delinquency and Collection Management System

A local Flask, SQLite, and vanilla JavaScript application for managing loan
installments, payments, delinquency, collection cases, customer contacts,
payment promises, compliance audit history, and anomaly detection.

## Status and scope

Phases 0–8 are implemented. The application is intended for local development
and synthetic data only. It has no authentication or production security
controls. The contact policy is a neutral test policy, not legal compliance
certification.

## Technology

- Python 3.10+ and Flask
- SQLite and SQL
- HTML5, CSS3, and JavaScript Fetch API
- Pytest

## Project layout

- `backend/app/routes/` — REST API route modules.
- `backend/app/services/` — data access and business/compliance services.
- `backend/app/utils/` — database, migration, and shared utility code.
- `backend/tests/` — API, business-rule, compliance, anomaly, and regression tests.
- `database/` — core schema, synthetic seed data, and local SQLite database.
- `frontend/index.html` — dashboard.
- `frontend/pages/` — customer, loan, installment, payment, collection, contact,
  promise, and report pages.
- `frontend/css/` and `frontend/js/` — shared UI styles and page/API behavior.
- `documentation/` — architecture, database, API, test, and user documentation.

## Run locally on Windows

From the project root, create and activate a virtual environment, then install
the backend dependencies:

```powershell
python -m venv backend\.venv
backend\.venv\Scripts\Activate.ps1
python -m pip install -r backend\requirements.txt
```

In one PowerShell terminal, start Flask:

```powershell
Set-Location backend
python run.py
```

In a second terminal, serve the frontend from the project root:

```powershell
python -m http.server 5500 --bind 127.0.0.1 --directory frontend
```

Open `http://127.0.0.1:5500/`. The frontend calls the Flask API at
`http://127.0.0.1:5000/api`. Local browser CORS is restricted to the exact
frontend origin `http://127.0.0.1:5500`; do not change it to a wildcard.

The backend uses `database\loan_delinquency.db` by default. On its first
database connection it applies backward-compatible, additive migrations for
the newer business and compliance tables. Existing records are retained.
Back up the database before running migrations on any data you need to keep.

## Run tests

From the project root:

```powershell
python -m pytest backend\tests -q
```

Tests use isolated copies of the SQLite database. They do not seed, clear, or
write test records to the project database.

## Documentation

- [Architecture](documentation/architecture.md)
- [Database design](documentation/database_design.md)
- [Data dictionary](documentation/data_dictionary.md)
- [API documentation](documentation/api_documentation.md)
- [Testing documentation](documentation/testing_documentation.md)
- [User guide](documentation/user_guide.md)

## Important limitations

- This is a local synthetic-data project, not a production collections system.
- No authentication, authorization, deployment hardening, or production
  monitoring is provided.
- Contact preferences require an explicit IANA timezone and allowed hours.
  Weekend/holiday permissions default to false; holidays must be explicitly
  configured. The policy makes no jurisdiction-specific legal-hours claim.
- Promise fulfillment uses posted payment evidence and assigns each payment
  to at most one eligible promise, in earliest-due order.
- Reports operate on records and calculations exposed by the local API; they
  are not regulatory or accounting statements.
