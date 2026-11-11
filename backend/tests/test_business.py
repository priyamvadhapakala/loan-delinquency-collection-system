import shutil
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
    database = tmp_path / "business_test.db"
    shutil.copyfile(PROJECT_ROOT / "database" / "loan_delinquency.db", database)
    app = create_app({"TESTING": True, "DATABASE": str(database)})
    with app.test_client() as test_client:
        yield test_client


def _insert_overdue_loan(client, loan_id="LON-000007"):
    with client.application.app_context():
        db = get_db()
        db.execute(
            """
            INSERT INTO Loan (
                loan_id, customer_id, loan_reference, principal_amount_minor,
                currency_code, annual_interest_rate_bps, term_months,
                disbursement_date, first_due_date
            ) VALUES (?, 'CUS-000006', ?, 100000, 'INR', 0, 1, '2026-01-01', '2026-01-31')
            """,
            (loan_id, f"TEST-{loan_id}"),
        )
        installment_id = f"INS-{int(loan_id[-6:]) + 30:06d}"
        db.execute(
            """
            INSERT INTO Installment (
                installment_id, loan_id, installment_number, due_date,
                scheduled_principal_minor, scheduled_interest_minor
            ) VALUES (?, ?, 1, '2026-01-31', 90000, 10000)
            """,
            (installment_id, loan_id),
        )
        db.commit()
        return installment_id


def test_delinquency_balance_matches_independent_database_calculation(client):
    response = client.get("/api/delinquency?as_of=2026-10-22")
    assert response.status_code == 200
    results = {item["loan_id"]: item for item in response.get_json()["data"]}

    with client.application.app_context():
        db = get_db()
        for loan_id, result in results.items():
            expected = db.execute(
                """
                SELECT
                    SUM(i.scheduled_principal_minor - COALESCE(a.paid_principal, 0))
                        AS principal,
                    SUM(i.scheduled_interest_minor - COALESCE(a.paid_interest, 0))
                        AS interest,
                    SUM(CASE WHEN i.due_date < '2026-10-22' THEN
                        i.scheduled_principal_minor + i.scheduled_interest_minor
                        - COALESCE(a.paid_principal, 0) - COALESCE(a.paid_interest, 0)
                        ELSE 0 END) AS arrears
                FROM Installment i
                LEFT JOIN (
                    SELECT pa.installment_id,
                        SUM(pa.allocated_principal_minor) AS paid_principal,
                        SUM(pa.allocated_interest_minor) AS paid_interest
                    FROM PaymentAllocation pa
                    JOIN Payment p ON p.payment_id=pa.payment_id
                    WHERE pa.allocation_status='active'
                      AND p.payment_status='posted'
                      AND substr(p.received_at, 1, 10) <= '2026-10-22'
                    GROUP BY pa.installment_id
                ) a ON a.installment_id=i.installment_id
                WHERE i.loan_id=?
                """,
                (loan_id,),
            ).fetchone()
            assert result["outstanding_principal_minor"] == expected["principal"]
            assert result["outstanding_interest_minor"] == expected["interest"]
            assert result["arrears_amount_minor"] == expected["arrears"]
        snapshots = db.execute(
            "SELECT loan_id, days_past_due, overdue_amount_minor, "
            "outstanding_principal_minor, delinquency_bucket "
            "FROM DelinquencySnapshot WHERE snapshot_date='2026-10-22'"
        ).fetchall()
    for snapshot in snapshots:
        result = results[snapshot["loan_id"]]
        assert result["days_past_due"] == snapshot["days_past_due"]
        assert result["arrears_amount_minor"] == snapshot["overdue_amount_minor"]
        assert result["outstanding_principal_minor"] == snapshot["outstanding_principal_minor"]
        assert result["delinquency_bucket"] == snapshot["delinquency_bucket"]


def test_delinquency_report_summarizes_server_calculated_balances(client):
    balances = client.get("/api/delinquency?as_of=2026-10-22").get_json()["data"]
    response = client.get("/api/reports/delinquency?as_of=2026-10-22")
    assert response.status_code == 200
    report = response.get_json()["data"]
    overdue = [item for item in balances if item["days_past_due"] > 0]
    assert report["as_of"] == "2026-10-22"
    assert report["loan_count"] == len(balances)
    assert report["overdue_loan_count"] == len(overdue)
    assert report["total_arrears_by_currency"] == [{
        "currency_code": "INR",
        "amount_minor": sum(item["arrears_amount_minor"] for item in overdue),
    }]
    for category in report["categories"]:
        matching = [item for item in overdue if item["delinquency_bucket"] == category["bucket"]]
        assert category["loan_count"] == len(matching)
        assert category["arrears_by_currency"] == (
            [{"currency_code": "INR", "amount_minor": sum(
                item["arrears_amount_minor"] for item in matching
            )}] if matching else []
        )


