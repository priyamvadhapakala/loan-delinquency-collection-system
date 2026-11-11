from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.services.business_service import _now, calculate_loan_balance, list_delinquency
from app.services.errors import ApiError
from app.utils.database import get_db, transaction


_ANOMALIES = (
    "paid_account_in_collection",
    "contact_outside_allowed_window",
    "payment_wrong_installment",
    "promise_exceeds_arrears",
    "disputed_debt_confirmed",
)


def _contact_is_invalid(row, holiday_dates):
    if not row["timezone"] or not row["allowed_contact_start"] or not row["allowed_contact_end"]:
        return "Customer timezone or allowed contact hours are not configured."
    try:
        local = datetime.strptime(
            row["attempted_at"], "%Y-%m-%dT%H:%M:%SZ"
        ).replace(tzinfo=timezone.utc).astimezone(ZoneInfo(row["timezone"]))
    except (ValueError, ZoneInfoNotFoundError):
        return "Contact attempt has an invalid timestamp or timezone."
    local_time = local.strftime("%H:%M")
    if not row["allowed_contact_start"] <= local_time < row["allowed_contact_end"]:
        return "Contact attempt was outside configured local contact hours."
    if local.weekday() >= 5 and not row["weekend_contact_allowed"]:
        return "Contact attempt occurred on a weekend without explicit permission."
    if local.date().isoformat() in holiday_dates and not row["holiday_contact_allowed"]:
        return "Contact attempt occurred on a configured holiday without explicit permission."
    if row["consent_status"] == "withdrawn" or row["preferred_channel"] == "none":
        return "Contact attempt used a withdrawn or disabled contact preference."
    if row["allowed_channels_json"] is not None:
        import json
        if row["channel"] not in json.loads(row["allowed_channels_json"]):
            return "Contact attempt used a channel outside the explicitly allowed list."
    return None


def _wrong_allocation_records(connection):
    rows = connection.execute(
        """
        SELECT a.allocation_id, a.installment_id, a.allocated_principal_minor,
               a.allocated_interest_minor, p.payment_id, p.loan_id, p.received_at,
               i.due_date
        FROM PaymentAllocation a
        JOIN Payment p ON p.payment_id=a.payment_id
        JOIN Installment i ON i.installment_id=a.installment_id
        WHERE a.allocation_status='active' AND p.payment_status='posted'
        ORDER BY p.received_at, p.payment_id, a.allocation_id
        """
    ).fetchall()
    schedules = {}
    for row in connection.execute(
        "SELECT installment_id, loan_id, due_date, "
        "scheduled_principal_minor + scheduled_interest_minor AS scheduled_minor "
        "FROM Installment ORDER BY due_date, installment_number"
    ).fetchall():
        schedules.setdefault(row["loan_id"], []).append(dict(row))
    paid = {}
    anomalies = []
    for row in rows:
        schedule = schedules.get(row["loan_id"], [])
        target = next(item for item in schedule if item["installment_id"] == row["installment_id"])
        received_date = row["received_at"][:10]
        reason = None
        if row["due_date"] > received_date:
            reason = "Payment was allocated to an installment not yet due on its received date."
        else:
            for item in schedule:
                if item["due_date"] > received_date:
                    break
                if item["due_date"] >= target["due_date"]:
                    break
                remaining = item["scheduled_minor"] - paid.get(item["installment_id"], 0)
                if remaining > 0:
                    reason = (
                        f"Earlier due installment {item['installment_id']} had "
                        f"{remaining} minor units outstanding before this allocation."
                    )
                    break
        if reason:
            anomalies.append({
                "anomaly_type": "payment_wrong_installment",
                "record_reference": row["allocation_id"],
                "reason": reason,
            })
        paid[row["installment_id"]] = paid.get(row["installment_id"], 0) + (
            row["allocated_principal_minor"] + row["allocated_interest_minor"]
        )
    return anomalies


