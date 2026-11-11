from flask import Blueprint, jsonify, request

from app.services.payment_service import list_payments, record_payment


payment_bp = Blueprint("payments", __name__, url_prefix="/api/payments")


@payment_bp.get("")
def payment_history():
    loan_id = request.args.get("loan_id")
    return jsonify({"data": list_payments(loan_id)}), 200


@payment_bp.post("")
def payment_create():
    payment = record_payment(request.get_json())
    response = jsonify({"data": payment})
    response.status_code = 201
    response.headers["Location"] = f"/api/payments?loan_id={payment['loan_id']}"
    return response
