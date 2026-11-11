# User Guide

## Start the local application

Use Python and synthetic data only. From the project root, activate the
backend virtual environment, then run Flask from `backend`:

```powershell
Set-Location backend
python run.py
```

In another PowerShell terminal, serve the frontend:

```powershell
python -m http.server 5500 --bind 127.0.0.1 --directory frontend
```

Open `http://127.0.0.1:5500/`. The backend health endpoint is
`http://127.0.0.1:5000/api/health`. Keep both servers on loopback. The
database is migrated additively when the backend first connects; back up any
database you need before startup.

## Navigate the workspace

The sidebar links to:

- Dashboard
- Customer Management
- Loan Management
- Installment Management
- Payment Management
- Collection Management
- Contact History
- Promise-to-Pay
- Reports

Search inputs and filters operate on the records loaded from the Flask API.
Customer and loan tables provide detail views; customer forms support create
and edit operations.

## Review delinquency

The dashboard displays customer/loan counts, active and overdue loans, overdue
amount, active collection cases, recent payments, and delinquency categories.
The overdue figures are calculated by the API from scheduled installments and
active allocations for posted payments. The API is the source of truth;
the frontend only formats the returned amounts.

The loans page shows each loan's current status and its overdue count. Reports
show overdue counts/amounts by DPD bucket, payment and case counts, and
detected anomaly records.

## Manage a collection case

On Collection Management:

1. Select an overdue loan in **Create a case from current arrears**.
2. Select the case source and submit. The API requires positive arrears and
   returns an existing active case rather than creating a duplicate.
3. Review DPD, arrears, priority, and case status in the table.
4. Change case lifecycle status with the row control. Invalid transitions are
   rejected by the API.
5. Use the account controls to update dispute, hardship, or debt verification
   status. Disputed debt cannot be marked confirmed.

Status changes are recorded in the audit history.

## Configure and record a contact attempt

The Contact History page implements a **neutral test-only policy**, not legal
compliance certification:

1. Select the customer and configure an explicit IANA timezone and allowed
   start/end hours. Attempts are denied while either is missing.
2. Choose a preferred channel and consent status. Leave the allowed-channel
   list blank for no channel-specific restriction; enter a comma-separated
   allow-list to apply a restriction.
3. Weekend and holiday permissions are off by default. Enable them only when
   the synthetic policy configuration explicitly permits them.
4. Add a holiday date and label only when the test scenario requires one. The
   system does not infer a holiday calendar.
5. Select an active case, enter an actual UTC attempt timestamp, choose
   channel/outcome, and submit.

The API validates local time in the configured timezone. A permitted attempt
appears in contact history and audit history. A denied attempt returns an
error, is not listed as a successful contact record, and is retained in audit
history with the denial reason. Do not treat this policy as legal advice or
compliance certification.

## Record and evaluate payment promises

On Promise-to-Pay:

1. Select an active collection case.
2. Enter the promised amount in integer minor currency units (100 INR paise =
   INR 1) and a due date.
3. Submit. The API checks that arrears are positive, the debt is not disputed,
   and the promise does not exceed current arrears.
4. Use **Evaluate overdue promises** to evaluate promises whose due dates have
   passed. Posted payments are evidence; each payment can satisfy at most one
   eligible promise. If periods overlap, evidence is allocated by earliest
   due date, then promise time and ID.
5. A pending promise can be manually marked kept only with enough posted
   payment evidence, or broken only after its due date with insufficient
   evidence. Cancellation is also recorded.

## Review anomalies

Reports runs a repeat-safe detection pass and shows active/resolved findings.
Use **Run detection** to request another pass. Detected types:

- paid account remains in collection
- contact outside configured window
- payment allocated to wrong installment
- promise amount exceeds arrears
- disputed debt treated as confirmed

Detection uses transactional and compliance records, not ground-truth labels.
Ground-truth labels are separate synthetic evaluation data.

## Troubleshooting

- **Cannot reach Flask API:** confirm Flask is running at
  `127.0.0.1:5000` and the browser page is served from the exact allowed
  origin `127.0.0.1:5500`.
- **CORS error:** do not use `localhost`, another port, or a wildcard origin.
- **Contact denied:** review the displayed audit reason, timezone, allowed
  hours, configured permissions, consent, and optional channel list.
- **No eligible case loan:** the API only creates cases when calculated
  arrears are positive.
- **Promise rejected:** check active case status, dispute status, arrears, due
  date, and the amount's minor-unit scale.

For endpoint schemas and response formats, see
[API Documentation](./api_documentation.md).
