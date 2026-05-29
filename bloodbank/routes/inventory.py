from datetime import date, datetime

from flask import Blueprint, jsonify

from ..auth_utils import clean_text, current_user, json_error, login_required, request_json, roles_required
from ..db import dict_from_row, get_db
from ..services.compatibility import normalize_blood_group
from ..services.inventory import stock_status


bp = Blueprint("inventory", __name__, url_prefix="/api/inventory")


def sync_expired_units(db) -> int:
    today = date.today().isoformat()
    rows = db.execute(
        """
        SELECT blood_group, COUNT(*) AS count
        FROM blood_units
        WHERE status = 'available' AND expiry_date < ?
        GROUP BY blood_group
        """,
        (today,),
    ).fetchall()
    total_expired = 0
    now = datetime.utcnow().isoformat(timespec="seconds")
    for row in rows:
        group = row["blood_group"]
        count = int(row["count"])
        total_expired += count
        inventory = dict_from_row(db.execute("SELECT * FROM blood_inventory WHERE blood_group = ?", (group,)).fetchone())
        available = max(0, int(inventory["available_units"]) - count)
        expired = int(inventory["expired_units"]) + count
        db.execute(
            """
            UPDATE blood_inventory
            SET available_units = ?, expired_units = ?, last_updated_at = ?
            WHERE blood_group = ?
            """,
            (available, expired, now, group),
        )
    if total_expired:
        db.execute("UPDATE blood_units SET status = 'expired' WHERE status = 'available' AND expiry_date < ?", (today,))
        db.commit()
    return total_expired


@bp.get("")
@login_required
def list_inventory():
    db = get_db()
    sync_expired_units(db)
    rows = db.execute("SELECT * FROM blood_inventory ORDER BY blood_group").fetchall()
    items = []
    for row in rows:
        item = dict(row)
        item["stock_status"] = stock_status(item)
        items.append(item)
    return jsonify({"items": items})


@bp.patch("/<blood_group>")
@roles_required("blood_bank_admin")
def update_inventory(blood_group: str):
    user = current_user()
    try:
        group = normalize_blood_group(blood_group)
    except ValueError as exc:
        return json_error(str(exc), 422)

    data = request_json()
    allowed_fields = ["available_units", "reserved_units", "expired_units", "low_stock_threshold"]
    updates = {}
    for field in allowed_fields:
        if field in data:
            try:
                value = int(data[field])
                if value < 0:
                    raise ValueError
                updates[field] = value
            except (TypeError, ValueError):
                return json_error(f"{field.replace('_', ' ').title()} must be a non-negative number.", 422)

    if not updates:
        return json_error("No inventory fields were provided.", 422)

    db = get_db()
    current = dict_from_row(db.execute("SELECT * FROM blood_inventory WHERE blood_group = ?", (group,)).fetchone())
    if not current:
        return json_error("Inventory row not found.", 404)

    now = datetime.utcnow().isoformat(timespec="seconds")
    set_clause = ", ".join([f"{field} = ?" for field in updates] + ["last_updated_at = ?"])
    params = [*updates.values(), now, group]
    db.execute(f"UPDATE blood_inventory SET {set_clause} WHERE blood_group = ?", params)
    db.execute(
        """
        INSERT INTO audit_logs (actor_id, action, entity_type, entity_id, details, created_at)
        VALUES (?, 'inventory_changed', 'blood_inventory', ?, ?, ?)
        """,
        (user["id"], current["id"], f"{group} inventory updated: {updates}", now),
    )
    db.commit()

    updated = dict_from_row(db.execute("SELECT * FROM blood_inventory WHERE blood_group = ?", (group,)).fetchone())
    updated["stock_status"] = stock_status(updated)
    return jsonify({"item": updated, "message": f"{group} inventory updated."})

