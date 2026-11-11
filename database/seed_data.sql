-- Synthetic baseline fixtures. Customer names were selected using
-- random.Random(20261022); values are frozen here for repeatable SQLite-only use.
-- All balances and delinquency snapshots below were calculated from the schedule
-- and posted allocations as of 2026-10-22; none are randomly assigned.
PRAGMA foreign_keys = ON;
BEGIN IMMEDIATE;

INSERT INTO Customer
    (customer_id, first_name, last_name, email, phone, customer_status, created_at)
VALUES
    ('CUS-000001', 'Vikram', 'Patel', 'vikram.patel.1@example.test', '+910000010001', 'active', '2026-03-01T09:00:00Z'),
    ('CUS-000002', 'Sana', 'Menon', 'sana.menon.2@example.test', '+910000010002', 'active', '2026-03-02T09:00:00Z'),
    ('CUS-000003', 'Dev', 'Bose', 'dev.bose.3@example.test', '+910000010003', 'active', '2026-03-03T09:00:00Z'),
    ('CUS-000004', 'Isha', 'Kapoor', 'isha.kapoor.4@example.test', '+910000010004', 'active', '2026-03-04T09:00:00Z'),
    ('CUS-000005', 'Isha', 'Bose', 'isha.bose.5@example.test', '+910000010005', 'active', '2026-03-05T09:00:00Z'),
    ('CUS-000006', 'Zoya', 'Singh', 'zoya.singh.6@example.test', '+910000010006', 'active', '2026-03-06T09:00:00Z');

INSERT INTO Loan
    (loan_id, customer_id, loan_reference, principal_amount_minor, currency_code,
     annual_interest_rate_bps, term_months, disbursement_date, first_due_date,
     loan_status, created_at)
VALUES
    ('LON-000001', 'CUS-000001', 'LN-2026-0001', 24000000, 'INR', 1200, 6, '2026-03-15', '2026-07-01', 'active', '2026-03-15T10:00:00Z'),
    ('LON-000002', 'CUS-000002', 'LN-2026-0002', 18000000, 'INR', 1200, 6, '2026-03-20', '2026-07-01', 'active', '2026-03-20T10:00:00Z'),
    ('LON-000003', 'CUS-000003', 'LN-2026-0003', 30000000, 'INR', 1500, 6, '2026-02-01', '2026-07-01', 'active', '2026-02-01T10:00:00Z'),
    ('LON-000004', 'CUS-000004', 'LN-2026-0004', 12000000, 'INR', 900, 6, '2026-05-01', '2026-07-01', 'active', '2026-05-01T10:00:00Z'),
    ('LON-000005', 'CUS-000005', 'LN-2026-0005', 36000000, 'INR', 1000, 6, '2026-06-10', '2026-11-01', 'active', '2026-06-10T10:00:00Z'),
    ('LON-000006', 'CUS-000006', 'LN-2026-0006', 21000000, 'INR', 1200, 6, '2026-05-15', '2026-08-01', 'active', '2026-05-15T10:00:00Z');

INSERT INTO Installment
    (installment_id, loan_id, installment_number, due_date,
     scheduled_principal_minor, scheduled_interest_minor)