def test_payment_partial_allocation_and_collection_case_priority(client):
    installment_id = _insert_overdue_loan(client)
    case = client.post("/api/collection-cases", json={
        "loan_id": "LON-000007",
        "case_source": "manual",
    })
    assert case.status_code == 201
    assert case.get_json()["data"]["priority"] == "high"
    assert case.get_json()["data"]["days_past_due"] > 90
    assert case.get_json()["data"]["arrears_amount_minor"] == 100000

    repeated = client.post("/api/collection-cases", json={"loan_id": "LON-000007"})
    assert repeated.status_code == 201
    assert repeated.get_json()["data"]["case_id"] == case.get_json()["data"]["case_id"]

    payment = client.post("/api/payments", json={
        "loan_id": "LON-000007",
        "amount_minor": 25000,
        "payment_method": "cash",
        "external_reference": "BUSINESS-PARTIAL-001",
        "received_at": "2026-11-11T10:00:00Z",
    })
    assert payment.status_code == 201
    result = payment.get_json()["data"]
    assert result["amount_allocated_minor"] == 25000
    assert result["amount_unallocated_minor"] == 0
    assert result["allocations"][0]["installment_id"] == installment_id
    assert result["allocations"][0]["allocated_interest_minor"] == 10000
    assert result["allocations"][0]["allocated_principal_minor"] == 15000

    updated = client.get("/api/loans/LON-000007/balance?as_of=2026-11-11")
    assert updated.get_json()["data"]["arrears_amount_minor"] == 75000
    assert updated.get_json()["data"]["days_past_due"] == 284

    full_payment = client.post("/api/payments", json={
        "loan_id": "LON-000007",
        "amount_minor": 75000,
        "payment_method": "cash",
        "external_reference": "BUSINESS-FULL-001",
        "received_at": "2026-11-11T11:00:00Z",
    })
    assert full_payment.status_code == 201
    balance = client.get("/api/loans/LON-000007/balance?as_of=2026-11-11")
    assert balance.get_json()["data"]["outstanding_balance_minor"] == 0
    assert balance.get_json()["data"]["delinquency_bucket"] == "current"


def test_promise_amount_must_not_exceed_arrears(client):
    _insert_overdue_loan(client)
    case = client.post("/api/collection-cases", json={"loan_id": "LON-000007"})
    case_id = case.get_json()["data"]["case_id"]
    invalid = client.post(f"/api/collection-cases/{case_id}/promises", json={
        "promised_at": "2026-11-11T12:00:00Z",
        "due_date": "2026-11-20",
        "amount_minor": 100001,
    })
    assert invalid.status_code == 400
    valid = client.post(f"/api/collection-cases/{case_id}/promises", json={
        "promised_at": "2026-11-11T12:00:00Z",
        "due_date": "2026-11-20",
        "amount_minor": 100000,
    })
    assert valid.status_code == 201
    assert valid.get_json()["data"]["amount_minor"] == 100000


def test_promises_are_evaluated_kept_or_broken_from_posted_payments(client):
    _insert_overdue_loan(client)
    case = client.post("/api/collection-cases", json={"loan_id": "LON-000007"})
    case_id = case.get_json()["data"]["case_id"]
    kept = client.post(f"/api/collection-cases/{case_id}/promises", json={
        "promised_at": "2026-02-01T10:00:00Z",
        "due_date": "2026-02-10",
        "amount_minor": 10000,
    })
    broken = client.post(f"/api/collection-cases/{case_id}/promises", json={
        "promised_at": "2026-02-01T11:00:00Z",
        "due_date": "2026-02-10",
        "amount_minor": 10000,
    })
    assert kept.status_code == 201
    assert broken.status_code == 201
    payment = client.post("/api/payments", json={
        "loan_id": "LON-000007",
        "amount_minor": 10000,
        "payment_method": "cash",
        "external_reference": "BUSINESS-PROMISE-FULFILLMENT",
        "received_at": "2026-02-01T10:30:00Z",
    })
    assert payment.status_code == 201
    premature_failure = client.patch(
        f"/api/promises/{kept.get_json()['data']['promise_id']}",
        json={"promise_status": "broken"},
    )
    assert premature_failure.status_code == 409
    result = client.post("/api/promises/evaluate", json={"as_of": "2026-02-11"})
    assert result.status_code == 200
    statuses = {item["promise_id"]: item["promise_status"] for item in result.get_json()["data"]["evaluated"]}
    assert statuses[kept.get_json()["data"]["promise_id"]] == "kept"
    assert statuses[broken.get_json()["data"]["promise_id"]] == "broken"
