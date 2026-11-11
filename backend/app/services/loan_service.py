from app.services.errors import NotFoundError
from app.utils.database import get_db


def list_loans(customer_id=None):
    connection = get_db()
    if customer_id is not None:
        customer = connection.execute(
            "SELECT 1 FROM Customer WHERE customer_id = ?", (customer_id,)
        ).fetchone()
        if customer is None:
            raise NotFoundError("Customer was not found.")
    query = (
        "SELECT loan_id, customer_id, loan_reference, principal_amount_minor, "
        "currency_code, annual_interest_rate_bps, term_months, "
        "disbursement_date, first_due_date, loan_status, created_at "
        "FROM Loan"
    )
    params = ()
    if customer_id is not None:
        query += " WHERE customer_id = ?"
        params = (customer_id,)
    query += " ORDER BY loan_id"
    return [dict(row) for row in connection.execute(query, params).fetchall()]


def get_loan(loan_id):
    row = get_db().execute(
        "SELECT loan_id, customer_id, loan_reference, principal_amount_minor, "
        "currency_code, annual_interest_rate_bps, term_months, "
        "disbursement_date, first_due_date, loan_status, created_at "
        "FROM Loan WHERE loan_id = ?",
        (loan_id,),
    ).fetchone()
    if row is None:
        raise NotFoundError("Loan was not found.")
    return dict(row)


def _installment_select():
    return """
        SELECT i.installment_id, i.loan_id, i.installment_number, i.due_date,
               i.scheduled_principal_minor, i.scheduled_interest_minor,
               COALESCE(a.allocated_principal_minor, 0) AS paid_principal_minor,
               COALESCE(a.allocated_interest_minor, 0) AS paid_interest_minor,
               i.scheduled_principal_minor - COALESCE(a.allocated_principal_minor, 0)
                   AS remaining_principal_minor,
               i.scheduled_interest_minor - COALESCE(a.allocated_interest_minor, 0)
                   AS remaining_interest_minor
        FROM Installment i
        LEFT JOIN (
            SELECT pa.installment_id,
                   SUM(pa.allocated_principal_minor) AS allocated_principal_minor,
                   SUM(pa.allocated_interest_minor) AS allocated_interest_minor
            FROM PaymentAllocation pa
            JOIN Payment p ON p.payment_id = pa.payment_id
            WHERE pa.allocation_status = 'active' AND p.payment_status = 'posted'
            GROUP BY pa.installment_id
        ) a ON a.installment_id = i.installment_id
    """


def list_installments(loan_id=None):
    connection = get_db()
    if loan_id is not None:
        if connection.execute(
            "SELECT 1 FROM Loan WHERE loan_id = ?", (loan_id,)
        ).fetchone() is None:
            raise NotFoundError("Loan was not found.")
    query = _installment_select()
    params = ()
    if loan_id is not None:
        query += " WHERE i.loan_id = ?"
        params = (loan_id,)
    query += " ORDER BY i.loan_id, i.installment_number"
    return [
        dict(row)
        for row in connection.execute(query, params).fetchall()
    ]


def get_installment(installment_id):
    row = get_db().execute(
        _installment_select() + " WHERE i.installment_id = ?",
        (installment_id,),
    ).fetchone()
    if row is None:
        raise NotFoundError("Installment was not found.")
    return dict(row)
