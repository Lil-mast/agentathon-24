from flask import Blueprint, current_app, request

from app.services.bq import list_amendments


amendments_bp = Blueprint("amendments", __name__)


@amendments_bp.get("/api/amendments")
def get_amendments():
    ward = request.args.get("ward", "").strip()
    rows = list_amendments(current_app.config, ward=ward if ward else None, limit=50)
    return {"items": rows, "count": len(rows)}, 200
