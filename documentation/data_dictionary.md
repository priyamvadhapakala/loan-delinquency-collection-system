# Data Dictionary

SQLite stores monetary amounts as integer paise (`INR` minor units), dates as
ISO `YYYY-MM-DD` text, and event times as UTC ISO-8601
`YYYY-MM-DDTHH:MM:SSZ` text. `PK` means primary key; `FK` means foreign key.

## Customer

| Column | SQLite type | Key / rules | Meaning |
|---|---|---|---|
| `customer_id` | TEXT | PK; `CUS-` plus six digits | Stable customer identifier |
| `first_name` | TEXT | NOT NULL, non-empty | Given name |
| `last_name` | TEXT | NOT NULL, non-empty | Family name |
| `email` | TEXT | NOT NULL, UNIQUE | Contact email |
| `phone` | TEXT | UNIQUE, nullable | Contact phone |
| `customer_status` | TEXT | NOT NULL; `active` or `inactive` | Customer lifecycle state |
| `created_at` | TEXT | NOT NULL; UTC timestamp | Record creation time |

## Loan

| Column | SQLite type | Key / rules | Meaning |
|---|---|---|---|
| `loan_id` | TEXT | PK; `LON-` plus six digits | Stable loan identifier |
| `customer_id` | TEXT | FK to `Customer.customer_id`, NOT NULL | Borrower |
| `loan_reference` | TEXT | NOT NULL, UNIQUE | External/business loan reference |
| `principal_amount_minor` | INTEGER | NOT NULL, greater than zero | Original principal in paise |
| `currency_code` | TEXT | NOT NULL; three uppercase letters | ISO-style currency code; sample uses INR |
| `annual_interest_rate_bps` | INTEGER | NOT NULL; 0–100000 | Annual interest rate in basis points |
| `term_months` | INTEGER | NOT NULL; 1–600 | Contract term |
| `disbursement_date` | TEXT | NOT NULL; valid calendar date | Disbursement date |
| `first_due_date` | TEXT | NOT NULL; on/after disbursement | First scheduled due date |
| `loan_status` | TEXT | NOT NULL; `active`, `paid_off`, `closed`, or `defaulted` | Loan lifecycle state |
| `created_at` | TEXT | NOT NULL; UTC timestamp | Record creation time |

## Installment

| Column | SQLite type | Key / rules | Meaning |
|---|---|---|---|
| `installment_id` | TEXT | PK; `INS-` plus six digits | Stable installment identifier |
| `loan_id` | TEXT | FK to `Loan.loan_id`, NOT NULL | Loan schedule owner |
| `installment_number` | INTEGER | NOT NULL, greater than zero | Sequence number in the loan schedule |
| `due_date` | TEXT | NOT NULL; valid calendar date | Contractual due date |
| `scheduled_principal_minor` | INTEGER | NOT NULL, zero or greater | Scheduled principal in paise |
| `scheduled_interest_minor` | INTEGER | NOT NULL, zero or greater | Scheduled interest in paise |

The principal and interest together must be greater than zero. `(loan_id,
installment_number)` and `(loan_id, due_date)` are each unique.

## Payment

| Column | SQLite type | Key / rules | Meaning |
|---|---|---|---|
| `payment_id` | TEXT | PK; `PAY-` plus six digits | Stable payment identifier |
| `loan_id` | TEXT | FK to `Loan.loan_id`, NOT NULL | Loan receiving the payment |
| `received_at` | TEXT | NOT NULL; UTC timestamp | Time funds were received |
| `amount_minor` | INTEGER | NOT NULL, greater than zero | Received amount in paise |
| `currency_code` | TEXT | NOT NULL; three uppercase letters | Must match the loan currency |
| `payment_method` | TEXT | NOT NULL; constrained category | `bank_transfer`, `debit_card`, `cash`, `mobile_wallet`, `direct_debit`, or `other` |
| `external_reference` | TEXT | NOT NULL, UNIQUE | Unique synthetic/payment-provider reference |
| `payment_status` | TEXT | NOT NULL; `pending`, `posted`, or `reversed` | Transaction state |
| `reversed_at` | TEXT | Nullable UTC timestamp | Required for a reversed payment |
| `created_at` | TEXT | NOT NULL; UTC timestamp | Record creation time |

Payment financial details cannot be edited or deleted. Allowed state changes
are pending to posted/reversed and posted to reversed; active allocations must
be reversed before reversing a payment.

## CollectionCase

| Column | SQLite type | Key / rules | Meaning |
|---|---|---|---|
| `case_id` | TEXT | PK; `CAS-` plus six digits | Stable collection case identifier |
| `loan_id` | TEXT | FK to `Loan.loan_id`, NOT NULL | Loan being followed up |
| `opened_at` | TEXT | NOT NULL; UTC timestamp | Case opening time |
| `case_status` | TEXT | NOT NULL; `open`, `in_progress`, `resolved`, or `closed` | Operational state |
| `priority` | TEXT | NOT NULL; `low`, `medium`, or `high` | Collection priority |
| `case_source` | TEXT | NOT NULL; `system`, `manual`, or `import` | Case creation source |
| `closed_at` | TEXT | Nullable UTC timestamp | Required for resolved/closed cases; otherwise NULL |

