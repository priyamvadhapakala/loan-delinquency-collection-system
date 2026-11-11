import json
import re
import sqlite3
from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.services.business_service import _audit, _now, calculate_loan_balance
from app.services.errors import ApiError, ConflictError, NotFoundError, validate_object
from app.utils.database import get_db, transaction


_CHANNELS = {"phone", "email", "sms", "letter"}
_OUTCOMES = {
    "connected", "no_answer", "left_message", "message_sent",
    "wrong_contact", "opted_out",
}
_TIME_PATTERN = re.compile(r"^\d{2}:\d{2}$")
_UTC_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


def _validate_time(value, field):
    if not isinstance(value, str) or not _TIME_PATTERN.fullmatch(value):
        raise ApiError(f"{field} must use HH:MM format.")
    try:
        return time.fromisoformat(value)
    except ValueError as error:
        raise ApiError(f"{field} must be a valid time.") from error


def _validate_timestamp(value):
    if not isinstance(value, str) or not _UTC_PATTERN.fullmatch(value):
        raise ApiError("attempted_at must be a UTC timestamp in YYYY-MM-DDTHH:MM:SSZ format.")
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError as error:
        raise ApiError("attempted_at must be a valid UTC timestamp.") from error


def get_contact_preference(customer_id):
    row = get_db().execute(
        "SELECT * FROM ContactPreference WHERE customer_id = ?", (customer_id,)
    ).fetchone()
    if row is None:
        if get_db().execute(
            "SELECT 1 FROM Customer WHERE customer_id = ?", (customer_id,)
        ).fetchone() is None:
            raise NotFoundError("Customer was not found.")
        return None
    result = dict(row)
    result["allowed_channels"] = (
        json.loads(result.pop("allowed_channels_json"))
        if result.get("allowed_channels_json") is not None
        else None
    )
    return result


def set_contact_preference(customer_id, payload):
    fields = {
        "preferred_channel", "contact_window", "consent_status", "timezone",
        "allowed_contact_start", "allowed_contact_end",
        "weekend_contact_allowed", "holiday_contact_allowed", "allowed_channels",
    }
    validate_object(payload, fields, ("preferred_channel", "consent_status"))
    connection = get_db()
    if connection.execute(
        "SELECT 1 FROM Customer WHERE customer_id = ?", (customer_id,)
    ).fetchone() is None:
        raise NotFoundError("Customer was not found.")
    channel = payload["preferred_channel"]
    consent = payload["consent_status"]
    if channel not in {"phone", "email", "sms", "letter", "none"}:
        raise ApiError("preferred_channel is invalid.")
    if consent not in {"granted", "not_required", "withdrawn"}:
        raise ApiError("consent_status is invalid.")
    if consent == "withdrawn" and channel != "none":
        raise ApiError("Withdrawn consent requires preferred_channel 'none'.")
    contact_window = payload.get("contact_window")
    if contact_window is not None and contact_window not in {
        "morning", "afternoon", "evening", "any"
    }:
        raise ApiError("contact_window is invalid.")
    zone = payload.get("timezone")
    if zone is not None:
        if not isinstance(zone, str) or not zone:
            raise ApiError("timezone must be a valid IANA timezone name.")
        try:
            ZoneInfo(zone)
        except ZoneInfoNotFoundError as error:
            raise ApiError("timezone must be a valid IANA timezone name.") from error
    start = payload.get("allowed_contact_start")
    end = payload.get("allowed_contact_end")
    if (start is None) != (end is None):
        raise ApiError("allowed_contact_start and allowed_contact_end must be configured together.")
    if start is not None:
        _validate_time(start, "allowed_contact_start")
        _validate_time(end, "allowed_contact_end")
        if start >= end:
            raise ApiError("Allowed contact hours must begin before they end.")
    for field in ("weekend_contact_allowed", "holiday_contact_allowed"):
        if field in payload and type(payload[field]) is not bool:
            raise ApiError(f"{field} must be a boolean.")
    allowed_channels = payload.get("allowed_channels")
    if allowed_channels is not None:
        if (not isinstance(allowed_channels, list)
                or not all(isinstance(item, str) and item in _CHANNELS
                           for item in allowed_channels)
                or len(set(allowed_channels)) != len(allowed_channels)):
            raise ApiError("allowed_channels must be a unique list of valid contact channels.")

    values = {
        "customer_id": customer_id,
        "preferred_channel": channel,
        "contact_window": contact_window,
        "consent_status": consent,
        "timezone": zone,
        "allowed_contact_start": start,
        "allowed_contact_end": end,
        "weekend_contact_allowed": int(payload.get("weekend_contact_allowed", False)),
        "holiday_contact_allowed": int(payload.get("holiday_contact_allowed", False)),
        "allowed_channels_json": (
            json.dumps(allowed_channels, separators=(",", ":"))
            if allowed_channels is not None else None
        ),
        "updated_at": _now(),
    }
    with transaction(connection):
        connection.execute(
            """
            INSERT INTO ContactPreference (
                customer_id, preferred_channel, contact_window, consent_status,
                timezone, allowed_contact_start, allowed_contact_end,
                weekend_contact_allowed, holiday_contact_allowed,
                allowed_channels_json, updated_at
            ) VALUES (
                :customer_id, :preferred_channel, :contact_window, :consent_status,
                :timezone, :allowed_contact_start, :allowed_contact_end,
                :weekend_contact_allowed, :holiday_contact_allowed,
                :allowed_channels_json, :updated_at
            )
            ON CONFLICT(customer_id) DO UPDATE SET
                preferred_channel=excluded.preferred_channel,
                contact_window=excluded.contact_window,
                consent_status=excluded.consent_status,
                timezone=excluded.timezone,
                allowed_contact_start=excluded.allowed_contact_start,
                allowed_contact_end=excluded.allowed_contact_end,
                weekend_contact_allowed=excluded.weekend_contact_allowed,
                holiday_contact_allowed=excluded.holiday_contact_allowed,
                allowed_channels_json=excluded.allowed_channels_json,
                updated_at=excluded.updated_at
            """,
            values,
        )
        _audit("contact_preference_updated", "customer", customer_id, "success",
               "Contact settings saved.", values)
    return get_contact_preference(customer_id)


