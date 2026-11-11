from flask import Blueprint, jsonify, request

from app.services.loan_service import get_loan, list_loans


loan_bp = Blueprint("loans", __name__, url_prefix="/api")


@loan_bp.get("/loans")
def loans():
    customer_id = request.args.get("customer_id")
    return jsonify({"data": list_loans(customer_id)}), 200


@loan_bp.get("/loans/<loan_id>")
def loan_detail(loan_id):
    return jsonify({"data": get_loan(loan_id)}), 200


@loan_bp.get("/customers/<customer_id>/loans")
def customer_loans(customer_id):
    return jsonify({"data": list_loans(customer_id)}), 200