A partial unique index allows at most one open or in-progress case per loan.

## ContactPreference

| Column | SQLite type | Key / rules | Meaning |
|---|---|---|---|
| `customer_id` | TEXT | PK and FK to `Customer.customer_id` | Customer with this preference |
| `preferred_channel` | TEXT | NOT NULL; `phone`, `email`, `sms`, `letter`, or `none` | Preferred contact method |
| `contact_window` | TEXT | Nullable; `morning`, `afternoon`, `evening`, or `any` | Preferred time window |
| `consent_status` | TEXT | NOT NULL; `granted`, `not_required`, or `withdrawn` | Contact consent state |
| `updated_at` | TEXT | NOT NULL; UTC timestamp | Last preference update time |
| `timezone` | TEXT | Nullable IANA timezone | Local timezone required before contact is allowed |
| `allowed_contact_start` | TEXT | Nullable `HH:MM` | Start of the explicitly configured contact window |
| `allowed_contact_end` | TEXT | Nullable `HH:MM` | End of the explicitly configured contact window |
| `weekend_contact_allowed` | INTEGER | NOT NULL; 0 or 1, default 0 | Explicit test-policy weekend permission |
| `holiday_contact_allowed` | INTEGER | NOT NULL; 0 or 1, default 0 | Explicit permission for configured holidays |
| `allowed_channels_json` | TEXT | Nullable JSON array | Optional explicit channel allow-list |

Withdrawn consent requires the preferred channel to be `none`.
Timezone and hours are nullable for backward-compatible migration, but the
contact service denies attempts when either is missing. This neutral policy is
for tests only and is not legal compliance certification.

## ContactAttempt

| Column | SQLite type | Key / rules | Meaning |
|---|---|---|---|
| `contact_attempt_id` | TEXT | PK; `CNT-` plus six digits | Stable contact event identifier |
| `case_id` | TEXT | FK to `CollectionCase.case_id`, NOT NULL | Case associated with the attempt |
| `attempted_at` | TEXT | NOT NULL; UTC timestamp | Attempt time |
| `channel` | TEXT | NOT NULL; `phone`, `email`, `sms`, or `letter` | Channel used |
| `outcome` | TEXT | NOT NULL; constrained category | `connected`, `no_answer`, `left_message`, `message_sent`, `wrong_contact`, or `opted_out` |
| `notes` | TEXT | Nullable; maximum 500 characters | Short synthetic operational note |

Contact attempts are immutable and cannot be deleted.

## PromiseToPay

| Column | SQLite type | Key / rules | Meaning |
|---|---|---|---|
| `promise_id` | TEXT | PK; `PTP-` plus six digits | Stable promise identifier |
| `case_id` | TEXT | FK to `CollectionCase.case_id`, NOT NULL | Related collection case |
| `promised_at` | TEXT | NOT NULL; UTC timestamp | Time the promise was recorded |
| `due_date` | TEXT | NOT NULL; valid date, on/after promise date | Promised payment date |
| `amount_minor` | INTEGER | NOT NULL, greater than zero | Promised amount in paise |
| `currency_code` | TEXT | NOT NULL; must match the case loan | Promise currency |
| `promise_status` | TEXT | NOT NULL; `pending`, `kept`, `broken`, or `cancelled` | Promise outcome |
| `resolved_at` | TEXT | Nullable UTC timestamp | NULL while pending; required after resolution |
| `created_at` | TEXT | NOT NULL; UTC timestamp | Record creation time |

Promise terms cannot be edited or deleted; the outcome can be updated.
Status evaluation uses posted payment evidence within the promise window. A
payment is applied to at most one promise; overlapping windows are evaluated
in earliest due-date order.

## DelinquencySnapshot

| Column | SQLite type | Key / rules | Meaning |
|---|---|---|---|
| `snapshot_id` | TEXT | PK; `SNP-` plus six digits | Stable snapshot identifier |
| `loan_id` | TEXT | FK to `Loan.loan_id`, NOT NULL | Loan summarized |
| `snapshot_date` | TEXT | NOT NULL; valid date | Date the values represent |
| `days_past_due` | INTEGER | NOT NULL, zero or greater | Days since the oldest unpaid installment due date |
| `overdue_amount_minor` | INTEGER | NOT NULL, zero or greater | Unpaid scheduled amount due before snapshot date, in paise |
| `outstanding_principal_minor` | INTEGER | NOT NULL, zero or greater | Original principal less active allocated principal, in paise |
| `delinquency_bucket` | TEXT | NOT NULL; `current`, `1-30`, `31-60`, `61-90`, or `91+` | Bucket corresponding to days past due |