def _case_customer(case_id):
    row = get_db().execute(
        """
        SELECT c.case_id, c.loan_id, c.case_status, l.customer_id
        FROM CollectionCase c JOIN Loan l ON l.loan_id = c.loan_id
        WHERE c.case_id = ?
        """,
        (case_id,),
    ).fetchone()
    if row is None:
        raise NotFoundError("Collection case was not found.")
    return row


def create_contact_attempt(case_id, payload):
    validate_object(
        payload,
        {"attempted_at", "channel", "outcome", "notes"},
        ("attempted_at", "channel", "outcome"),
    )
    attempted = _validate_timestamp(payload["attempted_at"])
    channel = payload["channel"]
    outcome = payload["outcome"]
    notes = payload.get("notes")
    if channel not in _CHANNELS or channel == "letter" and not isinstance(channel, str):
        raise ApiError("channel is invalid.")
    if outcome not in _OUTCOMES:
        raise ApiError("outcome is invalid.")
    if notes is not None and (not isinstance(notes, str) or len(notes) > 500):
        raise ApiError("notes must be a string of at most 500 characters.")
    case = _case_customer(case_id)
    connection = get_db()
    preference = connection.execute(
        "SELECT * FROM ContactPreference WHERE customer_id = ?",
        (case["customer_id"],),
    ).fetchone()
    reasons = []
    if case["case_status"] in {"resolved", "closed"}:
        reasons.append("Collection case is not active.")
    if preference is None:
        reasons.append("Contact preference, timezone, and allowed hours are not configured.")
    else:
        if not preference["timezone"] or not preference["allowed_contact_start"] or not preference["allowed_contact_end"]:
            reasons.append("Timezone and allowed contact hours must be explicitly configured.")
        if preference["consent_status"] == "withdrawn" or preference["preferred_channel"] == "none":
            reasons.append("Customer contact preference does not permit contact.")
        if preference["allowed_channels_json"] is not None:
            channels = json.loads(preference["allowed_channels_json"])
            if channel not in channels:
                reasons.append("Contact channel is outside the configured allowed channels.")
        account = connection.execute(
            "SELECT dispute_status FROM LoanAccountStatus WHERE loan_id = ?",
            (case["loan_id"],),
        ).fetchone()
        if account and account["dispute_status"] == "disputed":
            reasons.append("Debt is disputed; collection contact is paused.")
        if preference["timezone"] and preference["allowed_contact_start"] and preference["allowed_contact_end"]:
            local = attempted.astimezone(ZoneInfo(preference["timezone"]))
            local_date = local.date()
            local_time = local.timetz().replace(tzinfo=None)
            if not (_validate_time(preference["allowed_contact_start"], "allowed_contact_start")
                    <= local_time
                    < _validate_time(preference["allowed_contact_end"], "allowed_contact_end")):
                reasons.append("Contact is outside the configured local-time window.")
            if local.weekday() >= 5 and not preference["weekend_contact_allowed"]:
                reasons.append("Weekend contact is not explicitly permitted.")
            holiday = connection.execute(
                "SELECT 1 FROM ContactHoliday WHERE holiday_date = ?",
                (local_date.isoformat(),),
            ).fetchone()
            if holiday and not preference["holiday_contact_allowed"]:
                reasons.append("Holiday contact is not explicitly permitted.")

    with transaction(connection):
        if reasons:
            reason = " ".join(reasons)
            _audit("contact_attempt", "collection_case", case_id, "denied",
                   reason, {"attempted_at": payload["attempted_at"], "channel": channel})
        else:
            latest = connection.execute(
                "SELECT contact_attempt_id FROM ContactAttempt "
                "WHERE contact_attempt_id GLOB 'CNT-[0-9][0-9][0-9][0-9][0-9][0-9]' "
                "ORDER BY CAST(substr(contact_attempt_id, 5) AS INTEGER) DESC LIMIT 1"
            ).fetchone()
            number = int(latest["contact_attempt_id"][4:]) + 1 if latest else 1
            if number > 999999:
                raise ApiError("Contact attempt identifier capacity has been reached.", 409, "id_capacity")
            attempt_id = f"CNT-{number:06d}"
            connection.execute(
                "INSERT INTO ContactAttempt "
                "(contact_attempt_id, case_id, attempted_at, channel, outcome, notes) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (attempt_id, case_id, payload["attempted_at"], channel, outcome, notes),
            )
            _audit("contact_attempt", "collection_case", case_id, "permitted",
                   "Contact attempt passed configured test-only rules.",
                   {"contact_attempt_id": attempt_id, "attempted_at": payload["attempted_at"],
                    "channel": channel, "outcome": outcome})
            if outcome == "opted_out":
                connection.execute(
                    "UPDATE ContactPreference SET preferred_channel='none', "
                    "consent_status='withdrawn', updated_at=? WHERE customer_id=?",
                    (_now(), case["customer_id"]),
                )
                _audit("contact_preference_withdrawn", "customer", case["customer_id"],
                       "success", "Customer opted out during a recorded attempt.")
    if reasons:
        raise ApiError("Contact attempt denied: " + " ".join(reasons), 403, "contact_denied")
    return dict(connection.execute(
        "SELECT * FROM ContactAttempt WHERE contact_attempt_id = ?", (attempt_id,)
    ).fetchone())


