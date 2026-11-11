import re
import sqlite3
from datetime import datetime, timezone

from app.services.errors import (
    ApiError,
    ConflictError,
    NotFoundError,
    validate_object,
)
from app.utils.database import get_db, transaction


_PAYMENT_FIELDS = {
    "loan_id",
    "amount_minor",
    "payment_method",
    "external_reference",
    "currency_code",
    "received_at",
}
_PAYMENT_METHODS = {
    "bank_transfer",
    "debit_card",
    "cash",
    "mobile_wallet",
    "direct_debit",
    "other",
}
_UTC_TIMESTAMP = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$"
)


def _validate_payment(payload):
    validate_object(
        payload,
        _PAYMENT_FIELDS,
        ("loan_id", "amount_minor", "payment_method", "external_reference"),
    )
    if not isinstance(payload["loan_id"], str) or not payload["loan_id"].strip():
        raise ApiError("loan_id must be a non-empty string.")
    if type(payload["amount_minor"]) is not int or payload["amount_minor"] <= 0:
        raise ApiError("amount_minor must be a positive integer in minor currency units.")
    if (
        not isinstance(payload["payment_method"], str)
        or payload["payment_method"] not in _PAYMENT_METHODS
    ):
        raise ApiError("payment_method is not supported.")
    if payload["amount_minor"] > 9223372036854775807:
        raise ApiError("amount_minor exceeds the supported integer range.")
    reference = payload["external_reference"]
    if not isinstance(reference, str) or not reference.strip():
        raise ApiError("external_reference must be a non-empty string.")
    payload["external_reference"] = reference.strip()
    if "currency_code" in payload:
        currency = payload["currency_code"]
        if not isinstance(currency, str) or not re.fullmatch(r"[A-Z]{3}", currency):
            raise ApiError("currency_code must contain three uppercase letters.")
    if "received_at" in payload:
        timestamp = payload["received_at"]
        if not isinstance(timestamp, str) or not _UTC_TIMESTAMP.fullmatch(timestamp):
            raise ApiError("received_at must be a UTC timestamp in YYYY-MM-DDTHH:MM:SSZ format.")
        try:
            datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%SZ")
        except ValueError as error:
            raise ApiError("received_at must be a valid UTC timestamp.") from error


def _next_id(connection, table, column, prefix):
    row = connection.execute(
        f"SELECT {column} FROM {table} "
        f"WHERE {column} GLOB ? "
        f"ORDER BY CAST(substr({column}, ?) AS INTEGER) DESC LIMIT 1",
        (prefix + "[0-9][0-9][0-9][0-9][0-9][0-9]", len(prefix) + 1),
    ).fetchone()
    next_number = int(row[0][len(prefix):]) + 1 if row else 1
    if next_number > 999999:
        raise ApiError("Payment identifier capacity has been reached.", 409, "id_capacity")
    return f"{prefix}{next_number:06d}"


def _payment_with_allocations(connection, payment_id):
    payment = connection.execute(
        """
        SELECT p.payment_id, p.loan_id, p.received_at, p.amount_minor,
               p.currency_code, p.payment_method, p.external_reference,
               p.payment_status, p.reversed_at, p.created_at,
               COALESCE(SUM(CASE WHEN a.allocation_status = 'active'
                                 AND p.payment_status = 'posted'
                            THEN a.allocated_principal_minor
                               + a.allocated_interest_minor ELSE 0 END), 0)
                   AS amount_allocated_minor
        FROM Payment p
        LEFT JOIN PaymentAllocation a ON a.payment_id = p.payment_id
        WHERE p.payment_id = ?
        GROUP BY p.payment_id
        """,
        (payment_id,),
    ).fetchone()
    if payment is None:
        return None
    result = dict(payment)
    result["amount_unallocated_minor"] = (
        result["amount_minor"] - result["amount_allocated_minor"]
        if result["payment_status"] == "posted"
        else 0
    )
    result["allocations"] = [
        dict(row)
        for row in connection.execute(
            """
            SELECT allocation_id, installment_id,
                   allocated_principal_minor, allocated_interest_minor,
                   allocation_status, allocated_at, reversed_at
            FROM PaymentAllocation
            WHERE payment_id = ?
            ORDER BY allocation_id
            """,
            (payment_id,),
        ).fetchall()
    ]
    return result


