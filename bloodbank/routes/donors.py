from datetime import datetime

from flask import Blueprint, jsonify, request

from ..auth_utils import clean_text, current_user, json_error, login_required, request_json, roles_required
from ..db import dict_from_row, get_db
from ..services.compatibility import normalize_blood_group
from ..services.eligibility import donor_eligibility


bp = Blueprint("donors", __name__, url_prefix="/api/donors")


def donor_payload(row: dict) -> dict:
    eligibility = donor_eligibility(row.get("last_donation_date"), row.get("age"), row.get("availability_status"))
    fields = [
        row.get("name"),
        row.get("email"),
        row.get("phone"),
        row.get("city"),
        row.get("age"),
        row.get("gender"),
        row.get("blood_group"),
        row.get("medical_notes"),
        row.get("availability_status"),
    ]
    completion = round(sum(1 for field in fields if field not in (None, "")) / len(fields) * 100)
    return {
        **row,
        "eligibility": eligibility,
        "profile_completion": completion,
    }


@bp.get("")
@login_required
def list_donors():
    search = clean_text(request.args.get("search", ""), 80)
    city = clean_text(request.args.get("city", ""), 80)
    blood_group = clean_text(request.args.get("blood_group", ""), 5)
    sort = clean_text(request.args.get("sort", "newest"), 30)
    page = max(1, int(request.args.get("page", 1)))
    per_page = min(50, max(5, int(request.args.get("per_page", 12))))

    conditions = ["users.is_active = 1"]
    params = []
    if search:
        conditions.append("(users.name LIKE ? OR users.email LIKE ? OR users.phone LIKE ?)")
        params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])
    if city:
        conditions.append("users.city = ?")
        params.append(city)
    if blood_group:
        conditions.append("donor_profiles.blood_group = ?")
        params.append(blood_group)

    order_by = {
        "city": "users.city ASC, users.name ASC",
        "blood_group": "donor_profiles.blood_group ASC, users.name ASC",
        "eligible": "donor_profiles.last_donation_date ASC, users.name ASC",
        "newest": "users.created_at DESC",
    }.get(sort, "users.created_at DESC")

    db = get_db()
    total = db.execute(
        f"""
        SELECT COUNT(*) AS count
        FROM donor_profiles
        JOIN users ON users.id = donor_profiles.user_id
        WHERE {' AND '.join(conditions)}
        """,
        params,
    ).fetchone()["count"]
    rows = db.execute(
        f"""
        SELECT donor_profiles.*, users.name, users.email, users.phone, users.city, users.created_at
        FROM donor_profiles
        JOIN users ON users.id = donor_profiles.user_id
        WHERE {' AND '.join(conditions)}
        ORDER BY {order_by}
        LIMIT ? OFFSET ?
        """,
        (*params, per_page, (page - 1) * per_page),
    ).fetchall()
    return jsonify(
        {
            "items": [donor_payload(dict(row)) for row in rows],
            "pagination": {"page": page, "per_page": per_page, "total": total},
        }
    )


@bp.get("/me")
@roles_required("donor")
def my_profile():
    user = current_user()
    row = get_db().execute(
        """
        SELECT donor_profiles.*, users.name, users.email, users.phone, users.city, users.created_at
        FROM donor_profiles
        JOIN users ON users.id = donor_profiles.user_id
        WHERE users.id = ?
        """,
        (user["id"],),
    ).fetchone()
    return jsonify({"profile": donor_payload(dict_from_row(row)) if row else None})


@bp.put("/me")
@roles_required("donor")
def update_my_profile():
    user = current_user()
    data = request_json()
    try:
        age = int(data.get("age"))
        if age < 18 or age > 65:
            return json_error("Age must be between 18 and 65.", 422)
        blood_group = normalize_blood_group(data.get("blood_group", ""))
    except (TypeError, ValueError) as exc:
        return json_error(str(exc), 422)

    now = datetime.utcnow().isoformat(timespec="seconds")
    db = get_db()
    db.execute(
        """
        UPDATE users
        SET name = ?, phone = ?, city = ?
        WHERE id = ?
        """,
        (
            clean_text(data.get("name") or user["name"], 120),
            clean_text(data.get("phone"), 30),
            clean_text(data.get("city") or user["city"], 80),
            user["id"],
        ),
    )
    db.execute(
        """
        UPDATE donor_profiles
        SET age = ?, gender = ?, blood_group = ?, last_donation_date = ?,
            medical_notes = ?, availability_status = ?, updated_at = ?
        WHERE user_id = ?
        """,
        (
            age,
            clean_text(data.get("gender"), 40),
            blood_group,
            clean_text(data.get("last_donation_date"), 20) or None,
            clean_text(data.get("medical_notes"), 500),
            clean_text(data.get("availability_status", "available"), 30).lower(),
            now,
            user["id"],
        ),
    )
    db.execute(
        """
        INSERT INTO audit_logs (actor_id, action, entity_type, entity_id, details, created_at)
        VALUES (?, 'updated_donor_profile', 'donor_profile', ?, 'Donor updated profile details.', ?)
        """,
        (user["id"], user["id"], now),
    )
    db.commit()
    return my_profile()

