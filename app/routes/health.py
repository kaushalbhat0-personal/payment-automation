from flask import Blueprint, current_app, jsonify, send_from_directory
import os

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

import os

@bp.route("/")
def serve_react():
    template_folder = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "build")
    )
    return send_from_directory(template_folder, "index.html")


@bp.route("/<path:path>")
def serve_static_files(path):
    template_folder = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "build")
    )
    full_path = os.path.join(template_folder, path)
    if path != "" and os.path.exists(full_path):
        return send_from_directory(template_folder, path)
    else:
        return send_from_directory(template_folder, "index.html")
   