VALUES
    ('INS-000001', 'LON-000001', 1, '2026-07-01', 4000000, 240000),
    ('INS-000002', 'LON-000001', 2, '2026-08-01', 4000000, 200000),
    ('INS-000003', 'LON-000001', 3, '2026-09-01', 4000000, 160000),
    ('INS-000004', 'LON-000001', 4, '2026-10-01', 4000000, 120000),
    ('INS-000005', 'LON-000001', 5, '2026-11-01', 4000000, 80000),
    ('INS-000006', 'LON-000001', 6, '2026-12-01', 4000000, 40000),
    ('INS-000007', 'LON-000002', 1, '2026-07-01', 3000000, 180000),
    ('INS-000008', 'LON-000002', 2, '2026-08-01', 3000000, 150000),
    ('INS-000009', 'LON-000002', 3, '2026-09-01', 3000000, 120000),
    ('INS-000010', 'LON-000002', 4, '2026-10-01', 3000000, 90000),
    ('INS-000011', 'LON-000002', 5, '2026-11-01', 3000000, 60000),
    ('INS-000012', 'LON-000002', 6, '2026-12-01', 3000000, 30000),
    ('INS-000013', 'LON-000003', 1, '2026-07-01', 5000000, 375000),
    ('INS-000014', 'LON-000003', 2, '2026-08-01', 5000000, 312500),
    ('INS-000015', 'LON-000003', 3, '2026-09-01', 5000000, 250000),
    ('INS-000016', 'LON-000003', 4, '2026-10-01', 5000000, 187500),
    ('INS-000017', 'LON-000003', 5, '2026-11-01', 5000000, 125000),
    ('INS-000018', 'LON-000003', 6, '2026-12-01', 5000000, 62500),
    ('INS-000019', 'LON-000004', 1, '2026-07-01', 2000000, 90000),
    ('INS-000020', 'LON-000004', 2, '2026-08-01', 2000000, 75000),
    ('INS-000021', 'LON-000004', 3, '2026-09-01', 2000000, 60000),
    ('INS-000022', 'LON-000004', 4, '2026-10-01', 2000000, 45000),
    ('INS-000023', 'LON-000004', 5, '2026-11-01', 2000000, 30000),
    ('INS-000024', 'LON-000004', 6, '2026-12-01', 2000000, 15000),
    ('INS-000025', 'LON-000005', 1, '2026-11-01', 6000000, 300000),
    ('INS-000026', 'LON-000005', 2, '2026-12-01', 6000000, 250000),
    ('INS-000027', 'LON-000005', 3, '2027-01-01', 6000000, 200000),
    ('INS-000028', 'LON-000005', 4, '2027-02-01', 6000000, 150000),
    ('INS-000029', 'LON-000005', 5, '2027-03-01', 6000000, 100000),
    ('INS-000030', 'LON-000005', 6, '2027-04-01', 6000000, 50000),
    ('INS-000031', 'LON-000006', 1, '2026-08-01', 3500000, 210000),
    ('INS-000032', 'LON-000006', 2, '2026-09-01', 3500000, 175000),
    ('INS-000033', 'LON-000006', 3, '2026-10-01', 3500000, 140000),
    ('INS-000034', 'LON-000006', 4, '2026-11-01', 3500000, 105000),
    ('INS-000035', 'LON-000006', 5, '2026-12-01', 3500000, 70000),
    ('INS-000036', 'LON-000006', 6, '2027-01-01', 3500000, 35000);

INSERT INTO Payment
    (payment_id, loan_id, received_at, amount_minor, currency_code,
     payment_method, external_reference, payment_status, reversed_at, created_at)
VALUES
    ('PAY-000001', 'LON-000001', '2026-07-05T10:00:00Z', 4240000, 'INR', 'bank_transfer', 'SYN-REF-2026-0001', 'posted', NULL, '2026-07-05T10:00:00Z'),
    ('PAY-000002', 'LON-000001', '2026-08-15T11:00:00Z', 2000000, 'INR', 'mobile_wallet', 'SYN-REF-2026-0002', 'posted', NULL, '2026-08-15T11:00:00Z'),
    ('PAY-000003', 'LON-000002', '2026-07-03T09:30:00Z', 3180000, 'INR', 'bank_transfer', 'SYN-REF-2026-0003', 'posted', NULL, '2026-07-03T09:30:00Z'),
    ('PAY-000004', 'LON-000002', '2026-08-08T14:00:00Z', 2200000, 'INR', 'debit_card', 'SYN-REF-2026-0004', 'posted', NULL, '2026-08-08T14:00:00Z'),
    ('PAY-000005', 'LON-000002', '2026-10-15T11:00:00Z', 950000, 'INR', 'bank_transfer', 'SYN-REF-2026-0005', 'posted', NULL, '2026-10-15T11:00:00Z'),
    ('PAY-000006', 'LON-000003', '2026-09-10T10:30:00Z', 5250000, 'INR', 'direct_debit', 'SYN-REF-2026-0006', 'posted', NULL, '2026-09-10T10:30:00Z'),
    ('PAY-000007', 'LON-000003', '2026-10-12T12:00:00Z', 1000000, 'INR', 'mobile_wallet', 'SYN-REF-2026-0007', 'posted', NULL, '2026-10-12T12:00:00Z'),
    ('PAY-000008', 'LON-000004', '2026-07-02T09:00:00Z', 2090000, 'INR', 'bank_transfer', 'SYN-REF-2026-0008', 'posted', NULL, '2026-07-02T09:00:00Z'),
    ('PAY-000009', 'LON-000004', '2026-08-02T09:00:00Z', 2075000, 'INR', 'bank_transfer', 'SYN-REF-2026-0009', 'posted', NULL, '2026-08-02T09:00:00Z'),
    ('PAY-000010', 'LON-000004', '2026-09-02T09:00:00Z', 2060000, 'INR', 'bank_transfer', 'SYN-REF-2026-0010', 'posted', NULL, '2026-09-02T09:00:00Z'),
    ('PAY-000011', 'LON-000006', '2026-08-03T10:00:00Z', 3710000, 'INR', 'bank_transfer', 'SYN-REF-2026-0011', 'posted', NULL, '2026-08-03T10:00:00Z'),
    ('PAY-000012', 'LON-000006', '2026-09-03T10:00:00Z', 3675000, 'INR', 'debit_card', 'SYN-REF-2026-0012', 'posted', NULL, '2026-09-03T10:00:00Z'),
    ('PAY-000013', 'LON-000006', '2026-10-12T10:00:00Z', 1000000, 'INR', 'mobile_wallet', 'SYN-REF-2026-0013', 'posted', NULL, '2026-10-12T10:00:00Z');

