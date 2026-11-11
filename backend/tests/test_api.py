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
    source_db = PROJECT_ROOT / "database" / "loan_delinquency.db"
    test_db = tmp_path / "loan_delinquency_test.db"
    shutil.copyfile(source_db, test_db)
    app = create_app({
        "TESTING": True,
        "DATABASE": str(test_db),
    })
    with app.test_client() as test_client:
        yield test_client


def test_app_startup_and_database_connection(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}
    with client.application.app_context():
        assert get_db().execute("PRAGMA foreign_keys").fetchone()[0] == 1


def test_local_frontend_cors_allows_only_configured_origin(client):
    allowed_origin = "http://127.0.0.1:5500"
    response = client.get("/api/health", headers={"Origin": allowed_origin})
    assert response.headers["Access-Control-Allow-Origin"] == allowed_origin
    assert "Origin" in response.headers["Vary"]

    preflight = client.options(
        "/api/payments",
        headers={
            "Origin": allowed_origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type",
        },
    )
    assert preflight.status_code == 200
    assert preflight.headers["Access-Control-Allow-Origin"] == allowed_origin
    assert "POST" in preflight.headers["Access-Control-Allow-Methods"]
    assert "Content-Type" in preflight.headers["Access-Control-Allow-Headers"]

    for origin in ("http://localhost:5500", "http://127.0.0.1:5501", "https://example.test"):
        denied = client.get("/api/health", headers={"Origin": origin})
        assert "Access-Control-Allow-Origin" not in denied.headers


def test_customer_list_detail_create_and_update(client):
    response = client.get("/api/customers")
    assert response.status_code == 200
    assert len(response.get_json()["data"]) == 6

    response = client.get("/api/customers/CUS-000001")
    assert response.status_code == 200
    assert response.get_json()["data"]["email"] == "vikram.patel.1@example.test"

    response = client.post("/api/customers", json={
        "first_name": "Asha",
        "last_name": "Rao",
        "email": "asha.rao@example.test",
        "phone": "+910000020001",
    })
    assert response.status_code == 201
    customer_id = response.get_json()["data"]["customer_id"]
    assert customer_id == "CUS-000007"
    assert response.headers["Location"] == f"/api/customers/{customer_id}"

    response = client.patch(
        f"/api/customers/{customer_id}",
        json={"customer_status": "inactive", "phone": None},
    )
    assert response.status_code == 200
    assert response.get_json()["data"]["customer_status"] == "inactive"
    assert response.get_json()["data"]["phone"] is None


@pytest.mark.parametrize("body", [
    {"first_name": "", "last_name": "User", "email": "user@example.test"},
    {"first_name": "Test", "last_name": "User", "email": "not-an-email"},
    {"first_name": "Test", "last_name": "User", "email": "user@example.test", "extra": 1},
    {"first_name": "Test", "last_name": "User", "email": "vikram.patel.1@example.test"},
])
def test_customer_create_validation_and_duplicate_conflict(client, body):
    response = client.post("/api/customers", json=body)
    assert response.status_code in {400, 409}
    assert "error" in response.get_json()


def test_customer_missing_and_invalid_update(client):
    response = client.get("/api/customers/CUS-999999")
    assert response.status_code == 404
    response = client.patch("/api/customers/CUS-000001", json={})
    assert response.status_code == 400
    response = client.patch("/api/customers/CUS-999999", json={"first_name": "X"})
    assert response.status_code == 404


def test_loan_list_detail_customer_filter_and_missing(client):
    response = client.get("/api/loans")
    assert response.status_code == 200
    assert len(response.get_json()["data"]) == 6
    response = client.get("/api/loans/LON-000001")
    assert response.status_code == 200
    assert response.get_json()["data"]["customer_id"] == "CUS-000001"
    response = client.get("/api/customers/CUS-000001/loans")
    assert response.status_code == 200
    assert len(response.get_json()["data"]) == 1
    response = client.get("/api/loans?customer_id=CUS-999999")
    assert response.status_code == 404
    response = client.get("/api/loans/LON-999999")
    assert response.status_code == 404


