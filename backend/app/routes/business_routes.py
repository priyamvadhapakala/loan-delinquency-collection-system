from flask import Blueprint, jsonify, request

from app.services.anomaly_service import anomaly_report, detect_anomalies, list_anomalies
from app.services.business_service import (
    calculate_loan_balance,
    create_collection_case,
    delinquency_report,
    list_delinquency,
)
from app.services.compliance_service import (
    create_contact_attempt,
    create_contact_holiday,
    create_promise,
    evaluate_promises,
    get_account_status,
    get_contact_preference,
    list_audit_events,
    list_promises,
    set_account_status,
    set_contact_preference,
    update_promise_status,
)


business_bp = Blueprint("business", __name__, url_prefix="/api")


@business_bp.get("/delinquency")
def delinquency_summary():
    return jsonify({"data": list_delinquency(request.args.get("as_of"))}), 200


@business_bp.get("/loans/<loan_id>/balance")
def loan_balance(loan_id):
    return jsonify({
        "data": calculate_loan_balance(loan_id, request.args.get("as_of"))
    }), 200


@business_bp.get("/reports/delinquency")
def delinquency_report_get():
    return jsonify({"data": delinquency_report(request.args.get("as_of"))}), 200


@business_bp.post("/collection-cases")
def collection_case_create():
    case = create_collection_case(request.get_json())
    response = jsonify({"data": case})
    response.status_code = 201
    response.headers["Location"] = f"/api/collection-cases/{case['case_id']}"
    return response


@business_bp.get("/customers/<customer_id>/contact-preference")
def contact_preference_get(customer_id):
    return jsonify({"data": get_contact_preference(customer_id)}), 200


@business_bp.put("/customers/<customer_id>/contact-preference")
def contact_preference_put(customer_id):
    return jsonify({
        "data": set_contact_preference(customer_id, request.get_json())
    }), 200


@business_bp.post("/collection-cases/<case_id>/contact-attempts")
def contact_attempt_create(case_id):
    result = create_contact_attempt(case_id, request.get_json())
    return jsonify({"data": result}), 201


@business_bp.post("/contact-holidays/<holiday_date>")
def contact_holiday_create(holiday_date):
    return jsonify({"data": create_contact_holiday(holiday_date, request.get_json())}), 201


@business_bp.get("/loans/<loan_id>/account-status")
def account_status_get(loan_id):
    return jsonify({"data": get_account_status(loan_id)}), 200


@business_bp.put("/loans/<loan_id>/account-status")
def account_status_put(loan_id):
    return jsonify({"data": set_account_status(loan_id, request.get_json())}), 200


@business_bp.get("/promises")
def promises_get():
    return jsonify({"data": list_promises()}), 200


@business_bp.post("/collection-cases/<case_id>/promises")
def promise_create(case_id):
    promise = create_promise(case_id, request.get_json())
    response = jsonify({"data": promise})
    response.status_code = 201
    response.headers["Location"] = f"/api/promises/{promise['promise_id']}"
    return response


@business_bp.patch("/promises/<promise_id>")
def promise_update(promise_id):
    return jsonify({
        "data": update_promise_status(promise_id, request.get_json())
    }), 200


@business_bp.post("/promises/evaluate")
def promise_evaluate():
    body = request.get_json(silent=True) or {}
    if not isinstance(body, dict) or set(body) - {"as_of"}:
        return jsonify({"error": {
            "code": "invalid_request",
            "message": "A JSON object with optional as_of is required.",
        }}), 400
    return jsonify({"data": evaluate_promises(body.get("as_of"))}), 200


@business_bp.get("/audit-events")
def audit_events():
    return jsonify({"data": list_audit_events(
        request.args.get("entity_type"),
        request.args.get("entity_id"),
    )}), 200


@business_bp.get("/anomalies")
def anomalies_get():
    return jsonify({"data": list_anomalies(request.args.get("status"))}), 200


@business_bp.post("/anomalies/detect")
def anomalies_detect():
    body = request.get_json(silent=True) or {}
    if not isinstance(body, dict) or set(body) - {"as_of"}:
        return jsonify({"error": {
            "code": "invalid_request",
            "message": "A JSON object with optional as_of is required.",
        }}), 400
    return jsonify({"data": detect_anomalies(body.get("as_of"))}), 200


@business_bp.get("/reports/anomalies")
def anomalies_report():
    return jsonify({"data": anomaly_report(request.args.get("as_of"))}), 200