def create_contact_holiday(holiday_date, payload):
    validate_object(payload, {"label"}, ("label",))
    try:
        parsed = date.fromisoformat(holiday_date)
    except (TypeError, ValueError) as error:
        raise ApiError("Holiday date must be YYYY-MM-DD.") from error
    label = payload["label"]
    if not isinstance(label, str) or not label.strip():
        raise ApiError("label must be a non-empty string.")
    connection = get_db()
    try:
        with transaction(connection):
            connection.execute(
                "INSERT INTO ContactHoliday(holiday_date, label, configured_at) VALUES (?, ?, ?)",
                (parsed.isoformat(), label.strip(), _now()),
            )
            _audit("contact_holiday_configured", "contact_holiday", parsed.isoformat(),
                   "success", "Holiday explicitly configured.", {"label": label.strip()})
    except sqlite3.IntegrityError as error:
        raise ConflictError("This contact holiday is already configured.") from error
    return {"holiday_date": parsed.isoformat(), "label": label.strip()}


def set_account_status(loan_id, payload):
    fields = {"dispute_status", "hardship_status", "debt_status"}
    validate_object(payload, fields)
    if not payload:
        raise ApiError("At least one account status must be provided.")
    connection = get_db()
    if connection.execute("SELECT 1 FROM Loan WHERE loan_id=?", (loan_id,)).fetchone() is None:
        raise NotFoundError("Loan was not found.")
    current = connection.execute(
        "SELECT dispute_status, hardship_status, debt_status "
        "FROM LoanAccountStatus WHERE loan_id = ?", (loan_id,)
    ).fetchone()
    result = {
        "dispute_status": current["dispute_status"] if current else "clear",
        "hardship_status": current["hardship_status"] if current else "none",
        "debt_status": current["debt_status"] if current else "unverified",
    }
    result.update(payload)
    allowed = {
        "dispute_status": {"clear", "disputed", "resolved"},
        "hardship_status": {"none", "active", "resolved"},
        "debt_status": {"unverified", "confirmed"},
    }
    for field, values in allowed.items():
        if result[field] not in values:
            raise ApiError(f"{field} is invalid.")
    if result["dispute_status"] == "disputed" and result["debt_status"] == "confirmed":
        raise ConflictError("Disputed debt cannot be treated as confirmed.")
    now = _now()
    with transaction(connection):
        connection.execute(
            """
            INSERT INTO LoanAccountStatus
                (loan_id, dispute_status, hardship_status, debt_status, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(loan_id) DO UPDATE SET
                dispute_status=excluded.dispute_status,
                hardship_status=excluded.hardship_status,
                debt_status=excluded.debt_status,
                updated_at=excluded.updated_at
            """,
            (loan_id, result["dispute_status"], result["hardship_status"],
             result["debt_status"], now),
        )
        _audit("account_status_updated", "loan", loan_id, "success",
               "Dispute, hardship, and debt verification status updated.", result)
    return {**result, "loan_id": loan_id, "updated_at": now}


