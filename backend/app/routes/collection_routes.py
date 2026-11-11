from flask import Blueprint, jsonify, request

from app.services.collection_service import (
    get_collection_case,
    list_collection_cases,
    update_collection_case_status,
)


collection_bp = Blueprint(
    "collection_cases", __name__, url_prefix="/api/collection-cases"
)


@collection_bp.get("")
def collection_cases():
    return jsonify({"data": list_collection_cases()}), 200


@collection_bp.get("/<case_id>")
def collection_case_detail(case_id):
    return jsonify({"data": get_collection_case(case_id)}), 200


@collection_bp.patch("/<case_id>")
def collection_case_update(case_id):
    return jsonify({
        "data": update_collection_case_status(case_id, request.get_json())
    }), 200
