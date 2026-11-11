-- Loan Delinquency and Collection Management System
-- Amounts are integer paise; event timestamps are UTC ISO-8601 text.
PRAGMA foreign_keys = ON;
BEGIN IMMEDIATE;

CREATE TABLE IF NOT EXISTS Customer (
    customer_id TEXT PRIMARY KEY
        CHECK (customer_id GLOB 'CUS-[0-9][0-9][0-9][0-9][0-9][0-9]'),
    first_name TEXT NOT NULL CHECK (length(trim(first_name)) > 0),
    last_name TEXT NOT NULL CHECK (length(trim(last_name)) > 0),
    email TEXT NOT NULL UNIQUE CHECK (length(trim(email)) > 0),
    phone TEXT UNIQUE,
    customer_status TEXT NOT NULL DEFAULT 'active'
        CHECK (customer_status IN ('active', 'inactive')),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
        CHECK (strftime('%Y-%m-%dT%H:%M:%SZ', created_at) = created_at)
);

CREATE TABLE IF NOT EXISTS Loan (
    loan_id TEXT PRIMARY KEY
        CHECK (loan_id GLOB 'LON-[0-9][0-9][0-9][0-9][0-9][0-9]'),
    customer_id TEXT NOT NULL
        REFERENCES Customer(customer_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    loan_reference TEXT NOT NULL UNIQUE,
    principal_amount_minor INTEGER NOT NULL CHECK (principal_amount_minor > 0),
    currency_code TEXT NOT NULL DEFAULT 'INR'
        CHECK (currency_code GLOB '[A-Z][A-Z][A-Z]'),
    annual_interest_rate_bps INTEGER NOT NULL
        CHECK (annual_interest_rate_bps BETWEEN 0 AND 100000),
    term_months INTEGER NOT NULL CHECK (term_months BETWEEN 1 AND 600),
    disbursement_date TEXT NOT NULL
        CHECK (date(disbursement_date) = disbursement_date),
    first_due_date TEXT NOT NULL
        CHECK (date(first_due_date) = first_due_date
               AND first_due_date >= disbursement_date),
    loan_status TEXT NOT NULL DEFAULT 'active'
        CHECK (loan_status IN ('active', 'paid_off', 'closed', 'defaulted')),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
        CHECK (strftime('%Y-%m-%dT%H:%M:%SZ', created_at) = created_at)
);

CREATE TABLE IF NOT EXISTS Installment (
    installment_id TEXT PRIMARY KEY
        CHECK (installment_id GLOB 'INS-[0-9][0-9][0-9][0-9][0-9][0-9]'),
    loan_id TEXT NOT NULL
        REFERENCES Loan(loan_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    installment_number INTEGER NOT NULL CHECK (installment_number > 0),
    due_date TEXT NOT NULL CHECK (date(due_date) = due_date),
    scheduled_principal_minor INTEGER NOT NULL
        CHECK (scheduled_principal_minor >= 0),
    scheduled_interest_minor INTEGER NOT NULL
        CHECK (scheduled_interest_minor >= 0),
    CHECK (scheduled_principal_minor + scheduled_interest_minor > 0),
    UNIQUE (loan_id, installment_number),
    UNIQUE (loan_id, due_date)
);

CREATE TABLE IF NOT EXISTS Payment (
    payment_id TEXT PRIMARY KEY
        CHECK (payment_id GLOB 'PAY-[0-9][0-9][0-9][0-9][0-9][0-9]'),
    loan_id TEXT NOT NULL
        REFERENCES Loan(loan_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    received_at TEXT NOT NULL
        CHECK (strftime('%Y-%m-%dT%H:%M:%SZ', received_at) = received_at),
    amount_minor INTEGER NOT NULL CHECK (amount_minor > 0),
    currency_code TEXT NOT NULL CHECK (currency_code GLOB '[A-Z][A-Z][A-Z]'),
    payment_method TEXT NOT NULL
        CHECK (payment_method IN
            ('bank_transfer', 'debit_card', 'cash', 'mobile_wallet',
             'direct_debit', 'other')),
    external_reference TEXT NOT NULL UNIQUE,
    payment_status TEXT NOT NULL DEFAULT 'posted'
        CHECK (payment_status IN ('pending', 'posted', 'reversed')),
    reversed_at TEXT
        CHECK (reversed_at IS NULL
               OR strftime('%Y-%m-%dT%H:%M:%SZ', reversed_at) = reversed_at),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
        CHECK (strftime('%Y-%m-%dT%H:%M:%SZ', created_at) = created_at),
    CHECK ((payment_status = 'reversed' AND reversed_at IS NOT NULL)
           OR (payment_status <> 'reversed' AND reversed_at IS NULL))
);

CREATE TABLE IF NOT EXISTS CollectionCase (
    case_id TEXT PRIMARY KEY
        CHECK (case_id GLOB 'CAS-[0-9][0-9][0-9][0-9][0-9][0-9]'),
    loan_id TEXT NOT NULL
        REFERENCES Loan(loan_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    opened_at TEXT NOT NULL
        CHECK (strftime('%Y-%m-%dT%H:%M:%SZ', opened_at) = opened_at),
    case_status TEXT NOT NULL DEFAULT 'open'
        CHECK (case_status IN ('open', 'in_progress', 'resolved', 'closed')),
    priority TEXT NOT NULL DEFAULT 'medium'
        CHECK (priority IN ('low', 'medium', 'high')),
    case_source TEXT NOT NULL DEFAULT 'system'
        CHECK (case_source IN ('system', 'manual', 'import')),
    closed_at TEXT
        CHECK (closed_at IS NULL
               OR strftime('%Y-%m-%dT%H:%M:%SZ', closed_at) = closed_at),
    CHECK ((case_status IN ('resolved', 'closed') AND closed_at IS NOT NULL)
           OR (case_status IN ('open', 'in_progress') AND closed_at IS NULL))
);

CREATE TABLE IF NOT EXISTS ContactPreference (
    customer_id TEXT PRIMARY KEY
        REFERENCES Customer(customer_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    preferred_channel TEXT NOT NULL
        CHECK (preferred_channel IN ('phone', 'email', 'sms', 'letter', 'none')),
    contact_window TEXT
        CHECK (contact_window IS NULL
               OR contact_window IN ('morning', 'afternoon', 'evening', 'any')),
    consent_status TEXT NOT NULL
        CHECK (consent_status IN ('granted', 'not_required', 'withdrawn')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
        CHECK (strftime('%Y-%m-%dT%H:%M:%SZ', updated_at) = updated_at),
    CHECK (consent_status <> 'withdrawn' OR preferred_channel = 'none')
);

CREATE TABLE IF NOT EXISTS ContactAttempt (
    contact_attempt_id TEXT PRIMARY KEY
        CHECK (contact_attempt_id GLOB 'CNT-[0-9][0-9][0-9][0-9][0-9][0-9]'),
    case_id TEXT NOT NULL
        REFERENCES CollectionCase(case_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    attempted_at TEXT NOT NULL
        CHECK (strftime('%Y-%m-%dT%H:%M:%SZ', attempted_at) = attempted_at),
    channel TEXT NOT NULL CHECK (channel IN ('phone', 'email', 'sms', 'letter')),
    outcome TEXT NOT NULL
        CHECK (outcome IN
            ('connected', 'no_answer', 'left_message', 'message_sent',
             'wrong_contact', 'opted_out')),
    notes TEXT CHECK (notes IS NULL OR length(notes) <= 500)
);

CREATE TABLE IF NOT EXISTS PromiseToPay (
    promise_id TEXT PRIMARY KEY
        CHECK (promise_id GLOB 'PTP-[0-9][0-9][0-9][0-9][0-9][0-9]'),
    case_id TEXT NOT NULL
        REFERENCES CollectionCase(case_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    promised_at TEXT NOT NULL
        CHECK (strftime('%Y-%m-%dT%H:%M:%SZ', promised_at) = promised_at),
    due_date TEXT NOT NULL CHECK (date(due_date) = due_date),
    amount_minor INTEGER NOT NULL CHECK (amount_minor > 0),
    currency_code TEXT NOT NULL CHECK (currency_code GLOB '[A-Z][A-Z][A-Z]'),
    promise_status TEXT NOT NULL DEFAULT 'pending'
        CHECK (promise_status IN ('pending', 'kept', 'broken', 'cancelled')),
    resolved_at TEXT
        CHECK (resolved_at IS NULL
               OR strftime('%Y-%m-%dT%H:%M:%SZ', resolved_at) = resolved_at),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
        CHECK (strftime('%Y-%m-%dT%H:%M:%SZ', created_at) = created_at),
    CHECK (due_date >= substr(promised_at, 1, 10)),
    CHECK ((promise_status = 'pending' AND resolved_at IS NULL)
           OR (promise_status <> 'pending' AND resolved_at IS NOT NULL))
);

CREATE TABLE IF NOT EXISTS DelinquencySnapshot (
    snapshot_id TEXT PRIMARY KEY
        CHECK (snapshot_id GLOB 'SNP-[0-9][0-9][0-9][0-9][0-9][0-9]'),
    loan_id TEXT NOT NULL
        REFERENCES Loan(loan_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    snapshot_date TEXT NOT NULL CHECK (date(snapshot_date) = snapshot_date),
    days_past_due INTEGER NOT NULL CHECK (days_past_due >= 0),
    overdue_amount_minor INTEGER NOT NULL CHECK (overdue_amount_minor >= 0),
    outstanding_principal_minor INTEGER NOT NULL
        CHECK (outstanding_principal_minor >= 0),
    delinquency_bucket TEXT NOT NULL
        CHECK (delinquency_bucket IN
            ('current', '1-30', '31-60', '61-90', '91+')),
    CHECK (
        (days_past_due = 0 AND delinquency_bucket = 'current')
        OR (days_past_due BETWEEN 1 AND 30 AND delinquency_bucket = '1-30')
        OR (days_past_due BETWEEN 31 AND 60 AND delinquency_bucket = '31-60')
        OR (days_past_due BETWEEN 61 AND 90 AND delinquency_bucket = '61-90')
        OR (days_past_due >= 91 AND delinquency_bucket = '91+')
    ),
    CHECK ((days_past_due = 0 AND overdue_amount_minor = 0)
           OR (days_past_due > 0 AND overdue_amount_minor > 0)),
    UNIQUE (loan_id, snapshot_date)
);

CREATE TABLE IF NOT EXISTS PaymentAllocation (
    allocation_id TEXT PRIMARY KEY
        CHECK (allocation_id GLOB 'ALL-[0-9][0-9][0-9][0-9][0-9][0-9]'),
    payment_id TEXT NOT NULL
        REFERENCES Payment(payment_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    installment_id TEXT NOT NULL
        REFERENCES Installment(installment_id) ON UPDATE CASCADE ON DELETE RESTRICT,
    allocated_principal_minor INTEGER NOT NULL
        CHECK (allocated_principal_minor >= 0),
    allocated_interest_minor INTEGER NOT NULL
        CHECK (allocated_interest_minor >= 0),
    allocation_status TEXT NOT NULL DEFAULT 'active'
        CHECK (allocation_status IN ('active', 'reversed')),
    allocated_at TEXT NOT NULL
        CHECK (strftime('%Y-%m-%dT%H:%M:%SZ', allocated_at) = allocated_at),
    reversed_at TEXT
        CHECK (reversed_at IS NULL
               OR strftime('%Y-%m-%dT%H:%M:%SZ', reversed_at) = reversed_at),
    CHECK (allocated_principal_minor + allocated_interest_minor > 0),
    CHECK ((allocation_status = 'active' AND reversed_at IS NULL)
           OR (allocation_status = 'reversed' AND reversed_at IS NOT NULL))
);

CREATE INDEX IF NOT EXISTS ix_loan_customer ON Loan(customer_id);
CREATE INDEX IF NOT EXISTS ix_installment_loan_due
    ON Installment(loan_id, due_date);
CREATE INDEX IF NOT EXISTS ix_payment_loan_received
    ON Payment(loan_id, received_at);
CREATE INDEX IF NOT EXISTS ix_paymentallocation_payment
    ON PaymentAllocation(payment_id);
CREATE INDEX IF NOT EXISTS ix_paymentallocation_installment
    ON PaymentAllocation(installment_id);
CREATE INDEX IF NOT EXISTS ix_case_loan_status
    ON CollectionCase(loan_id, case_status);
CREATE UNIQUE INDEX IF NOT EXISTS ux_case_one_active_per_loan
    ON CollectionCase(loan_id)
    WHERE case_status IN ('open', 'in_progress');
CREATE INDEX IF NOT EXISTS ix_contactattempt_case_time
    ON ContactAttempt(case_id, attempted_at);
CREATE INDEX IF NOT EXISTS ix_promise_case_due
    ON PromiseToPay(case_id, due_date);
CREATE INDEX IF NOT EXISTS ix_snapshot_loan_date
    ON DelinquencySnapshot(loan_id, snapshot_date);

CREATE TRIGGER IF NOT EXISTS payment_currency_matches_loan_insert
BEFORE INSERT ON Payment
WHEN NEW.currency_code <> (
    SELECT currency_code FROM Loan WHERE loan_id = NEW.loan_id
)
BEGIN
    SELECT RAISE(ABORT, 'payment currency must match its loan');
END;

CREATE TRIGGER IF NOT EXISTS payment_currency_matches_loan_update
BEFORE UPDATE OF loan_id, currency_code ON Payment
WHEN NEW.currency_code <> (
    SELECT currency_code FROM Loan WHERE loan_id = NEW.loan_id
)
BEGIN
    SELECT RAISE(ABORT, 'payment currency must match its loan');
END;

CREATE TRIGGER IF NOT EXISTS payment_financial_fields_immutable
BEFORE UPDATE OF loan_id, received_at, amount_minor, currency_code,
                 payment_method, external_reference, created_at ON Payment
BEGIN
    SELECT RAISE(ABORT, 'payment financial details are immutable');
END;

CREATE TRIGGER IF NOT EXISTS payment_status_transition_guard
BEFORE UPDATE OF payment_status ON Payment
WHEN NEW.payment_status <> OLD.payment_status
BEGIN
    SELECT CASE
        WHEN NOT (
            (OLD.payment_status = 'pending'
             AND NEW.payment_status IN ('posted', 'reversed'))
            OR (OLD.payment_status = 'posted'
                AND NEW.payment_status = 'reversed')
        )
        THEN RAISE(ABORT, 'invalid payment status transition')
    END;
    SELECT CASE
        WHEN NEW.payment_status = 'reversed'
             AND EXISTS (
                 SELECT 1 FROM PaymentAllocation
                 WHERE payment_id = OLD.payment_id
                   AND allocation_status = 'active'
             )
        THEN RAISE(ABORT, 'reverse active allocations before reversing payment')
    END;
END;

CREATE TRIGGER IF NOT EXISTS payment_no_delete
BEFORE DELETE ON Payment
BEGIN
    SELECT RAISE(ABORT, 'payments are historical records and cannot be deleted');
END;

CREATE TRIGGER IF NOT EXISTS promise_currency_matches_loan_insert
BEFORE INSERT ON PromiseToPay
WHEN NEW.currency_code <> (
    SELECT l.currency_code
    FROM CollectionCase c JOIN Loan l ON l.loan_id = c.loan_id
    WHERE c.case_id = NEW.case_id
)
BEGIN
    SELECT RAISE(ABORT, 'promise currency must match its loan');
END;

CREATE TRIGGER IF NOT EXISTS promise_financial_fields_immutable
BEFORE UPDATE OF case_id, promised_at, due_date, amount_minor,
                 currency_code, created_at ON PromiseToPay
BEGIN
    SELECT RAISE(ABORT, 'promise terms are immutable');
END;

CREATE TRIGGER IF NOT EXISTS promise_no_delete
BEFORE DELETE ON PromiseToPay
BEGIN
    SELECT RAISE(ABORT, 'payment promises are historical records and cannot be deleted');
END;

CREATE TRIGGER IF NOT EXISTS contact_attempt_no_update
BEFORE UPDATE ON ContactAttempt
BEGIN
    SELECT RAISE(ABORT, 'contact attempts are historical records and cannot be updated');
END;

CREATE TRIGGER IF NOT EXISTS contact_attempt_no_delete
BEFORE DELETE ON ContactAttempt
BEGIN
    SELECT RAISE(ABORT, 'contact attempts are historical records and cannot be deleted');
END;

CREATE TRIGGER IF NOT EXISTS snapshot_outstanding_not_above_principal
BEFORE INSERT ON DelinquencySnapshot
WHEN NEW.outstanding_principal_minor > (
    SELECT principal_amount_minor
    FROM Loan WHERE loan_id = NEW.loan_id
)
BEGIN
    SELECT RAISE(ABORT, 'snapshot principal cannot exceed original principal');
END;

CREATE TRIGGER IF NOT EXISTS snapshot_no_update
BEFORE UPDATE ON DelinquencySnapshot
BEGIN
    SELECT RAISE(ABORT, 'delinquency snapshots are immutable');
END;

CREATE TRIGGER IF NOT EXISTS snapshot_no_delete
BEFORE DELETE ON DelinquencySnapshot
BEGIN
    SELECT RAISE(ABORT, 'delinquency snapshots are historical records and cannot be deleted');
END;

CREATE TRIGGER IF NOT EXISTS allocation_loan_matches_payment_insert
BEFORE INSERT ON PaymentAllocation
WHEN (
    SELECT p.loan_id FROM Payment p WHERE p.payment_id = NEW.payment_id
) IS NOT (
    SELECT i.loan_id FROM Installment i WHERE i.installment_id = NEW.installment_id
)
BEGIN
    SELECT RAISE(ABORT, 'payment and installment must belong to the same loan');
END;

CREATE TRIGGER IF NOT EXISTS allocation_active_limits_insert
BEFORE INSERT ON PaymentAllocation
WHEN NEW.allocation_status = 'active'
BEGIN
    SELECT CASE
        WHEN (SELECT payment_status FROM Payment
              WHERE payment_id = NEW.payment_id) <> 'posted'
        THEN RAISE(ABORT, 'only posted payments can have active allocations')
    END;
    SELECT CASE
        WHEN COALESCE((
            SELECT SUM(allocated_principal_minor + allocated_interest_minor)
            FROM PaymentAllocation
            WHERE payment_id = NEW.payment_id AND allocation_status = 'active'
        ), 0) + NEW.allocated_principal_minor + NEW.allocated_interest_minor
        > (SELECT amount_minor FROM Payment WHERE payment_id = NEW.payment_id)
        THEN RAISE(ABORT, 'active allocations cannot exceed payment amount')
    END;
    SELECT CASE
        WHEN COALESCE((
            SELECT SUM(allocated_principal_minor)
            FROM PaymentAllocation
            WHERE installment_id = NEW.installment_id
              AND allocation_status = 'active'
        ), 0) + NEW.allocated_principal_minor
        > (SELECT scheduled_principal_minor FROM Installment
           WHERE installment_id = NEW.installment_id)
        THEN RAISE(ABORT, 'principal allocations cannot exceed scheduled principal')
    END;
    SELECT CASE
        WHEN COALESCE((
            SELECT SUM(allocated_interest_minor)
            FROM PaymentAllocation
            WHERE installment_id = NEW.installment_id
              AND allocation_status = 'active'
        ), 0) + NEW.allocated_interest_minor
        > (SELECT scheduled_interest_minor FROM Installment
           WHERE installment_id = NEW.installment_id)
        THEN RAISE(ABORT, 'interest allocations cannot exceed scheduled interest')
    END;
END;

CREATE TRIGGER IF NOT EXISTS allocation_state_transition_guard
BEFORE UPDATE OF allocation_status ON PaymentAllocation
WHEN NEW.allocation_status <> OLD.allocation_status
BEGIN
    SELECT CASE
        WHEN OLD.allocation_status <> 'active'
             OR NEW.allocation_status <> 'reversed'
        THEN RAISE(ABORT, 'allocations may only transition from active to reversed')
    END;
END;

CREATE TRIGGER IF NOT EXISTS allocation_financial_fields_immutable
BEFORE UPDATE OF payment_id, installment_id, allocated_principal_minor,
                 allocated_interest_minor, allocated_at ON PaymentAllocation
BEGIN
    SELECT RAISE(ABORT, 'allocation financial details are immutable');
END;

CREATE TRIGGER IF NOT EXISTS allocation_no_delete
BEFORE DELETE ON PaymentAllocation
BEGIN
    SELECT RAISE(ABORT, 'payment allocations are historical records and cannot be deleted');
END;

COMMIT;
