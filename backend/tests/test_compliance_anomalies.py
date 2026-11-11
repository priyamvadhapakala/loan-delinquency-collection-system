import shutil
import sqlite3
import sys
from pathlib import Path

import pytest


BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))

from app import create_app
from app.utils.database import get_db


@pytest.fixture
def client(tmp_path):
    database = tmp_path / "compliance_test.db"
    shutil.copyfile(PROJECT_ROOT / "database" / "loan_delinquency.db", database)
    app = create_app({"TESTING": True, "DATABASE": str(database)})
    with app.test_client() as test_client:
        yield test_client


def _preference(client, **overrides):
    payload = {
        "preferred_channel": "email",
        "contact_window": "any",
        "consent_status": "granted",
        "timezone": "UTC",
        "allowed_contact_start": "09:00",
        "allowed_contact_end": "18:00",
        "weekend_contact_allowed": False,
        "holiday_contact_allowed": False,
        "allowed_channels": ["email"],
    }
    payload.update(overrides)
    return client.put("/api/customers/CUS-000001/contact-preference", json=payload)


def _attempt(client, attempted_at="2026-11-10T10:00:00Z", channel="email"):
    return client.post("/api/collection-cases/CAS-000001/contact-attempts", json={
        "attempted_at": attempted_at,
        "channel": channel,
        "outcome": "message_sent",
        "notes": "Synthetic compliance test.",
    })


def test_contact_requires_explicit_timezone_hours_and_channel_permission(client):
    missing = _attempt(client)
    assert missing.status_code == 403
    assert "explicitly configured" in missing.get_json()["error"]["message"]

    configured = _preference(client)
    assert configured.status_code == 200
    valid = _attempt(client)
    assert valid.status_code == 201

    outside = _attempt(client, attempted_at="2026-11-10T19:00:00Z")
    assert outside.status_code == 403
    channel = _attempt(client, channel="phone")
    assert channel.status_code == 403

    weekend = _attempt(client, attempted_at="2026-11-14T10:00:00Z")
    assert weekend.status_code == 403
    assert "Weekend" in weekend.get_json()["error"]["message"]

    holiday = client.post("/api/contact-holidays/2026-11-10", json={"label": "Synthetic test holiday"})
    assert holiday.status_code == 201
    holiday_attempt = _attempt(client)
    assert holiday_attempt.status_code == 403
    assert "Holiday" in holiday_attempt.get_json()["error"]["message"]

    audits = client.get(
        "/api/audit-events?entity_type=collection_case&entity_id=CAS-000001"
    ).get_json()["data"]
    attempts = [item for item in audits if item["action"] == "contact_attempt"]
    assert any(item["outcome"] == "permitted" for item in attempts)
    assert sum(item["outcome"] == "denied" for item in attempts) >= 4
    assert len({item["audit_id"] for item in audits}) == len(audits)


def test_customer_mutations_are_audited_and_audit_history_is_immutable(client):
    created = client.post("/api/customers", json={
        "first_name": "Synthetic",
        "last_name": "Audit",
        "email": "synthetic.audit@example.test",
        "phone": "+15555550101",
    })
    assert created.status_code == 201
    customer_id = created.get_json()["data"]["customer_id"]
    updated = client.patch(
        f"/api/customers/{customer_id}",
        json={"customer_status": "inactive"},
    )
    assert updated.status_code == 200

    events = client.get(
        f"/api/audit-events?entity_type=customer&entity_id={customer_id}"
    ).get_json()["data"]
    assert [event["action"] for event in events] == [
        "customer_created",
        "customer_updated",
    ]
    assert all(
        "synthetic.audit@example.test" not in str(event["details"])
        for event in events
    )

    with client.application.app_context():
        db = get_db()
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            db.execute(
                "UPDATE ComplianceAuditEvent SET reason='changed' WHERE audit_id=?",
                (events[0]["audit_id"],),
            )
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            db.execute(
                "DELETE FROM ComplianceAuditEvent WHERE audit_id=?",
                (events[0]["audit_id"],),
            )