INSERT INTO PaymentAllocation
    (allocation_id, payment_id, installment_id, allocated_principal_minor,
     allocated_interest_minor, allocation_status, allocated_at, reversed_at)
VALUES
    ('ALL-000001', 'PAY-000001', 'INS-000001', 4000000, 240000, 'active', '2026-07-05T10:05:00Z', NULL),
    ('ALL-000002', 'PAY-000002', 'INS-000002', 1800000, 200000, 'active', '2026-08-15T11:05:00Z', NULL),
    ('ALL-000003', 'PAY-000003', 'INS-000007', 3000000, 180000, 'active', '2026-07-03T09:35:00Z', NULL),
    ('ALL-000004', 'PAY-000004', 'INS-000008', 2050000, 150000, 'active', '2026-08-08T14:05:00Z', NULL),
    ('ALL-000005', 'PAY-000005', 'INS-000008', 950000, 0, 'active', '2026-10-15T11:05:00Z', NULL),
    ('ALL-000006', 'PAY-000006', 'INS-000015', 5000000, 250000, 'active', '2026-09-10T10:35:00Z', NULL),
    ('ALL-000007', 'PAY-000007', 'INS-000013', 900000, 100000, 'active', '2026-10-12T12:05:00Z', NULL),
    ('ALL-000008', 'PAY-000008', 'INS-000019', 2000000, 90000, 'active', '2026-07-02T09:05:00Z', NULL),
    ('ALL-000009', 'PAY-000009', 'INS-000020', 2000000, 75000, 'active', '2026-08-02T09:05:00Z', NULL),
    ('ALL-000010', 'PAY-000010', 'INS-000021', 2000000, 60000, 'active', '2026-09-02T09:05:00Z', NULL),
    ('ALL-000011', 'PAY-000011', 'INS-000031', 3500000, 210000, 'active', '2026-08-03T10:05:00Z', NULL),
    ('ALL-000012', 'PAY-000012', 'INS-000032', 3500000, 175000, 'active', '2026-09-03T10:05:00Z', NULL),
    ('ALL-000013', 'PAY-000013', 'INS-000033', 900000, 100000, 'active', '2026-10-12T10:05:00Z', NULL);

INSERT INTO CollectionCase
    (case_id, loan_id, opened_at, case_status, priority, case_source, closed_at)
VALUES
    ('CAS-000001', 'LON-000001', '2026-08-20T09:00:00Z', 'in_progress', 'high', 'system', NULL),
    ('CAS-000002', 'LON-000002', '2026-09-10T09:00:00Z', 'in_progress', 'medium', 'system', NULL),
    ('CAS-000003', 'LON-000003', '2026-07-10T09:00:00Z', 'open', 'high', 'system', NULL),
    ('CAS-000004', 'LON-000004', '2026-10-10T09:00:00Z', 'open', 'low', 'system', NULL),
    ('CAS-000005', 'LON-000006', '2026-10-10T09:00:00Z', 'in_progress', 'medium', 'system', NULL);

