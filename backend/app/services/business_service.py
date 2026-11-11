import re
import sqlite3
from datetime import date, datetime, timezone

from app.services.errors import ApiError, ConflictError, NotFoundError, validate_object
from app.services.collection_service import get_collection_case
from app.utils.database import get_db, transaction


_STATUSES = {"open", "in_progress", "resolved", "closed"}
_UTC_TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _as_of(value):
    if value is None:
        return date.today()
    if not isinstance(value, str):
        raise ApiError("as_of must be a YYYY-MM-DD date.")
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise ApiError("as_of must be a valid YYYY-MM-DD date.") from error


def _balance_rows(connection, loan_id, cutoff):
    return connection.execute(
        """
        SELECT i.installment_id, i.installment_number, i.due_date,
               i.scheduled_principal_minor, i.scheduled_interest_minor,
               COALESCE(SUM(CASE WHEN p.payment_id IS NOT NULL
                                 THEN a.allocated_principal_minor ELSE 0 END), 0)
                   AS paid_principal_minor,
               COALESCE(SUM(CASE WHEN p.payment_id IS NOT NULL
                                 THEN a.allocated_interest_minor ELSE 0 END), 0)
                   AS paid_interest_minor
        FROM Installment i
        LEFT JOIN PaymentAllocation a
            ON a.installment_id = i.installment_id
           AND a.allocation_status = 'active'
        LEFT JOIN Payment p
            ON p.payment_id = a.payment_id
           AND p.payment_status = 'posted'
           AND substr(p.received_at, 1, 10) <= ?
        WHERE i.loan_id = ?
        GROUP BY i.installment_id
        ORDER BY i.due_date, i.installment_number
        """,
        (cutoff.isoformat(), loan_id),
    ).fetchall()


def _bucket(days_past_due):
    if days_past_due == 0:
        return "current"
    if days_past_due <= 30:
        return "1-30"
    if days_past_due <= 60:
        return "31-60"
    if days_past_due <= 90:
        return "61-90"
    return "91+"


def _priority(days_past_due):
    if days_past_due >= 61:
        return "high"
    if days_past_due >= 31:
        return "medium"
    return "low"


def calculate_loan_balance(loan_id, as_of=None):
    cutoff = _as_of(as_of)
    connection = get_db()
    loan = connection.execute(
        "SELECT loan_id, currency_code FROM Loan WHERE loan_id = ?", (loan_id,)
    ).fetchone()
    if loan is None:
        raise NotFoundError("Loan was not found.")

    schedule = _balance_rows(connection, loan_id, cutoff)
    outstanding_principal = 0
    outstanding_interest = 0
    arrears = 0
    overdue_installments = []
    for row in schedule:
        remaining_principal = row["scheduled_principal_minor"] - row["paid_principal_minor"]
        remaining_interest = row["scheduled_interest_minor"] - row["paid_interest_minor"]
        outstanding_principal += remaining_principal
        outstanding_interest += remaining_interest
        if row["due_date"] < cutoff.isoformat() and remaining_principal + remaining_interest > 0:
            arrears += remaining_principal + remaining_interest
            overdue_installments.append({
                "installment_id": row["installment_id"],
                "installment_number": row["installment_number"],
                "due_date": row["due_date"],
                "remaining_principal_minor": remaining_principal,
                "remaining_interest_minor": remaining_interest,
                "outstanding_minor": remaining_principal + remaining_interest,
            })

    oldest_due = overdue_installments[0]["due_date"] if overdue_installments else None
    days_past_due = (
        (cutoff - date.fromisoformat(oldest_due)).days if oldest_due else 0
    )
    return {
        "loan_id": loan_id,
        "as_of": cutoff.isoformat(),
        "currency_code": loan["currency_code"],
        "outstanding_principal_minor": outstanding_principal,
        "outstanding_interest_minor": outstanding_interest,
        "outstanding_balance_minor": outstanding_principal + outstanding_interest,
        "arrears_amount_minor": arrears,
        "days_past_due": days_past_due,
        "delinquency_bucket": _bucket(days_past_due),
        "oldest_overdue_due_date": oldest_due,
        "overdue_installments": overdue_installments,
    }


def list_delinquency(as_of=None):
    cutoff = _as_of(as_of)
    loan_ids = [
        row["loan_id"]
        for row in get_db().execute("SELECT loan_id FROM Loan ORDER BY loan_id").fetchall()
    ]
    return [calculate_loan_balance(loan_id, cutoff.isoformat()) for loan_id in loan_ids]


def delinquency_report(as_of=None):
    cutoff = _as_of(as_of)
    balances = list_delinquency(cutoff.isoformat())
    overdue = [balance for balance in balances if balance["days_past_due"] > 0]

    def currency_totals(records):
        totals = {}
        for record in records:
            currency = record["currency_code"]
            totals[currency] = totals.get(currency, 0) + record["arrears_amount_minor"]
        return [
            {"currency_code": currency, "amount_minor": amount}
            for currency, amount in sorted(totals.items())
        ]

    categories = []
    for bucket in ("1-30", "31-60", "61-90", "91+"):
        matching = [item for item in overdue if item["delinquency_bucket"] == bucket]
        categories.append({
            "bucket": bucket,
            "loan_count": len(matching),
            "arrears_by_currency": currency_totals(matching),
        })
    return {
        "as_of": cutoff.isoformat(),
        "loan_count": len(balances),
        "overdue_loan_count": len(overdue),
        "total_arrears_by_currency": currency_totals(overdue),
        "categories": categories,
    }