def test_disputed_debt_pauses_contact_and_cannot_be_confirmed(client):
    assert _preference(client).status_code == 200
    disputed = client.put(
        "/api/loans/LON-000001/account-status",
        json={"dispute_status": "disputed"},
    )
    assert disputed.status_code == 200
    attempt = _attempt(client)
    assert attempt.status_code == 403
    assert "disputed" in attempt.get_json()["error"]["message"].lower()

    confirmation = client.put(
        "/api/loans/LON-000001/account-status",
        json={"debt_status": "confirmed"},
    )
    assert confirmation.status_code == 409
    assert client.get("/api/loans/LON-000001/account-status").get_json()["data"][
        "dispute_status"
    ] == "disputed"

    hardship = client.put(
        "/api/loans/LON-000001/account-status",
        json={"hardship_status": "active"},
    )
    assert hardship.status_code == 200
    assert hardship.get_json()["data"]["hardship_status"] == "active"


def test_database_rejects_allocation_to_installment_of_another_loan(client):
    with client.application.app_context():
        db = get_db()
        db.execute(
            """
            INSERT INTO Payment (
                payment_id, loan_id, received_at, amount_minor, currency_code,
                payment_method, external_reference, payment_status
            ) VALUES (
                'PAY-000014', 'LON-000001', '2026-11-11T10:00:00Z', 1,
                'INR', 'cash', 'WRONG-LOAN-TEST', 'posted'
            )
            """
        )
        db.execute(
            """
            INSERT INTO Loan (
                loan_id, customer_id, loan_reference, principal_amount_minor,
                currency_code, annual_interest_rate_bps, term_months,
                disbursement_date, first_due_date
            ) VALUES (
                'LON-000007', 'CUS-000006', 'WRONG-LOAN-TARGET',
                100000, 'INR', 0, 1, '2026-01-01', '2026-01-31'
            )
            """
        )
        db.execute(
            """
            INSERT INTO Installment (
                installment_id, loan_id, installment_number, due_date,
                scheduled_principal_minor, scheduled_interest_minor
            ) VALUES (
                'INS-000037', 'LON-000007', 1, '2026-01-31', 90000, 10000
            )
            """
        )
        with pytest.raises(sqlite3.IntegrityError, match="same loan"):
            db.execute(
                """
                INSERT INTO PaymentAllocation (
                    allocation_id, payment_id, installment_id,
                    allocated_principal_minor, allocated_interest_minor,
                    allocation_status, allocated_at
                ) VALUES (
                    'ALL-999999', 'PAY-000014', 'INS-000037',
                    1, 0, 'active', '2026-11-11T10:00:00Z'
                )
                """
            )
        db.rollback()


def _insert_anomaly_fixtures(client):
    with client.application.app_context():
        db = get_db()
        db.execute(
            """
            INSERT INTO Loan (
                loan_id, customer_id, loan_reference, principal_amount_minor,
                currency_code, annual_interest_rate_bps, term_months,
                disbursement_date, first_due_date
            ) VALUES (
                'LON-000007', 'CUS-000006', 'ANOMALY-PAID-LOAN',
                100000, 'INR', 0, 1, '2026-01-01', '2026-01-31'
            )
            """
        )
        db.execute(
            """
            INSERT INTO Installment (
                installment_id, loan_id, installment_number, due_date,
                scheduled_principal_minor, scheduled_interest_minor
            ) VALUES ('INS-000037', 'LON-000007', 1, '2026-01-31', 90000, 10000)
            """
        )
        db.execute(
            """
            INSERT INTO Payment (
                payment_id, loan_id, received_at, amount_minor, currency_code,
                payment_method, external_reference, payment_status
            ) VALUES (
                'PAY-000014', 'LON-000007', '2026-02-01T10:00:00Z', 100000,
                'INR', 'cash', 'ANOMALY-PAID-REF', 'posted'
            )
            """
        )
        db.execute(
            """
            INSERT INTO PaymentAllocation (
                allocation_id, payment_id, installment_id,
                allocated_principal_minor, allocated_interest_minor,
                allocation_status, allocated_at
            ) VALUES (
                'ALL-000014', 'PAY-000014', 'INS-000037',
                90000, 10000, 'active', '2026-02-01T10:00:00Z'
            )
            """
        )
        db.execute(
            """
            INSERT INTO CollectionCase (
                case_id, loan_id, opened_at, case_status, priority, case_source
            ) VALUES (
                'CAS-000006', 'LON-000007', '2026-02-02T10:00:00Z',
                'open', 'high', 'manual'
            )
            """
        )
        db.execute(
            """
            INSERT INTO Payment (
                payment_id, loan_id, received_at, amount_minor, currency_code,
                payment_method, external_reference, payment_status
            ) VALUES (
                'PAY-000015', 'LON-000001', '2026-07-05T10:00:00Z', 1000,
                'INR', 'cash', 'ANOMALY-WRONG-ALLOCATION', 'posted'
            )
            """
        )
        db.execute(
            """
            INSERT INTO PaymentAllocation (
                allocation_id, payment_id, installment_id,
                allocated_principal_minor, allocated_interest_minor,
                allocation_status, allocated_at
            ) VALUES (
                'ALL-000015', 'PAY-000015', 'INS-000002',
                1000, 0, 'active', '2026-07-05T10:00:00Z'
            )
            """
        )
        db.execute(
            """
            INSERT INTO PromiseToPay (
                promise_id, case_id, promised_at, due_date, amount_minor,
                currency_code, promise_status
            ) VALUES (
                'PTP-000006', 'CAS-000001', '2026-10-22T10:00:00Z',
                '2026-11-20', 999999999, 'INR', 'pending'
            )
            """
        )
        db.execute(
            """
            INSERT INTO LoanAccountStatus (
                loan_id, dispute_status, hardship_status, debt_status, updated_at
            ) VALUES (
                'LON-000002', 'disputed', 'none', 'confirmed',
                '2026-11-11T10:00:00Z'
            )
            """
        )
        db.execute(
            """
            INSERT INTO AnomalyGroundTruth (
                label_id, anomaly_type, record_reference, is_anomaly, label_source, labeled_at
            ) VALUES (
                'GT-SYNTHETIC-001', 'paid_account_in_collection',
                'CAS-000006', 1, 'synthetic_test_fixture', '2026-11-11T10:00:00Z'
            )
            """
        )
        db.commit()


