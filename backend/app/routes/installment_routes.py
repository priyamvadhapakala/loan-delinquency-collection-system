from flask import Blueprint, jsonify

from app.services.loan_service import (
    get_installment,
    list_installments,
)


installment_bp = Blueprint("installments", __name__, url_prefix="/api")


@installment_bp.get("/installments")
def installments():
    return jsonify({"data": list_installments()}), 200


@installment_bp.get("/installments/<installment_id>")
def installment_detail(installment_id):
    return jsonify({"data": get_installment(installment_id)}), 200


@installment_bp.get("/loans/<loan_id>/installments")
def loan_installments(loan_id):
    return jsonify({"data": list_installments(loan_id)}), 200