Bucket and amount/day consistency are checked. A loan can have only one
snapshot per date. Snapshots are immutable.

## PaymentAllocation

| Column | SQLite type | Key / rules | Meaning |
|---|---|---|---|
| `allocation_id` | TEXT | PK; `ALL-` plus six digits | Stable allocation/history identifier |
| `payment_id` | TEXT | FK to `Payment.payment_id`, NOT NULL | Source payment |
| `installment_id` | TEXT | FK to `Installment.installment_id`, NOT NULL | Target installment |
| `allocated_principal_minor` | INTEGER | NOT NULL, zero or greater | Payment portion applied to principal |
| `allocated_interest_minor` | INTEGER | NOT NULL, zero or greater | Payment portion applied to interest |
| `allocation_status` | TEXT | NOT NULL; `active` or `reversed` | Whether the allocation currently counts |
| `allocated_at` | TEXT | NOT NULL; UTC timestamp | Allocation time |
| `reversed_at` | TEXT | Nullable UTC timestamp | Required when allocation is reversed |

At least one allocated component must be positive. The allocated total is the
sum of principal and interest; active allocations are constrained by database
triggers so they cannot exceed the source payment or the remaining scheduled
component amounts. Allocation financial details cannot be edited or deleted;
reversals remain in the table for history.

## LoanAccountStatus (runtime additive table)

| Column | SQLite type | Key / rules | Meaning |
|---|---|---|---|
| `loan_id` | TEXT | PK and FK to `Loan.loan_id` | Loan account |
| `dispute_status` | TEXT | `clear`, `disputed`, or `resolved` | Current debt dispute state |
| `hardship_status` | TEXT | `none`, `active`, or `resolved` | Current hardship state |
| `debt_status` | TEXT | `unverified` or `confirmed` | Debt verification state |
| `updated_at` | TEXT | NOT NULL; UTC timestamp | Last status change |

The service rejects a simultaneous `disputed` and `confirmed` state.

## ComplianceAuditEvent (runtime additive table)

| Column | SQLite type | Key / rules | Meaning |
|---|---|---|---|
| `audit_id` | TEXT | PK; `AUD-` plus six digits | Audit event identifier |
| `event_at` | TEXT | NOT NULL; UTC timestamp | Event time |
| `action` | TEXT | NOT NULL | Event action name |
| `entity_type` | TEXT | NOT NULL | Related entity category |
| `entity_id` | TEXT | NOT NULL | Related entity identifier |
| `outcome` | TEXT | `permitted`, `denied`, or `success` | Decision/result |
| `reason` | TEXT | NOT NULL | Human-readable event reason |
| `details_json` | TEXT | Valid JSON | Non-secret event metadata |

Audit records are immutable. Denied contacts are recorded here even though
they are not successful `ContactAttempt` rows.

## ContactHoliday (runtime additive table)

| Column | SQLite type | Key / rules | Meaning |
|---|---|---|---|
| `holiday_date` | TEXT | PK; valid `YYYY-MM-DD` | Explicitly configured test holiday |
| `label` | TEXT | NOT NULL, non-empty | Synthetic holiday label |
| `configured_at` | TEXT | NOT NULL; UTC timestamp | Configuration time |

No holiday dates are inferred from jurisdictional calendars.

## AnomalyRecord (runtime additive table)

| Column | SQLite type | Key / rules | Meaning |
|---|---|---|---|
| `anomaly_id` | TEXT | PK; `ANM-` plus six digits | Finding identifier |
| `anomaly_type` | TEXT | Constrained category | One of the five detected anomaly types |
| `record_reference` | TEXT | NOT NULL | Related record identifier |
| `reason` | TEXT | NOT NULL | Detection explanation |
| `detection_status` | TEXT | `active` or `resolved` | State from latest detection |
| `first_detected_at` | TEXT | NOT NULL; UTC timestamp | First detection time |
| `last_detected_at` | TEXT | NOT NULL; UTC timestamp | Most recent detection/resolution pass |

`(anomaly_type, record_reference)` is unique, so rerunning detection updates
the finding rather than duplicating it.

## AnomalyGroundTruth (runtime additive table)

| Column | SQLite type | Key / rules | Meaning |
|---|---|---|---|
| `label_id` | TEXT | PK | Synthetic label identifier |
| `anomaly_type` | TEXT | NOT NULL | Ground-truth category |
| `record_reference` | TEXT | NOT NULL | Record used for evaluation |
| `is_anomaly` | INTEGER | 0 or 1 | Ground-truth label |
| `label_source` | TEXT | NOT NULL | Synthetic evaluation source |
| `labeled_at` | TEXT | NOT NULL | Label timestamp |

Labels are maintained separately and are never queried by anomaly detection.
