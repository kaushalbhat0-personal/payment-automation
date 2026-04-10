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

@bp.get("/dashboard-summary")
def dashboard_summary():
    config = current_app.config["APP_CONFIG"]
    rows = get_all_records(config)

    total_revenue = 0
    unique_students = set()
    batch_revenue = {}
    mode_distribution = {}

    for row in rows:
        amount = row.get("Amount", 0) or 0
        phone = str(row.get("Phone", "")).strip()
        batch = row.get("Preferred Batch", "Unknown")
        mode = row.get("Mode", "Unknown")

        # Total revenue
        total_revenue += amount

        # Unique students (EMI safe)
        if phone:
            unique_students.add(phone)

        # Batch revenue
        if batch not in batch_revenue:
            batch_revenue[batch] = 0
        batch_revenue[batch] += amount

        # Mode distribution
        if mode not in mode_distribution:
            mode_distribution[mode] = 0
        mode_distribution[mode] += 1

    return jsonify({
        "total_students": len(unique_students),
        "total_revenue": total_revenue,
        "batch_revenue": batch_revenue,
        "mode_distribution": mode_distribution
    })

@bp.get("/")
def home():
    return "Server is running 🚀"