def test_all_five_anomaly_types_repeat_without_duplicates_and_ignore_labels(client):
    _insert_anomaly_fixtures(client)
    with client.application.app_context():
        db = get_db()
        history_before = {
            table: db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("Payment", "PaymentAllocation", "ContactAttempt", "PromiseToPay")
        }
    first = client.post("/api/anomalies/detect", json={"as_of": "2026-11-11"})
    assert first.status_code == 200
    records = first.get_json()["data"]
    keys = {(item["anomaly_type"], item["record_reference"]) for item in records}
    expected = {
        ("paid_account_in_collection", "CAS-000006"),
        ("contact_outside_allowed_window", "CNT-000001"),
        ("payment_wrong_installment", "ALL-000015"),
        ("promise_exceeds_arrears", "PTP-000006"),
        ("disputed_debt_confirmed", "LON-000002"),
    }
    assert expected <= keys

    with client.application.app_context():
        db = get_db()
        count_before = db.execute("SELECT COUNT(*) FROM AnomalyRecord").fetchone()[0]
        labels_before = db.execute("SELECT COUNT(*) FROM AnomalyGroundTruth").fetchone()[0]
    second = client.post("/api/anomalies/detect", json={"as_of": "2026-11-11"})
    assert second.status_code == 200
    with client.application.app_context():
        db = get_db()
        assert db.execute("SELECT COUNT(*) FROM AnomalyRecord").fetchone()[0] == count_before
        assert db.execute("SELECT COUNT(*) FROM AnomalyGroundTruth").fetchone()[0] == labels_before
        assert {
            table: db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("Payment", "PaymentAllocation", "ContactAttempt", "PromiseToPay")
        } == history_before
        assert db.execute(
            "SELECT COUNT(*) FROM AnomalyRecord WHERE anomaly_type='paid_account_in_collection' "
            "AND record_reference='CAS-000006' AND detection_status='active'"
        ).fetchone()[0] == 1

    report = client.get("/api/reports/anomalies?as_of=2026-11-11").get_json()["data"]
    assert report["ground_truth_used"] is False
    assert report["active_count"] >= 5
    assert report["counts_by_type"]["payment_wrong_installment"] >= 1


def test_resolved_collection_case_is_not_reopened(client):
    resolved = client.patch(
        "/api/collection-cases/CAS-000001",
        json={"case_status": "resolved"},
    )
    assert resolved.status_code == 200
    reopened = client.patch(
        "/api/collection-cases/CAS-000001",
        json={"case_status": "in_progress"},
    )
    assert reopened.status_code == 409
