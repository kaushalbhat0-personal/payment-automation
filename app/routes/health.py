from flask import Blueprint, current_app, jsonify, send_from_directory
import os

from app.services.sheets_client import get_all_records

bp = Blueprint("health", __name__)


@bp.get("/health")
def health():
    """
    Health Check Endpoint
    ---
    get:
      tags:
        - Health
      summary: Health check to verify that the server is running
      description: Returns status ok if the server is up.
      responses:
        200:
          description: Service is healthy
          content:
            application/json:
              example:
                status: ok
    """
    return {"status": "ok"}


@bp.get("/dashboard-data")
def dashboard_data():
    """
    Get dashboard data for all payment records
    ---
    get:
      tags:
        - Dashboard
      summary: Retrieve payment records for the dashboard
      description: Returns a list of all sheet records for displaying in the dashboard.
      responses:
        200:
          description: List of payment records
          content:
            application/json:
              schema:
                type: array
                items:
                  type: object
                  additionalProperties: true
              example:
                [
                  {
                    "Payment ID": "pay_xyz123",
                    "Name": "Alice",
                    "Email": "alice@example.com",
                    "Phone": "9999111222",
                    "Amount": 50000,
                    "Status": "captured",
                    "Preferred Batch": "Weekday Batch (9am-12pm)",
                    "Mode": "Offline",
                    "Captured At IST": "2024-06-11 14:23:15"
                  }
                ]
    """
    config = current_app.config["APP_CONFIG"]
    data = get_all_records(config)
    return jsonify(data)

@bp.get("/dashboard-summary")
def dashboard_summary():
    """
    Get dashboard analytics summary
    ---
    responses:
      200:
        description: Returns aggregated dashboard data
        examples:
          application/json:
            {
              "total_students": 71,
              "total_revenue": 1422295,
              "batch_revenue": {
                "Weekday Batch": 1057463,
                "Weekend Batch": 339389
              },
              "mode_distribution": {
                "Online": 75,
                "Offline": 25
              }
            }
    """
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
    """
    Serve the React app main entrypoint.
    ---
    tags:
      - Frontend
    responses:
      200:
        description: Returns the React app's index.html
        content:
          text/html:
            schema:
              type: string
    """
    template_folder = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "build")
    )
    return send_from_directory(template_folder, "index.html")


@bp.route("/<path:path>")
def serve_static_files(path):
    """
    Serve static files from the React build directory.

    ---
    tags:
      - Frontend
    parameters:
      - name: path
        in: path
        required: true
        description: The path of the static asset to serve
        schema:
          type: string
    responses:
      200:
        description: The requested static file or React app's index.html
        content:
          text/html:
            schema:
              type: string
    """
    template_folder = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "build")
    )
    full_path = os.path.join(template_folder, path)
    if path != "" and os.path.exists(full_path):
        return send_from_directory(template_folder, path)
    else:
        return send_from_directory(template_folder, "index.html")
   