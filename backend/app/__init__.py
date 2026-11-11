import logging
import sqlite3
from pathlib import Path

from flask import Flask, jsonify, request
from werkzeug.exceptions import HTTPException

from app.routes import register_blueprints
from app.services.errors import ApiError
from app.utils.database import close_db, get_db


PROJECT_ROOT = Path(__file__).resolve().parents[2]


LOCAL_FRONTEND_ORIGIN = "http://127.0.0.1:5500"


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_mapping(
        DATABASE=str(PROJECT_ROOT / "database" / "loan_delinquency.db"),
        JSON_SORT_KEYS=False,
    )
    if test_config:
        app.config.update(test_config)

    app.teardown_appcontext(close_db)
    app.config["ADDITIVE_MIGRATIONS_APPLIED"] = False

    register_blueprints(app)

    @app.after_request
    def add_local_frontend_cors_headers(response):
        if request.headers.get("Origin") == LOCAL_FRONTEND_ORIGIN:
            response.headers["Access-Control-Allow-Origin"] = LOCAL_FRONTEND_ORIGIN
            response.headers["Access-Control-Allow-Methods"] = (
                "GET, POST, PUT, PATCH, OPTIONS"
            )
            response.headers["Access-Control-Allow-Headers"] = "Content-Type"
            response.headers["Access-Control-Max-Age"] = "600"
            response.vary.add("Origin")
        return response

    @app.get("/api/health")
    def health():
        get_db().execute("SELECT 1").fetchone()
        return jsonify({"status": "ok"}), 200

    @app.errorhandler(ApiError)
    def handle_api_error(error):
        return jsonify({
            "error": {
                "code": error.code,
                "message": error.message,
            }
        }), error.status_code

    @app.errorhandler(sqlite3.Error)
    def handle_database_error(error):
        app.logger.exception("Database operation failed")
        return jsonify({
            "error": {
                "code": "database_error",
                "message": "A database operation could not be completed.",
            }
        }), 503

    @app.errorhandler(HTTPException)
    def handle_http_error(error):
        return jsonify({
            "error": {
                "code": error.name.lower().replace(" ", "_"),
                "message": error.description,
            }
        }), error.code

    @app.errorhandler(Exception)
    def handle_unexpected_error(error):
        app.logger.exception("Unexpected application error")
        return jsonify({
            "error": {
                "code": "internal_server_error",
                "message": "An unexpected error occurred.",
            }
        }), 500

    return app


__all__ = ["create_app"]