def create_collection_case(payload):
    validate_object(payload, {"loan_id", "case_source"}, ("loan_id",))
    loan_id = payload["loan_id"]
    source = payload.get("case_source", "manual")
    if not isinstance(loan_id, str) or not loan_id.strip():
        raise ApiError("loan_id must be a non-empty string.")
    if source not in {"system", "manual", "import"}:
        raise ApiError("case_source must be system, manual, or import.")
    balance = calculate_loan_balance(loan_id)
    if balance["arrears_amount_minor"] <= 0:
        raise ConflictError("A collection case requires positive overdue arrears.")
    connection = get_db()
    active = connection.execute(
        "SELECT case_id FROM CollectionCase WHERE loan_id = ? "
        "AND case_status IN ('open', 'in_progress')",
        (loan_id,),
    ).fetchone()
    if active:
        return get_collection_case(active["case_id"])

    latest = connection.execute(
        "SELECT case_id FROM CollectionCase "
        "WHERE case_id GLOB 'CAS-[0-9][0-9][0-9][0-9][0-9][0-9]' "
        "ORDER BY CAST(substr(case_id, 5) AS INTEGER) DESC LIMIT 1"
    ).fetchone()
    next_id = int(latest["case_id"][4:]) + 1 if latest else 1
    if next_id > 999999:
        raise ApiError("Collection case identifier capacity has been reached.", 409, "id_capacity")
    case_id = f"CAS-{next_id:06d}"
    now = _now()
    try:
        with transaction(connection):
            connection.execute(
                "INSERT INTO CollectionCase "
                "(case_id, loan_id, opened_at, case_status, priority, case_source) "
                "VALUES (?, ?, ?, 'open', ?, ?)",
                (case_id, loan_id, now, _priority(balance["days_past_due"]), source),
            )
            _audit("collection_case_created", "collection_case", case_id, "success",
                   "Case created from current overdue balance.", {"loan_id": loan_id})
    except sqlite3.IntegrityError as error:
        if "UNIQUE" in str(error):
            active = connection.execute(
                "SELECT case_id FROM CollectionCase WHERE loan_id = ? "
                "AND case_status IN ('open', 'in_progress')", (loan_id,)
            ).fetchone()
            if active:
                return get_collection_case(active["case_id"])
        raise ApiError("Collection case violates a database constraint.") from error
    return get_collection_case(case_id)


def _audit(action, entity_type, entity_id, outcome, reason, details=None):
    connection = get_db()
    latest = connection.execute(
        "SELECT audit_id FROM ComplianceAuditEvent "
        "WHERE audit_id GLOB 'AUD-[0-9][0-9][0-9][0-9][0-9][0-9]' "
        "ORDER BY CAST(substr(audit_id, 5) AS INTEGER) DESC LIMIT 1"
    ).fetchone()
    number = int(latest["audit_id"][4:]) + 1 if latest else 1
    if number > 999999:
        raise ApiError("Audit identifier capacity has been reached.", 409, "id_capacity")
    import json
    connection.execute(
        "INSERT INTO ComplianceAuditEvent "
        "(audit_id, event_at, action, entity_type, entity_id, outcome, reason, details_json) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (f"AUD-{number:06d}", _now(), action, entity_type, entity_id, outcome,
         reason, json.dumps(details or {}, sort_keys=True)),
    )


def update_collection_case_status(case_id, payload):
    from app.services.collection_service import get_collection_case
    validate_object(payload, {"case_status"}, ("case_status",))
    new_status = payload["case_status"]
    if not isinstance(new_status, str) or new_status not in _STATUSES:
        raise ApiError("case_status must be open, in_progress, resolved, or closed.")
    connection = get_db()
    case = connection.execute(
        "SELECT case_id, loan_id, case_status FROM CollectionCase WHERE case_id = ?",
        (case_id,),
    ).fetchone()
    if case is None:
        raise NotFoundError("Collection case was not found.")
    allowed = {
        "open": {"open", "in_progress", "resolved", "closed"},
        "in_progress": {"open", "in_progress", "resolved", "closed"},
        "resolved": {"resolved", "closed"},
        "closed": {"closed"},
    }
    if new_status not in allowed[case["case_status"]]:
        raise ConflictError("Collection case lifecycle transition is not allowed.")
    closed_at = _now() if new_status in {"resolved", "closed"} else None
    with transaction(connection):
        connection.execute(
            "UPDATE CollectionCase SET case_status = ?, closed_at = ? WHERE case_id = ?",
            (new_status, closed_at, case_id),
        )
        _audit("collection_case_status_changed", "collection_case", case_id,
               "success", f"Case status changed to {new_status}.",
               {"previous_status": case["case_status"], "case_status": new_status})
    return get_collection_case(case_id)
