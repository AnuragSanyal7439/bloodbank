from flask import Blueprint, jsonify

from ..db import get_db


bp = Blueprint("health", __name__, url_prefix="/api")


@bp.get("/health")
def health():
    db = get_db()
    db.execute("SELECT 1").fetchone()
    return jsonify(
        {
            "status": "ok",
            "service": "bloodbank",
            "database": "connected",
        }
    )