INSERT INTO ContactPreference
    (customer_id, preferred_channel, contact_window, consent_status, updated_at)
VALUES
    ('CUS-000001', 'phone', 'afternoon', 'granted', '2026-03-01T09:00:00Z'),
    ('CUS-000002', 'sms', 'evening', 'granted', '2026-03-02T09:00:00Z'),
    ('CUS-000003', 'email', 'any', 'granted', '2026-03-03T09:00:00Z'),
    ('CUS-000004', 'phone', 'morning', 'granted', '2026-03-04T09:00:00Z'),
    ('CUS-000005', 'email', 'afternoon', 'granted', '2026-03-05T09:00:00Z'),
    ('CUS-000006', 'sms', 'evening', 'granted', '2026-03-06T09:00:00Z');

INSERT INTO ContactAttempt
    (contact_attempt_id, case_id, attempted_at, channel, outcome, notes)
VALUES
    ('CNT-000001', 'CAS-000001', '2026-10-18T14:00:00Z', 'phone', 'connected', 'Discussed a possible payment date.'),
    ('CNT-000002', 'CAS-000002', '2026-10-10T18:00:00Z', 'sms', 'message_sent', 'Payment reminder sent; customer replied with a date.'),
    ('CNT-000003', 'CAS-000003', '2026-10-11T10:00:00Z', 'email', 'message_sent', 'Follow-up reminder sent.'),
    ('CNT-000004', 'CAS-000004', '2026-10-15T09:30:00Z', 'phone', 'no_answer', 'No answer; follow-up scheduled.'),
    ('CNT-000005', 'CAS-000005', '2026-10-16T18:00:00Z', 'sms', 'message_sent', 'Reminder sent through the preferred channel.');

INSERT INTO PromiseToPay
    (promise_id, case_id, promised_at, due_date, amount_minor, currency_code,
     promise_status, resolved_at, created_at)
VALUES
    ('PTP-000001', 'CAS-000001', '2026-10-20T14:00:00Z', '2026-10-25', 5000000, 'INR', 'pending', NULL, '2026-10-20T14:00:00Z'),
    ('PTP-000002', 'CAS-000002', '2026-10-10T18:00:00Z', '2026-10-15', 950000, 'INR', 'kept', '2026-10-15T12:00:00Z', '2026-10-10T18:00:00Z'),
    ('PTP-000003', 'CAS-000003', '2026-08-20T11:00:00Z', '2026-10-05', 8000000, 'INR', 'broken', '2026-10-06T09:00:00Z', '2026-08-20T11:00:00Z'),
    ('PTP-000004', 'CAS-000004', '2026-10-15T09:30:00Z', '2026-10-26', 2045000, 'INR', 'pending', NULL, '2026-10-15T09:30:00Z'),
    ('PTP-000005', 'CAS-000005', '2026-10-16T18:00:00Z', '2026-10-27', 2640000, 'INR', 'pending', NULL, '2026-10-16T18:00:00Z');

INSERT INTO DelinquencySnapshot
    (snapshot_id, loan_id, snapshot_date, days_past_due, overdue_amount_minor,
     outstanding_principal_minor, delinquency_bucket)
VALUES
    ('SNP-000001', 'LON-000001', '2026-10-22', 82, 10480000, 18200000, '61-90'),
    ('SNP-000002', 'LON-000002', '2026-10-22', 51, 6210000, 12000000, '31-60'),
    ('SNP-000003', 'LON-000003', '2026-10-22', 113, 14875000, 24100000, '91+'),
    ('SNP-000004', 'LON-000004', '2026-10-22', 21, 2045000, 6000000, '1-30'),
    ('SNP-000005', 'LON-000005', '2026-10-22', 0, 0, 36000000, 'current'),
    ('SNP-000006', 'LON-000006', '2026-10-22', 21, 2640000, 13100000, '1-30');

COMMIT;
