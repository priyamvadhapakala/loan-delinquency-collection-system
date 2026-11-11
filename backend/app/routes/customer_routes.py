from flask import Blueprint, jsonify, request

from app.services.customer_service import (
    create_customer,
    get_customer,
    list_customers,
    update_customer,
)


customer_bp = Blueprint("customers", __name__, url_prefix="/api/customers")


@customer_bp.get("")
def customers():
    return jsonify({"data": list_customers()}), 200


@customer_bp.get("/<customer_id>")
def customer_detail(customer_id):
    return jsonify({"data": get_customer(customer_id)}), 200


@customer_bp.post("")
def customer_create():
    customer = create_customer(request.get_json())
    response = jsonify({"data": customer})
    response.status_code = 201
    response.headers["Location"] = f"/api/customers/{customer['customer_id']}"
    return response


@customer_bp.patch("/<customer_id>")
def customer_update(customer_id):
    return jsonify({"data": update_customer(customer_id, request.get_json())}), 200