def get_account_status(loan_id):
    if get_db().execute("SELECT 1 FROM Loan WHERE loan_id=?", (loan_id,)).fetchone() is None:
        raise NotFoundError("Loan was not found.")
    row = get_db().execute(
        "SELECT loan_id, dispute_status, hardship_status, debt_status, updated_at "
        "FROM LoanAccountStatus WHERE loan_id = ?", (loan_id,)
    ).fetchone()
    return dict(row) if row else {
        "loan_id": loan_id, "dispute_status": "clear",
        "hardship_status": "none", "debt_status": "unverified", "updated_at": None,
    }


def _arrears_at(connection, loan_id, as_of):
    return calculate_loan_balance(loan_id, as_of)["arrears_amount_minor"]


def _promise_payment_totals(connection, promises):
    totals = {promise["promise_id"]: 0 for promise in promises}
    by_loan = {}
    for promise in promises:
        if promise["promise_status"] != "cancelled":
            by_loan.setdefault(promise["loan_id"], []).append(promise)

    for loan_id, loan_promises in by_loan.items():
        ordered_promises = sorted(
            loan_promises,
            key=lambda item: (item["due_date"], item["promised_at"], item["promise_id"]),
        )
        payments = connection.execute(
            "SELECT received_at, amount_minor FROM Payment "
            "WHERE loan_id=? AND payment_status='posted' "
            "ORDER BY received_at, payment_id",
            (loan_id,),
        ).fetchall()
        for payment in payments:
            payment_date = payment["received_at"][:10]
            remaining_payment = payment["amount_minor"]
            for promise in ordered_promises:
                if not (
                    promise["promised_at"] < payment["received_at"]
                    and payment_date <= promise["due_date"]
                ):
                    continue
                remaining_promise = promise["amount_minor"] - totals[promise["promise_id"]]
                if remaining_promise <= 0:
                    continue
                allocated = min(remaining_payment, remaining_promise)
                totals[promise["promise_id"]] += allocated
                remaining_payment -= allocated
                if remaining_payment == 0:
                    break
    return totals


