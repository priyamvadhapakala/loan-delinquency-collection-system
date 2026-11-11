# Testing and Validation

## Automated backend tests

From the project root:

```powershell
python -m pytest backend\tests -q
```

The tests cover API success/error responses, database constraints, transaction
and allocation behavior, schedule-based balances, DPD and delinquency buckets,
collection case creation/priority/lifecycle, promise validation and evaluation,
contact preferences and allowed windows, audit history, account dispute and
hardship status, all five anomaly categories, repeat-safe detection, and the
ground-truth/detector separation.

Each test fixture copies `database\loan_delinquency.db` to a temporary test
database. Tests do not migrate or write test records to the project database.

## Frontend syntax checks

From the project root:

```powershell
$files = Get-ChildItem frontend\js -Filter *.js -Recurse
foreach ($file in $files) { node --check $file.FullName }
python -m compileall -q backend\app backend\tests
```

## Browser and API integration checks

Run Flask at `http://127.0.0.1:5000` and serve `frontend` at the one permitted
origin, `http://127.0.0.1:5500`. Verify:

1. All nine pages load and display a page heading.
2. No JavaScript page exceptions or unexpected HTTP failures occur during
   page loads.
3. Dashboard and report delinquency totals come from
   `/api/reports/delinquency`.
4. Search filters narrow the loaded customer records.
5. Contact preference creation is followed by a permitted attempt (HTTP 201);
   an attempt outside the configured local-time window is denied (HTTP 403),
   and both decisions appear in the audit table.
6. Promise creation succeeds when within arrears; overdue evaluation runs;
   a promise cannot be marked kept without enough posted payments.
7. Account status controls update the API and audit history.
8. A collection case can be created from positive-arrears loan data.
9. Anomaly detection can be triggered repeatedly without adding duplicate
   anomaly records or using ground-truth labels.
10. At a 390-pixel viewport, the customer page remains within the viewport;
    its main content does not introduce document-level horizontal overflow.

The local development CORS check should show
`Access-Control-Allow-Origin: http://127.0.0.1:5500` for that origin and no
allow-origin header for `http://localhost:5500` or other origins. The
preflight response allows the API methods required by the frontend, including
PUT.

## Database checks

Useful read-only checks:

```powershell
python -c "import sqlite3; c=sqlite3.connect(r'database\loan_delinquency.db'); print(c.execute('PRAGMA integrity_check').fetchone()[0]); print(c.execute('PRAGMA foreign_key_check').fetchall()); c.close()"
```

For a migrated test copy, also check `ComplianceAuditEvent` is append-only,
`AnomalyRecord` has no duplicate `(anomaly_type, record_reference)` pairs,
and active payment allocations do not exceed their payment or installment.

## Validation results

Latest automated run: **29 backend tests passed**. Node syntax checks passed
for all **8 frontend JavaScript files**; Python `compileall` passed. Browser
verification loaded all **9 pages** without JavaScript exceptions or
unexpected HTTP failures. Contact permission/denial, promise creation and
evaluation, account status updates, collection case creation, anomaly
detection, search filtering, and a 390-pixel viewport were exercised against
an isolated migrated database copy. The project database SHA-256 remained
unchanged during these checks.

The expected HTTP 403 for a deliberately denied contact and HTTP 409 for an
invalid promise status are validation outcomes, not unexpected runtime
failures.
