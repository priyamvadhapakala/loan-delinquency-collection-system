# Database Design

## Scope

The core schema in `database/schema.sql` contains ten business tables. The
backend adds contact-rule configuration, account status, audit, and anomaly
tables through idempotent additive migrations on first database connection.
No existing business table is dropped or replaced.

## Relationships

- One `Customer` can have many `Loan` records.
- One `Customer` has zero or one `ContactPreference`, including explicit
  timezone and allowed contact-hour settings.
- One `Loan` has many `Installment`, `Payment`, `CollectionCase`, and
  `DelinquencySnapshot` records.
- A `Payment` can be split among multiple `Installment` records through
  `PaymentAllocation`. An installment can also receive allocations from
  multiple payments, which supports partial payments.
- One `CollectionCase` can have many `ContactAttempt` and `PromiseToPay`
  records.
- A collection case belongs to a loan. Contact attempts and promises reach the
  customer through that case and loan.

Foreign keys use restrictive deletion so a parent with dependent records
cannot be removed. IDs are stable, prefixed text identifiers (for example,
`CUS-000001` and `LON-000001`). Unique external references and schedule keys
prevent repeated business records.

## Table purpose

| Table | Purpose |
|---|---|
| `Customer` | Synthetic customer identity and contact details |
| `Loan` | Principal, currency, rate, term, and lifecycle |
| `Installment` | Scheduled principal and interest by due date |
| `Payment` | Received payment transactions and reversal state |
| `CollectionCase` | Operational follow-up case for a loan |
| `ContactPreference` | One current channel, contact window, and consent state per customer |
| `ContactAttempt` | Immutable history of collection communications |
| `PromiseToPay` | Promised amount/date and its operational outcome |
| `DelinquencySnapshot` | Immutable point-in-time delinquency and balance values |
| `PaymentAllocation` | Principal/interest portions of payments applied to installments |
| `LoanAccountStatus` | Dispute, hardship, and debt-verification status for a loan |
| `ComplianceAuditEvent` | Append-only audit history, including denied contacts |
| `ContactHoliday` | Explicitly configured synthetic test-policy holiday dates |
| `AnomalyRecord` | Repeat-safe, persisted anomaly detection results |
| `AnomalyGroundTruth` | Separate synthetic labels used for evaluation, never as detector inputs |

## Amounts, dates, and statuses

- All monetary values are integer **paise** (`INR` minor units); no floating
  point values are used. For example, `100000` means INR 1,000.00.
- Interest rates are integer basis points; 100 basis points equal 1%.
- Calendar dates use `YYYY-MM-DD`. Event timestamps use UTC
  `YYYY-MM-DDTHH:MM:SSZ`.
- Status and category fields have `CHECK` constraints. Delinquency bucket
  values must agree with the stored days-past-due range.
- The runtime business service calculates balances from installment schedules
  and active posted allocations. A snapshot is an explicit historical record,
  not a substitute for the live calculation.
- The database stores installment schedules and point-in-time snapshots; it
  does not recalculate loan balances automatically. Snapshot amounts in the
  seed data are calculated from scheduled installments and posted allocations
  as of the snapshot date.

## Payment allocation and history rules

`PaymentAllocation` stores principal and interest allocated separately.
Database triggers ensure that:

- an allocation's payment and installment belong to the same loan;
- active allocations belong to posted payments;
- active allocations do not exceed the payment amount;
- allocated principal and interest do not exceed the matching installment
  components.

Allocation financial fields cannot be edited or deleted. An active allocation
may be reversed with a reversal timestamp; a reversed allocation is retained
as history. Payment financial details are immutable; a payment can move from
pending to posted or reversed, or from posted to reversed. Active allocations
must be reversed before the payment itself can be reversed. Contact attempts
and delinquency snapshots are immutable records. Promise terms are immutable
while their outcome can be updated.

## Sample data and reproducibility

`database/seed_data.sql` contains six fully synthetic customers, six loans,
36 installments, 13 posted payments, 13 allocations, five collection cases,
six contact preferences, five contact attempts, five promises, and six
snapshots. Synthetic customer names were selected using the fixed seed
`20261022` and `random.Random`; resulting values are stored directly in SQL so
the seed file runs in SQLite without a Python dependency. The seed includes
both fully paid and partial installment allocations, delinquent and current
loans, and a pending, kept, and broken promise.

No sample anomaly records or randomly assigned balances/statuses are included.
The six snapshots are for `2026-10-22`; their values were calculated from the
installments and active posted allocations at that cutoff.

## Initialization

The existing To initialize a new empty SQLite database, enable foreign keys on the
connection, execute `database/schema.sql`, then execute `database/seed_data.sql`. The seed
file is intentionally insert-only: it does not delete or replace data and
should be run once per database. A uniqueness failure on a repeated seed run
is intentional and protects existing records.

## Indexes and constraints

Primary keys, unique email/reference fields, unique loan installment numbers
and due dates, and one snapshot per loan/date prevent duplicate records.
Foreign-key indexes support common joins. A partial unique index permits at
most one open or in-progress case per loan. `NOT NULL`, `UNIQUE`, `CHECK`,
foreign-key, and trigger constraints enforce the invariants described above.

## Additive compliance tables

The runtime migration checks existing columns and creates these tables and
indexes without deleting existing rows:

- `LoanAccountStatus` has one row per loan and constrains dispute, hardship,
  and debt-verification status. A disputed debt cannot be saved as confirmed
  through the service.
- `ComplianceAuditEvent` records UTC time, action, entity, outcome, reason,
  and JSON details. Database triggers prevent audit rows from being updated
  or deleted.
- `ContactHoliday` contains only dates explicitly configured for the
  test-only contact policy; the application does not infer a holiday calendar.
- `AnomalyRecord` has a unique `(anomaly_type, record_reference)` key.
  Detection updates an existing finding rather than creating duplicate rows.
- `AnomalyGroundTruth` stores synthetic evaluation labels separately from the
  anomaly input fields. Detection code does not query this table.

The contact preference migration adds nullable `timezone`,
`allowed_contact_start`, and `allowed_contact_end`; weekend/holiday permission
flags default to false; an optional JSON allowed-channel list is nullable.
The contact service denies attempts when timezone or allowed hours are not
configured. These rules are test-only, not legal compliance certification.