def test_installment_schedule_detail_and_missing(client):
    response = client.get("/api/installments")
    assert response.status_code == 200
    assert len(response.get_json()["data"]) == 36
    response = client.get("/api/loans/LON-000001/installments")
    assert response.status_code == 200
    assert len(response.get_json()["data"]) == 6
    response = client.get("/api/installments/INS-000001")
    assert response.status_code == 200
    assert response.get_json()["data"]["paid_principal_minor"] == 4000000
    response = client.get("/api/installments/INS-999999")
    assert response.status_code == 404
    response = client.get("/api/loans/LON-999999/installments")
    assert response.status_code == 404


def test_payment_recording_history_and_allocations(client):
    response = client.post("/api/payments", json={
        "loan_id": "LON-000001",
        "amount_minor": 100000,
        "payment_method": "bank_transfer",
        "external_reference": "API-TEST-REF-001",
        "received_at": "2026-10-22T12:00:00Z",
    })
    assert response.status_code == 201
    result = response.get_json()["data"]
    assert result["payment_id"] == "PAY-000014"
    assert result["amount_allocated_minor"] == 100000
    assert result["amount_unallocated_minor"] == 0
    assert sum(
        item["allocated_principal_minor"] + item["allocated_interest_minor"]
        for item in result["allocations"]
    ) == 100000

    response = client.get("/api/payments?loan_id=LON-000001")
    assert response.status_code == 200
    assert len(response.get_json()["data"]) == 3
    response = client.get("/api/payments?loan_id=LON-999999")
    assert response.status_code == 404


@pytest.mark.parametrize("body", [
    {
        "loan_id": "LON-000001",
        "amount_minor": 0,
        "payment_method": "cash",
        "external_reference": "INVALID-001",
    },
    {
        "loan_id": "LON-000001",
        "amount_minor": 100,
        "payment_method": ["cash"],
        "external_reference": "INVALID-002",
    },
    {
        "loan_id": "LON-000001",
        "amount_minor": 100,
        "payment_method": "cash",
        "external_reference": "INVALID-003",
        "received_at": "not-a-date",
    },
])
def test_payment_validation(client, body):
    response = client.post("/api/payments", json=body)
    assert response.status_code == 400
    assert "error" in response.get_json()


def test_payment_missing_loan_currency_mismatch_and_duplicate_reference(client):
    base = {
        "amount_minor": 1000,
        "payment_method": "cash",
        "external_reference": "API-TEST-REF-002",
    }
    response = client.post("/api/payments", json={**base, "loan_id": "LON-999999"})
    assert response.status_code == 404
    response = client.post(
        "/api/payments",
        json={**base, "loan_id": "LON-000001", "currency_code": "USD"},
    )
    assert response.status_code == 400
    response = client.post(
        "/api/payments",
        json={
            "loan_id": "LON-000001",
            "amount_minor": 1000,
            "payment_method": "cash",
            "external_reference": "SYN-REF-2026-0001",
        },
    )
    assert response.status_code == 409


def test_collection_case_list_detail_update_and_missing(client):
    response = client.get("/api/collection-cases")
    assert response.status_code == 200
    assert len(response.get_json()["data"]) == 5
    response = client.get("/api/collection-cases/CAS-000001")
    assert response.status_code == 200
    assert len(response.get_json()["data"]["contact_attempts"]) == 1
    assert len(response.get_json()["data"]["promises_to_pay"]) == 1

    response = client.patch(
        "/api/collection-cases/CAS-000001",
        json={"case_status": "resolved"},
    )
    assert response.status_code == 200
    assert response.get_json()["data"]["closed_at"] is not None
    response = client.patch(
        "/api/collection-cases/CAS-999999",
        json={"case_status": "closed"},
    )
    assert response.status_code == 404
    response = client.patch(
        "/api/collection-cases/CAS-000002",
        json={"case_status": ["invalid"]},
    )
    assert response.status_code == 400


def test_json_errors_and_missing_route(client):
    response = client.post("/api/customers", data="not json", content_type="application/json")
    assert response.status_code == 400
    assert response.is_json
    response = client.get("/api/no-such-resource")
    assert response.status_code == 404
    assert response.is_json


def test_database_connection_failure_is_json_503(tmp_path):
    app = create_app({
        "TESTING": True,
        "DATABASE": str(tmp_path),
    })
    with app.test_client() as client:
        response = client.get("/api/health")
    assert response.status_code == 503
    assert response.get_json()["error"]["code"] == "database_error"
