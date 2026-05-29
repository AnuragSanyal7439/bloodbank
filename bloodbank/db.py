from datetime import date, datetime, timedelta
import sqlite3

from flask import current_app, g
from werkzeug.security import generate_password_hash

from .services.compatibility import BLOOD_GROUPS


def dict_from_row(row: sqlite3.Row | None) -> dict | None:
    return dict(row) if row else None


def dicts_from_rows(rows: list[sqlite3.Row]) -> list[dict]:
    return [dict(row) for row in rows]


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        db_path = current_app.config["DATABASE_PATH"]
        db_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        g.db = connection
    return g.db


def close_db(_error: Exception | None = None) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.close()


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE COLLATE NOCASE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('donor', 'recipient', 'hospital', 'blood_bank_admin', 'super_admin')),
    phone TEXT,
    city TEXT,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    last_login_at TEXT
);

CREATE TABLE IF NOT EXISTS donor_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL UNIQUE,
    age INTEGER NOT NULL,
    gender TEXT NOT NULL,
    blood_group TEXT NOT NULL,
    last_donation_date TEXT,
    medical_notes TEXT,
    availability_status TEXT NOT NULL DEFAULT 'available',
    verified INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS hospital_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL UNIQUE,
    hospital_name TEXT NOT NULL,
    registration_id TEXT,
    address TEXT,
    contact_person TEXT,
    verified INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS blood_inventory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    blood_group TEXT NOT NULL UNIQUE,
    available_units INTEGER NOT NULL DEFAULT 0,
    reserved_units INTEGER NOT NULL DEFAULT 0,
    expired_units INTEGER NOT NULL DEFAULT 0,
    low_stock_threshold INTEGER NOT NULL DEFAULT 5,
    last_updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS blood_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    requester_id INTEGER NOT NULL,
    patient_name TEXT NOT NULL,
    blood_group TEXT NOT NULL,
    units_required INTEGER NOT NULL,
    hospital_name TEXT NOT NULL,
    city TEXT NOT NULL,
    urgency TEXT NOT NULL CHECK (urgency IN ('Normal', 'Urgent', 'Critical')),
    required_at TEXT NOT NULL,
    contact_details TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'Pending' CHECK (status IN ('Pending', 'Matched', 'Fulfilled', 'Cancelled')),
    admin_notes TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (requester_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS request_matches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id INTEGER NOT NULL,
    donor_id INTEGER NOT NULL,
    score INTEGER NOT NULL,
    reason TEXT,
    created_at TEXT NOT NULL,
    UNIQUE (request_id, donor_id),
    FOREIGN KEY (request_id) REFERENCES blood_requests(id) ON DELETE CASCADE,
    FOREIGN KEY (donor_id) REFERENCES donor_profiles(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS blood_donations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    donor_id INTEGER NOT NULL,
    blood_group TEXT NOT NULL,
    units INTEGER NOT NULL,
    donation_date TEXT NOT NULL,
    center TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'Pending' CHECK (status IN ('Pending', 'Accepted', 'Rejected')),
    verified_by INTEGER,
    verified_at TEXT,
    notes TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (donor_id) REFERENCES donor_profiles(id),
    FOREIGN KEY (verified_by) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS blood_units (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    donation_id INTEGER,
    donor_id INTEGER,
    blood_group TEXT NOT NULL,
    collection_date TEXT NOT NULL,
    expiry_date TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'available' CHECK (status IN ('available', 'reserved', 'used', 'expired')),
    created_at TEXT NOT NULL,
    FOREIGN KEY (donation_id) REFERENCES blood_donations(id),
    FOREIGN KEY (donor_id) REFERENCES donor_profiles(id)
);

CREATE TABLE IF NOT EXISTS appointments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    donor_id INTEGER NOT NULL,
    center TEXT NOT NULL,
    appointment_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'Pending' CHECK (status IN ('Pending', 'Approved', 'Rescheduled', 'Cancelled', 'Completed')),
    admin_notes TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (donor_id) REFERENCES donor_profiles(id)
);

CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    title TEXT NOT NULL,
    message TEXT NOT NULL,
    type TEXT NOT NULL DEFAULT 'info',
    channel TEXT NOT NULL DEFAULT 'in_app',
    related_type TEXT,
    related_id INTEGER,
    is_read INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    actor_id INTEGER,
    action TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id INTEGER,
    details TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (actor_id) REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_users_role_city ON users(role, city);
CREATE INDEX IF NOT EXISTS idx_donor_blood_city ON donor_profiles(blood_group, availability_status);
CREATE INDEX IF NOT EXISTS idx_requests_status_urgency ON blood_requests(status, urgency);
CREATE INDEX IF NOT EXISTS idx_requests_city_blood ON blood_requests(city, blood_group);
CREATE INDEX IF NOT EXISTS idx_units_expiry_status ON blood_units(expiry_date, status);
CREATE INDEX IF NOT EXISTS idx_appointments_status_date ON appointments(status, appointment_at);
CREATE INDEX IF NOT EXISTS idx_notifications_user_read ON notifications(user_id, is_read);
"""


def init_db(seed: bool = True) -> None:
    db = get_db()
    db.executescript(SCHEMA_SQL)
    ensure_inventory_rows(db)
    if seed:
        seed_database(db)
    db.commit()


def ensure_inventory_rows(db: sqlite3.Connection) -> None:
    now = datetime.utcnow().isoformat(timespec="seconds")
    threshold = current_app.config["DEFAULT_LOW_STOCK_THRESHOLD"]
    for group in BLOOD_GROUPS:
        db.execute(
            """
            INSERT OR IGNORE INTO blood_inventory
                (blood_group, available_units, reserved_units, expired_units, low_stock_threshold, last_updated_at)
            VALUES (?, 0, 0, 0, ?, ?)
            """,
            (group, threshold, now),
        )


def seed_database(db: sqlite3.Connection) -> None:
    has_users = db.execute("SELECT COUNT(*) AS count FROM users").fetchone()["count"]
    if has_users:
        return

    now = datetime.utcnow().isoformat(timespec="seconds")
    today = date.today()

    def add_user(name, email, password, role, phone, city):
        cursor = db.execute(
            """
            INSERT INTO users (name, email, password_hash, role, phone, city, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (name, email, generate_password_hash(password), role, phone, city, now),
        )
        return int(cursor.lastrowid)

    donor_user_id = add_user("Aarav Donor", "donor@bloodbank.demo", "Donor@123", "donor", "9876500001", "Pune")
    recipient_id = add_user("Riya Patient", "recipient@bloodbank.demo", "Patient@123", "recipient", "9876500002", "Pune")
    hospital_user_id = add_user("CityCare Hospital", "hospital@bloodbank.demo", "Hospital@123", "hospital", "9876500003", "Mumbai")
    admin_id = add_user("Blood Bank Admin", "admin@bloodbank.demo", "Admin@123", "blood_bank_admin", "9876500004", "Pune")
    super_id = add_user("Super Admin", "superadmin@bloodbank.demo", "Super@123", "super_admin", "9876500005", "Delhi")

    donor_profiles = [
        (donor_user_id, 24, "Male", "O-", (today - timedelta(days=130)).isoformat(), "Healthy, regular donor.", "available", 1),
        (add_user("Nisha Kapoor", "nisha@bloodbank.demo", "Donor@123", "donor", "9876500102", "Pune"), 29, "Female", "A+", (today - timedelta(days=100)).isoformat(), "No recent medication.", "available", 1),
        (add_user("Kabir Singh", "kabir@bloodbank.demo", "Donor@123", "donor", "9876500103", "Mumbai"), 32, "Male", "B+", (today - timedelta(days=45)).isoformat(), "Cooldown active.", "available", 1),
        (add_user("Meera Joshi", "meera@bloodbank.demo", "Donor@123", "donor", "9876500104", "Delhi"), 27, "Female", "AB+", None, "First-time donor.", "available", 1),
        (add_user("Ishaan Rao", "ishaan@bloodbank.demo", "Donor@123", "donor", "9876500105", "Pune"), 35, "Male", "A-", (today - timedelta(days=180)).isoformat(), "Eligible.", "available", 1),
        (add_user("Anika Sen", "anika@bloodbank.demo", "Donor@123", "donor", "9876500106", "Mumbai"), 22, "Female", "B-", (today - timedelta(days=120)).isoformat(), "Available weekends.", "available", 1),
        (add_user("Dev Patel", "dev@bloodbank.demo", "Donor@123", "donor", "9876500107", "Bengaluru"), 41, "Male", "O+", (today - timedelta(days=96)).isoformat(), "Eligible.", "available", 1),
        (add_user("Sara Ali", "sara@bloodbank.demo", "Donor@123", "donor", "9876500108", "Pune"), 30, "Female", "AB-", (today - timedelta(days=70)).isoformat(), "Travelling this month.", "unavailable", 1),
    ]

    donor_ids = []
    for profile in donor_profiles:
        cursor = db.execute(
            """
            INSERT INTO donor_profiles
                (user_id, age, gender, blood_group, last_donation_date, medical_notes, availability_status, verified, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (*profile, now),
        )
        donor_ids.append(int(cursor.lastrowid))

    db.execute(
        """
        INSERT INTO hospital_profiles
            (user_id, hospital_name, registration_id, address, contact_person, verified, updated_at)
        VALUES (?, ?, ?, ?, ?, 1, ?)
        """,
        (hospital_user_id, "CityCare Multi Speciality Hospital", "MH-HSP-2026-118", "Andheri East, Mumbai", "Dr. Priya Nair", now),
    )

    inventory_seed = {
        "A+": (18, 3, 1, 6),
        "A-": (4, 1, 0, 5),
        "B+": (12, 2, 0, 6),
        "B-": (3, 1, 1, 5),
        "AB+": (8, 0, 0, 4),
        "AB-": (2, 0, 0, 4),
        "O+": (21, 4, 2, 8),
        "O-": (5, 2, 0, 6),
    }
    for group, values in inventory_seed.items():
        db.execute(
            """
            UPDATE blood_inventory
            SET available_units = ?, reserved_units = ?, expired_units = ?, low_stock_threshold = ?, last_updated_at = ?
            WHERE blood_group = ?
            """,
            (*values, now, group),
        )

    request_data = [
        (recipient_id, "Rohan Mehta", "O-", 2, "Ruby Hall Clinic", "Pune", "Critical", (datetime.utcnow() + timedelta(hours=8)).isoformat(timespec="minutes"), "Emergency desk: 9876500201", "Pending"),
        (hospital_user_id, "Asha Gupta", "A+", 3, "CityCare Multi Speciality Hospital", "Mumbai", "Urgent", (datetime.utcnow() + timedelta(days=1)).isoformat(timespec="minutes"), "Blood coordinator: 9876500202", "Matched"),
        (hospital_user_id, "Vikram Bose", "B-", 1, "CityCare Multi Speciality Hospital", "Mumbai", "Normal", (datetime.utcnow() + timedelta(days=3)).isoformat(timespec="minutes"), "Ward 4B: 9876500203", "Pending"),
        (recipient_id, "Neha Kulkarni", "AB-", 1, "Sahyadri Hospital", "Pune", "Urgent", (datetime.utcnow() + timedelta(days=2)).isoformat(timespec="minutes"), "Family contact: 9876500204", "Fulfilled"),
    ]
    request_ids = []
    for item in request_data:
        cursor = db.execute(
            """
            INSERT INTO blood_requests
                (requester_id, patient_name, blood_group, units_required, hospital_name, city, urgency, required_at, contact_details, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (*item, now, now),
        )
        request_ids.append(int(cursor.lastrowid))

    donation_data = [
        (donor_ids[0], "O-", 1, (today - timedelta(days=130)).isoformat(), "Pune Central Blood Bank", "Accepted", admin_id, (today - timedelta(days=130)).isoformat(), "Seeded verified donation"),
        (donor_ids[1], "A+", 1, (today - timedelta(days=100)).isoformat(), "Pune Central Blood Bank", "Accepted", admin_id, (today - timedelta(days=100)).isoformat(), "Seeded verified donation"),
        (donor_ids[2], "B+", 1, (today - timedelta(days=45)).isoformat(), "Mumbai City Blood Bank", "Accepted", admin_id, (today - timedelta(days=45)).isoformat(), "Seeded verified donation"),
    ]
    for donation in donation_data:
        cursor = db.execute(
            """
            INSERT INTO blood_donations
                (donor_id, blood_group, units, donation_date, center, status, verified_by, verified_at, notes, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (*donation, now),
        )
        donation_id = int(cursor.lastrowid)
        db.execute(
            """
            INSERT INTO blood_units
                (donation_id, donor_id, blood_group, collection_date, expiry_date, status, created_at)
            VALUES (?, ?, ?, ?, ?, 'available', ?)
            """,
            (donation_id, donation[0], donation[1], donation[3], (date.fromisoformat(donation[3]) + timedelta(days=42)).isoformat(), now),
        )

    appointment_data = [
        (donor_ids[0], "Pune Central Blood Bank", (datetime.utcnow() + timedelta(days=5, hours=2)).isoformat(timespec="minutes"), "Approved", "Bring donor ID."),
        (donor_ids[4], "Pune Central Blood Bank", (datetime.utcnow() + timedelta(days=2, hours=5)).isoformat(timespec="minutes"), "Pending", None),
        (donor_ids[5], "Mumbai City Blood Bank", (datetime.utcnow() + timedelta(days=4, hours=1)).isoformat(timespec="minutes"), "Approved", "Slot confirmed."),
    ]
    for appointment in appointment_data:
        db.execute(
            """
            INSERT INTO appointments
                (donor_id, center, appointment_at, status, admin_notes, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (*appointment, now, now),
        )

    notifications = [
        (None, "Critical O- request", "A critical request for 2 units of O- is pending in Pune.", "critical", "blood_request", request_ids[0]),
        (donor_user_id, "Donation appointment approved", "Your Pune Central Blood Bank appointment is approved.", "success", "appointment", 1),
        (admin_id, "Low stock warning", "AB- and B- inventory are below threshold.", "warning", "inventory", None),
    ]
    for user_id, title, message, kind, related_type, related_id in notifications:
        db.execute(
            """
            INSERT INTO notifications
                (user_id, title, message, type, related_type, related_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, title, message, kind, related_type, related_id, now),
        )

    db.execute(
        """
        INSERT INTO audit_logs (actor_id, action, entity_type, entity_id, details, created_at)
        VALUES (?, 'seeded_demo_data', 'system', NULL, 'Initial portfolio demo data created.', ?)
        """,
        (super_id, now),
    )

