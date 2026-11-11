import re
import sqlite3

from app.services.errors import (
    ApiError,
    ConflictError,
    NotFoundError,
    validate_object,
)
from app.services.business_service import _audit
from app.utils.database import get_db, transaction


_CUSTOMER_ID_PREFIX = "CUS-"
_CUSTOMER_FIELDS = {
    "first_name",
    "last_name",
    "email",
    "phone",
    "customer_status",
}
_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _validate_customer_fields(payload, partial=False):
    required = () if partial else ("first_name", "last_name", "email")
    validate_object(payload, _CUSTOMER_FIELDS, required)
    if partial and not payload:
        raise ApiError("At least one customer field must be provided.")

    for field in ("first_name", "last_name", "email"):
        if field in payload:
            value = payload[field]
            if not isinstance(value, str) or not value.strip():
                raise ApiError(f"{field} must be a non-empty string.")
            payload[field] = value.strip()

    if "email" in payload and not _EMAIL_PATTERN.fullmatch(payload["email"]):
        raise ApiError("email must be a valid email address.")
    if "phone" in payload:
        phone = payload["phone"]
        if phone is not None and (
            not isinstance(phone, str) or not phone.strip()
        ):
            raise ApiError("phone must be a non-empty string or null.")
        payload["phone"] = phone.strip() if isinstance(phone, str) else None
    if "customer_status" in payload:
        status = payload["customer_status"]
        if not isinstance(status, str) or status not in {"active", "inactive"}:
            raise ApiError("customer_status must be 'active' or 'inactive'.")


def _customer_row(row):
    return dict(row) if row is not None else None


def list_customers():
    rows = get_db().execute(
        "SELECT customer_id, first_name, last_name, email, phone, "
        "customer_status, created_at FROM Customer ORDER BY customer_id"
    ).fetchall()
    return [_customer_row(row) for row in rows]


def get_customer(customer_id):
    row = get_db().execute(
        "SELECT customer_id, first_name, last_name, email, phone, "
        "customer_status, created_at FROM Customer WHERE customer_id = ?",
        (customer_id,),
    ).fetchone()
    if row is None:
        raise NotFoundError("Customer was not found.")
    return _customer_row(row)


def create_customer(payload):
    payload = dict(payload) if isinstance(payload, dict) else payload
    _validate_customer_fields(payload)
    connection = get_db()
    try:
        with transaction(connection):
            last_id = connection.execute(
                "SELECT customer_id FROM Customer "
                "WHERE customer_id GLOB 'CUS-[0-9][0-9][0-9][0-9][0-9][0-9]' "
                "ORDER BY CAST(substr(customer_id, 5) AS INTEGER) DESC LIMIT 1"
            ).fetchone()
            next_number = int(last_id["customer_id"][4:]) + 1 if last_id else 1
            if next_number > 999999:
                raise ApiError("Customer identifier capacity has been reached.", 409, "id_capacity")
            customer_id = f"{_CUSTOMER_ID_PREFIX}{next_number:06d}"
            connection.execute(
                "INSERT INTO Customer "
                "(customer_id, first_name, last_name, email, phone, customer_status) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    customer_id,
                    payload["first_name"],
                    payload["last_name"],
                    payload["email"],
                    payload.get("phone"),
                    payload.get("customer_status", "active"),
                ),
            )
            _audit(
                "customer_created",
                "customer",
                customer_id,
                "success",
                "Customer record created.",
                {"changed_fields": sorted(payload.keys())},
            )
    except sqlite3.IntegrityError as error:
        if "UNIQUE constraint failed" in str(error):
            raise ConflictError("A customer with that email or phone already exists.") from error
        raise ApiError("Customer details violate a database constraint.") from error
    return get_customer(customer_id)


def update_customer(customer_id, payload):
    payload = dict(payload) if isinstance(payload, dict) else payload
    _validate_customer_fields(payload, partial=True)
    connection = get_db()
    fields = list(payload)
    assignments = ", ".join(f"{field} = ?" for field in fields)
    try:
        with transaction(connection):
            cursor = connection.execute(
                f"UPDATE Customer SET {assignments} WHERE customer_id = ?",
                [payload[field] for field in fields] + [customer_id],
            )
            if cursor.rowcount == 0:
                raise NotFoundError("Customer was not found.")
            _audit(
                "customer_updated",
                "customer",
                customer_id,
                "success",
                "Customer record updated.",
                {"changed_fields": sorted(payload.keys())},
            )
    except sqlite3.IntegrityError as error:
        if "UNIQUE constraint failed" in str(error):
            raise ConflictError("A customer with that email or phone already exists.") from error
        raise ApiError("Customer details violate a database constraint.") from error
    return get_customer(customer_id)
