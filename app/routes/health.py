from flask import Blueprint, current_app, jsonify

from app.services.sheets_client import get_all_records

bp = Blueprint("health", __name__)


@bp.get("/health")
def health():
    return {"status": "ok"}


@bp.get("/dashboard-data")
def dashboard_data():
    config = current_app.config["APP_CONFIG"]
    data = get_all_records(config)
    return jsonify(data)


@bp.get("/")
def home():
    return "Server is running 🚀"
