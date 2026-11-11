import sqlite3
from datetime import datetime, timezone

from app.services.errors import (
    ApiError,
    ConflictError,
    NotFoundError,
    validate_object,
)
from app.utils.database import get_db, transaction


_CASE_STATUSES = {"open", "in_progress", "resolved", "closed"}


def _case_detail(connection, case_id):
    row = connection.execute(
        """
        SELECT c.case_id, c.loan_id, c.opened_at, c.case_status, c.priority,
               c.case_source, c.closed_at, l.customer_id
        FROM CollectionCase c
        JOIN Loan l ON l.loan_id = c.loan_id
        WHERE c.case_id = ?
        """,
        (case_id,),
    ).fetchone()
    if row is None:
        raise NotFoundError("Collection case was not found.")
    result = dict(row)
    from app.services.business_service import calculate_loan_balance
    result.update(calculate_loan_balance(result["loan_id"]))
    account_status = connection.execute(
        "SELECT dispute_status, hardship_status, debt_status "
        "FROM LoanAccountStatus WHERE loan_id = ?",
        (result["loan_id"],),
    ).fetchone()
    result["account_status"] = (
        dict(account_status) if account_status else {
            "dispute_status": "clear",
            "hardship_status": "none",
            "debt_status": "unverified",
        }
    )
    result["contact_attempts"] = [
        dict(item)
        for item in connection.execute(
            """
            SELECT contact_attempt_id, attempted_at, channel, outcome, notes
            FROM ContactAttempt WHERE case_id = ?
            ORDER BY attempted_at, contact_attempt_id
            """,
            (case_id,),
        ).fetchall()
    ]
    result["promises_to_pay"] = [
        dict(item)
        for item in connection.execute(
            """
            SELECT promise_id, promised_at, due_date, amount_minor,
                   currency_code, promise_status, resolved_at, created_at
            FROM PromiseToPay WHERE case_id = ?
            ORDER BY due_date, promise_id
            """,
            (case_id,),
        ).fetchall()
    ]
    return result


def list_collection_cases():
    connection = get_db()
    case_ids = connection.execute(
        "SELECT case_id FROM CollectionCase ORDER BY opened_at DESC, case_id"
    ).fetchall()
    return [_case_detail(connection, row["case_id"]) for row in case_ids]


def get_collection_case(case_id):
    return _case_detail(get_db(), case_id)


def update_collection_case_status(case_id, payload):
    from app.services.business_service import update_collection_case_status as update
    return update(case_id, payload)