def list_promises():
    rows = get_db().execute(
        """
        SELECT p.promise_id, p.case_id, c.loan_id, l.customer_id,
               p.promised_at, p.due_date, p.amount_minor, p.currency_code,
               p.promise_status, p.resolved_at, p.created_at
        FROM PromiseToPay p
        JOIN CollectionCase c ON c.case_id=p.case_id
        JOIN Loan l ON l.loan_id=c.loan_id
        ORDER BY p.due_date, p.promise_id
        """
    ).fetchall()
    return [dict(row) for row in rows]


def create_promise(case_id, payload):
    validate_object(
        payload, {"promised_at", "due_date", "amount_minor"},
        ("promised_at", "due_date", "amount_minor")
    )
    promised_at = payload["promised_at"]
    if not isinstance(promised_at, str) or not _UTC_PATTERN.fullmatch(promised_at):
        raise ApiError("promised_at must be a UTC timestamp.")
    try:
        datetime.strptime(promised_at, "%Y-%m-%dT%H:%M:%SZ")
        due_date = date.fromisoformat(payload["due_date"])
    except (TypeError, ValueError) as error:
        raise ApiError("promised_at or due_date is invalid.") from error
    if due_date < date.fromisoformat(promised_at[:10]):
        raise ApiError("due_date must be on or after promised_at.")
    amount = payload["amount_minor"]
    if type(amount) is not int or amount <= 0:
        raise ApiError("amount_minor must be a positive integer.")
    case = _case_customer(case_id)
    if case["case_status"] not in {"open", "in_progress"}:
        raise ConflictError("A promise can only be recorded on an active collection case.")
    account = get_account_status(case["loan_id"])
    if account["dispute_status"] == "disputed":
        raise ConflictError("A promise cannot be recorded while the debt is disputed.")
    arrears = _arrears_at(get_db(), case["loan_id"], promised_at[:10])
    if arrears <= 0:
        raise ConflictError("A promise requires positive arrears.")
    if amount > arrears:
        raise ApiError("amount_minor cannot exceed current overdue arrears.")
    currency = get_db().execute(
        "SELECT currency_code FROM Loan WHERE loan_id=?", (case["loan_id"],)
    ).fetchone()["currency_code"]
    latest = get_db().execute(
        "SELECT promise_id FROM PromiseToPay "
        "WHERE promise_id GLOB 'PTP-[0-9][0-9][0-9][0-9][0-9][0-9]' "
        "ORDER BY CAST(substr(promise_id, 5) AS INTEGER) DESC LIMIT 1"
    ).fetchone()
    number = int(latest["promise_id"][4:]) + 1 if latest else 1
    if number > 999999:
        raise ApiError("Promise identifier capacity has been reached.", 409, "id_capacity")
    promise_id = f"PTP-{number:06d}"
    connection = get_db()
    try:
        with transaction(connection):
            connection.execute(
                "INSERT INTO PromiseToPay "
                "(promise_id, case_id, promised_at, due_date, amount_minor, currency_code) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (promise_id, case_id, promised_at, due_date.isoformat(), amount, currency),
            )
            _audit("promise_created", "promise", promise_id, "success",
                   "Promise amount validated against arrears.",
                   {"case_id": case_id, "amount_minor": amount,
                    "arrears_amount_minor": arrears, "due_date": due_date.isoformat()})
    except sqlite3.IntegrityError as error:
        raise ApiError("Promise details violate a database constraint.") from error
    return next(row for row in list_promises() if row["promise_id"] == promise_id)