def list_payments(loan_id=None):
    connection = get_db()
    if loan_id is not None and connection.execute(
        "SELECT 1 FROM Loan WHERE loan_id = ?", (loan_id,)
    ).fetchone() is None:
        raise NotFoundError("Loan was not found.")
    query = "SELECT payment_id FROM Payment"
    params = ()
    if loan_id is not None:
        query += " WHERE loan_id = ?"
        params = (loan_id,)
    query += " ORDER BY received_at DESC, payment_id DESC"
    payment_ids = [
        row["payment_id"] for row in connection.execute(query, params).fetchall()
    ]
    return [
        _payment_with_allocations(connection, payment_id)
        for payment_id in payment_ids
    ]


def record_payment(payload):
    payload = dict(payload) if isinstance(payload, dict) else payload
    _validate_payment(payload)
    connection = get_db()
    received_at = payload.get("received_at")
    if received_at is None:
        received_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    try:
        with transaction(connection):
            loan = connection.execute(
                "SELECT currency_code FROM Loan WHERE loan_id = ?",
                (payload["loan_id"],),
            ).fetchone()
            if loan is None:
                raise NotFoundError("Loan was not found.")
            currency_code = payload.get("currency_code", loan["currency_code"])
            if currency_code != loan["currency_code"]:
                raise ApiError("currency_code must match the loan currency.")

            payment_id = _next_id(connection, "Payment", "payment_id", "PAY-")
            connection.execute(
                """
                INSERT INTO Payment
                    (payment_id, loan_id, received_at, amount_minor,
                     currency_code, payment_method, external_reference,
                     payment_status)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'posted')
                """,
                (
                    payment_id,
                    payload["loan_id"],
                    received_at,
                    payload["amount_minor"],
                    currency_code,
                    payload["payment_method"],
                    payload["external_reference"],
                ),
            )
            from app.services.business_service import _audit
            _audit(
            "payment_recorded",
            "payment",
            payment_id,
            "success",
            "Posted payment and deterministic earliest-due allocations recorded.",
            {"loan_id": payload["loan_id"], "amount_minor": payload["amount_minor"]},
            )

            remaining_payment = payload["amount_minor"]
            installments = connection.execute(
                """
                SELECT i.installment_id, i.scheduled_principal_minor,
                       i.scheduled_interest_minor,
                       COALESCE(a.paid_principal_minor, 0) AS paid_principal_minor,
                       COALESCE(a.paid_interest_minor, 0) AS paid_interest_minor
                FROM Installment i
                LEFT JOIN (
                    SELECT pa.installment_id,
                           SUM(pa.allocated_principal_minor) AS paid_principal_minor,
                           SUM(pa.allocated_interest_minor) AS paid_interest_minor
                    FROM PaymentAllocation pa
                    JOIN Payment p ON p.payment_id = pa.payment_id
                    WHERE pa.allocation_status = 'active'
                      AND p.payment_status = 'posted'
                    GROUP BY pa.installment_id
                ) a ON a.installment_id = i.installment_id
                WHERE i.loan_id = ? AND i.due_date <= ?
                ORDER BY i.due_date, i.installment_number
                """,
                (payload["loan_id"], received_at[:10]),
            ).fetchall()

            for installment in installments:
                if remaining_payment == 0:
                    break
                remaining_interest = (
                    installment["scheduled_interest_minor"]
                    - installment["paid_interest_minor"]
                )
                remaining_principal = (
                    installment["scheduled_principal_minor"]
                    - installment["paid_principal_minor"]
                )
                interest = min(remaining_payment, remaining_interest)
                remaining_payment -= interest
                principal = min(remaining_payment, remaining_principal)
                remaining_payment -= principal
                if interest == 0 and principal == 0:
                    continue
                allocation_id = _next_id(
                    connection, "PaymentAllocation", "allocation_id", "ALL-"
                )
                connection.execute(
                    """
                    INSERT INTO PaymentAllocation
                        (allocation_id, payment_id, installment_id,
                         allocated_principal_minor, allocated_interest_minor,
                         allocation_status, allocated_at)
                    VALUES (?, ?, ?, ?, ?, 'active', ?)
                    """,
                    (
                        allocation_id,
                        payment_id,
                        installment["installment_id"],
                        principal,
                        interest,
                        received_at,
                    ),
                )
    except sqlite3.IntegrityError as error:
        if "UNIQUE constraint failed: Payment.external_reference" in str(error):
            raise ConflictError("A payment with that external_reference already exists.") from error
        raise ApiError("Payment details violate a database constraint.") from error

    return _payment_with_allocations(connection, payment_id)
