from datetime import datetime

from flask import Blueprint, jsonify, session
from werkzeug.security import generate_password_hash

from ..auth_utils import (
    VALID_ROLES,
    authenticate,
    clean_text,
    current_user,
    json_error,
    request_json,
    validate_email,
    validate_required,
)
from ..db import dict_from_row, get_db


bp = Blueprint("auth", __name__, url_prefix="/api/auth")


def public_user(user: dict | None) -> dict | None:
    if not user:
        return None
    return {
        "id": user["id"],
        "name": user["name"],
        "email": user["email"],
        "role": user["role"],
        "phone": user.get("phone"),
        "city": user.get("city"),
        "created_at": user.get("created_at"),
        "last_login_at": user.get("last_login_at"),
    }


@bp.post("/register")
def register():
    data = request_json()
    errors = validate_required(data, ["name", "email", "password", "role", "city"])
    email = clean_text(data.get("email", ""), 180).lower()
    password = str(data.get("password", ""))
    role = clean_text(data.get("role", ""), 40)

    if email and not validate_email(email):
        errors["email"] = "Enter a valid email address."
    if password and len(password) < 8:
        errors["password"] = "Password must be at least 8 characters."
    if role and role not in VALID_ROLES - {"blood_bank_admin", "super_admin"}:
        errors["role"] = "Choose donor, recipient, or hospital for public registration."
    if errors:
        return json_error("Please fix the highlighted fields.", 422, errors)

    db = get_db()
    now = datetime.utcnow().isoformat(timespec="seconds")
    try:
        cursor = db.execute(
            """
            INSERT INTO users (name, email, password_hash, role, phone, city, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                clean_text(data["name"], 120),
                email,
                generate_password_hash(password),
                role,
                clean_text(data.get("phone", ""), 30),
                clean_text(data["city"], 80),
                now,
            ),
        )
        user_id = int(cursor.lastrowid)

        if role == "donor":
            donor_errors = validate_required(data, ["age", "gender", "blood_group"])
            if donor_errors:
                raise ValueError("Donor registration requires age, gender, and blood group.")
            db.execute(
                """
                INSERT INTO donor_profiles
                    (user_id, age, gender, blood_group, last_donation_date, medical_notes, availability_status, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    int(data["age"]),
                    clean_text(data["gender"], 40),
                    clean_text(data["blood_group"], 5),
                    clean_text(data.get("last_donation_date", ""), 20) or None,
                    clean_text(data.get("medical_notes", ""), 500),
                    clean_text(data.get("availability_status", "available"), 30).lower(),
                    now,
                ),
            )
        elif role == "hospital":
            db.execute(
                """
                INSERT INTO hospital_profiles
                    (user_id, hospital_name, registration_id, address, contact_person, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    clean_text(data.get("hospital_name") or data["name"], 160),
                    clean_text(data.get("registration_id", ""), 80),
                    clean_text(data.get("address", ""), 260),
                    clean_text(data.get("contact_person", data["name"]), 120),
                    now,
                ),
            )

        db.commit()
    except Exception as exc:
        db.rollback()
        if "UNIQUE constraint failed" in str(exc):
            return json_error("An account with this email already exists.", 409)
        return json_error(str(exc), 422)

    user = dict_from_row(db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone())
    session.clear()
    session["user_id"] = user_id
    return jsonify({"user": public_user(user), "message": "Registration successful."}), 201


@bp.post("/login")
def login():
    data = request_json()
    email = clean_text(data.get("email", ""), 180).lower()
    password = str(data.get("password", ""))
    user = authenticate(email, password)
    if not user:
        return json_error("Invalid email or password.", 401)

    now = datetime.utcnow().isoformat(timespec="seconds")
    db = get_db()
    db.execute("UPDATE users SET last_login_at = ? WHERE id = ?", (now, user["id"]))
    db.commit()
    user["last_login_at"] = now
    session.clear()
    session["user_id"] = user["id"]
    return jsonify({"user": public_user(user), "message": "Welcome back."})


@bp.post("/logout")
def logout():
    session.clear()
    return jsonify({"message": "Logged out."})


@bp.get("/me")
def me():
    return jsonify({"user": public_user(current_user())})