def detect_anomalies(as_of=None):
    if as_of is None:
        cutoff = date.today().isoformat()
    else:
        try:
            cutoff = date.fromisoformat(as_of).isoformat()
        except (TypeError, ValueError) as error:
            raise ApiError("as_of must be a valid YYYY-MM-DD date.") from error
    connection = get_db()
    found = []

    active_cases = connection.execute(
        "SELECT case_id, loan_id FROM CollectionCase "
        "WHERE case_status IN ('open', 'in_progress')"
    ).fetchall()
    for case in active_cases:
        balance = calculate_loan_balance(case["loan_id"], cutoff)
        if balance["outstanding_balance_minor"] == 0:
            found.append({
                "anomaly_type": "paid_account_in_collection",
                "record_reference": case["case_id"],
                "reason": "Loan has zero outstanding balance but an active collection case remains.",
            })

    holiday_dates = {
        row["holiday_date"]
        for row in connection.execute("SELECT holiday_date FROM ContactHoliday").fetchall()
    }
    contacts = connection.execute(
        """
        SELECT ca.contact_attempt_id, ca.case_id, ca.attempted_at, ca.channel,
               cp.timezone, cp.allowed_contact_start, cp.allowed_contact_end,
               cp.weekend_contact_allowed, cp.holiday_contact_allowed,
               cp.consent_status, cp.preferred_channel, cp.allowed_channels_json,
               l.customer_id
        FROM ContactAttempt ca
        JOIN CollectionCase c ON c.case_id=ca.case_id
        JOIN Loan l ON l.loan_id=c.loan_id
        LEFT JOIN ContactPreference cp ON cp.customer_id=l.customer_id
        """
    ).fetchall()
    for contact in contacts:
        reason = _contact_is_invalid(contact, holiday_dates)
        if reason:
            found.append({
                "anomaly_type": "contact_outside_allowed_window",
                "record_reference": contact["contact_attempt_id"],
                "reason": reason,
            })

    found.extend(_wrong_allocation_records(connection))

    promises = connection.execute(
        """
        SELECT p.promise_id, p.amount_minor, p.promised_at, c.loan_id
        FROM PromiseToPay p JOIN CollectionCase c ON c.case_id=p.case_id
        """
    ).fetchall()
    for promise in promises:
        arrears = calculate_loan_balance(
            promise["loan_id"], promise["promised_at"][:10]
        )["arrears_amount_minor"]
        if promise["amount_minor"] > arrears:
            found.append({
                "anomaly_type": "promise_exceeds_arrears",
                "record_reference": promise["promise_id"],
                "reason": (
                    f"Promise amount {promise['amount_minor']} exceeds "
                    f"arrears {arrears} in minor currency units when recorded."
                ),
            })

    disputed = connection.execute(
        "SELECT loan_id FROM LoanAccountStatus "
        "WHERE dispute_status='disputed' AND debt_status='confirmed'"
    ).fetchall()
    for account in disputed:
        found.append({
            "anomaly_type": "disputed_debt_confirmed",
            "record_reference": account["loan_id"],
            "reason": "Debt is marked disputed and confirmed simultaneously.",
        })

    detected_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    found_keys = {(item["anomaly_type"], item["record_reference"]) for item in found}
    with transaction(connection):
        for item in found:
            existing = connection.execute(
                "SELECT anomaly_id, first_detected_at FROM AnomalyRecord "
                "WHERE anomaly_type=? AND record_reference=?",
                (item["anomaly_type"], item["record_reference"]),
            ).fetchone()
            if existing:
                connection.execute(
                    "UPDATE AnomalyRecord SET reason=?, detection_status='active', "
                    "last_detected_at=? WHERE anomaly_id=?",
                    (item["reason"], detected_at, existing["anomaly_id"]),
                )
            else:
                latest = connection.execute(
                    "SELECT anomaly_id FROM AnomalyRecord "
                    "WHERE anomaly_id GLOB 'ANM-[0-9][0-9][0-9][0-9][0-9][0-9]' "
                    "ORDER BY CAST(substr(anomaly_id, 5) AS INTEGER) DESC LIMIT 1"
                ).fetchone()
                number = int(latest["anomaly_id"][4:]) + 1 if latest else 1
                if number > 999999:
                    raise ApiError("Anomaly identifier capacity has been reached.", 409, "id_capacity")
                connection.execute(
                    "INSERT INTO AnomalyRecord "
                    "(anomaly_id, anomaly_type, record_reference, reason, "
                    "detection_status, first_detected_at, last_detected_at) "
                    "VALUES (?, ?, ?, ?, 'active', ?, ?)",
                    (f"ANM-{number:06d}", item["anomaly_type"],
                     item["record_reference"], item["reason"], detected_at, detected_at),
                )
        for row in connection.execute(
            "SELECT anomaly_id, anomaly_type, record_reference "
            "FROM AnomalyRecord WHERE detection_status='active'"
        ).fetchall():
            if (row["anomaly_type"], row["record_reference"]) not in found_keys:
                connection.execute(
                    "UPDATE AnomalyRecord SET detection_status='resolved', "
                    "reason='Condition was not present in the latest detection run.', "
                    "last_detected_at=? WHERE anomaly_id=?",
                    (detected_at, row["anomaly_id"]),
                )
    return list_anomalies()


def list_anomalies(detection_status=None):
    if detection_status is not None and detection_status not in {"active", "resolved"}:
        raise ApiError("detection_status must be active or resolved.")
    query = "SELECT * FROM AnomalyRecord"
    params = ()
    if detection_status:
        query += " WHERE detection_status=?"
        params = (detection_status,)
    query += " ORDER BY anomaly_type, record_reference"
    return [dict(row) for row in get_db().execute(query, params).fetchall()]


def anomaly_report(as_of=None):
    records = detect_anomalies(as_of)
    active = [item for item in records if item["detection_status"] == "active"]
    counts = {name: 0 for name in _ANOMALIES}
    for item in active:
        counts[item["anomaly_type"]] += 1
    return {
        "as_of": as_of or date.today().isoformat(),
        "active_count": len(active),
        "counts_by_type": counts,
        "records": records,
        "ground_truth_used": False,
    }