def update_promise_status(promise_id, payload):
    validate_object(payload, {"promise_status"}, ("promise_status",))
    new_status = payload["promise_status"]
    if new_status not in {"kept", "broken", "cancelled"}:
        raise ApiError("promise_status must be kept, broken, or cancelled.")
    connection = get_db()
    promise = connection.execute(
        """
        SELECT p.*, c.loan_id FROM PromiseToPay p
        JOIN CollectionCase c ON c.case_id=p.case_id WHERE p.promise_id=?
        """,
        (promise_id,),
    ).fetchone()
    if promise is None:
        raise NotFoundError("Promise was not found.")
    if promise["promise_status"] != "pending":
        raise ConflictError("Only pending promises can be resolved.")
    today = date.today().isoformat()
    if new_status == "broken" and promise["due_date"] >= today:
        raise ConflictError("A promise cannot be marked broken before its due date.")
    if new_status in {"kept", "broken"}:
        promises = connection.execute(
            """
            SELECT p.promise_id, p.amount_minor, p.promised_at, p.due_date,
                   p.promise_status, c.loan_id
            FROM PromiseToPay p JOIN CollectionCase c ON c.case_id=p.case_id
            WHERE c.loan_id=? AND p.promise_status <> 'cancelled'
            """,
            (promise["loan_id"],),
        ).fetchall()
        paid = _promise_payment_totals(connection, promises).get(promise_id, 0)
        if new_status == "kept" and paid < promise["amount_minor"]:
            raise ConflictError("Recorded posted payments do not fulfill this promise.")
        if new_status == "broken" and paid >= promise["amount_minor"]:
            raise ConflictError("Posted payments fulfill this promise; it cannot be marked broken.")
    resolved_at = _now()
    with transaction(connection):
        connection.execute(
            "UPDATE PromiseToPay SET promise_status=?, resolved_at=? WHERE promise_id=?",
            (new_status, resolved_at, promise_id),
        )
        _audit("promise_status_changed", "promise", promise_id, "success",
               f"Promise marked {new_status}.",
               {"promise_status": new_status, "payments_minor": (
                   paid if new_status in {"kept", "broken"} else None
               )})
    return next(row for row in list_promises() if row["promise_id"] == promise_id)


def evaluate_promises(as_of=None):
    if as_of is None:
        cutoff = date.today()
    else:
        try:
            cutoff = date.fromisoformat(as_of)
        except (TypeError, ValueError) as error:
            raise ApiError("as_of must be a valid YYYY-MM-DD date.") from error
    connection = get_db()
    pending = connection.execute(
        """
        SELECT p.promise_id, p.amount_minor, p.promised_at, p.due_date, c.loan_id
        FROM PromiseToPay p JOIN CollectionCase c ON c.case_id=p.case_id
        WHERE p.promise_status='pending' AND p.due_date < ?
        ORDER BY p.due_date, p.promised_at, p.promise_id
        """,
        (cutoff.isoformat(),),
    ).fetchall()
    all_promises = connection.execute(
        """
        SELECT p.promise_id, p.amount_minor, p.promised_at, p.due_date,
               p.promise_status, c.loan_id
        FROM PromiseToPay p JOIN CollectionCase c ON c.case_id=p.case_id
        WHERE p.promise_status <> 'cancelled'
        """
    ).fetchall()
    payment_totals = _promise_payment_totals(connection, all_promises)
    evaluated = []
    for promise in pending:
        paid = payment_totals.get(promise["promise_id"], 0)
        status = "kept" if paid >= promise["amount_minor"] else "broken"
        resolved_at = _now()
        with transaction(connection):
            connection.execute(
                "UPDATE PromiseToPay SET promise_status=?, resolved_at=? "
                "WHERE promise_id=? AND promise_status='pending'",
                (status, resolved_at, promise["promise_id"]),
            )
            _audit("promise_evaluated", "promise", promise["promise_id"], "success",
                   f"Promise evaluated as {status} from posted payments.",
                   {"payments_minor": paid, "amount_minor": promise["amount_minor"]})
        evaluated.append({"promise_id": promise["promise_id"], "promise_status": status})
    return {"as_of": cutoff.isoformat(), "evaluated": evaluated}


def list_audit_events(entity_type=None, entity_id=None):
    query = "SELECT * FROM ComplianceAuditEvent"
    clauses = []
    params = []
    if entity_type is not None:
        clauses.append("entity_type = ?")
        params.append(entity_type)
    if entity_id is not None:
        clauses.append("entity_id = ?")
        params.append(entity_id)
    if clauses:
        query += " WHERE " + " AND ".join(clauses)
    query += " ORDER BY event_at, audit_id"
    result = []
    for row in get_db().execute(query, params).fetchall():
        record = dict(row)
        record["details"] = json.loads(record.pop("details_json"))
        result.append(record)
    return result
