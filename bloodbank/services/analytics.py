from collections import defaultdict
from datetime import datetime

from .inventory import stock_status


def month_key(value: str) -> str:
    try:
        return datetime.fromisoformat(value[:19]).strftime("%b")
    except (ValueError, TypeError):
        return "Unknown"


def dashboard_overview(db) -> dict:
    counts = {
        "total_donors": db.execute("SELECT COUNT(*) AS count FROM donor_profiles").fetchone()["count"],
        "total_requests": db.execute("SELECT COUNT(*) AS count FROM blood_requests").fetchone()["count"],
        "critical_pending": db.execute(
            "SELECT COUNT(*) AS count FROM blood_requests WHERE urgency = 'Critical' AND status IN ('Pending', 'Matched')"
        ).fetchone()["count"],
        "appointments_pending": db.execute("SELECT COUNT(*) AS count FROM appointments WHERE status = 'Pending'").fetchone()["count"],
        "users": db.execute("SELECT COUNT(*) AS count FROM users").fetchone()["count"],
    }

    inventory = [dict(row) for row in db.execute("SELECT * FROM blood_inventory ORDER BY blood_group").fetchall()]
    for item in inventory:
        item["stock_status"] = stock_status(item)

    request_rows = db.execute("SELECT created_at, urgency, city, blood_group, status FROM blood_requests").fetchall()
    donation_rows = db.execute("SELECT donation_date, blood_group, units, status FROM blood_donations").fetchall()
    donor_city_rows = db.execute(
        """
        SELECT users.city, COUNT(*) AS count
        FROM donor_profiles
        JOIN users ON users.id = donor_profiles.user_id
        GROUP BY users.city
        ORDER BY count DESC
        """
    ).fetchall()

    monthly_requests = defaultdict(int)
    urgency_distribution = defaultdict(int)
    for row in request_rows:
        monthly_requests[month_key(row["created_at"])] += 1
        urgency_distribution[row["urgency"]] += 1

    monthly_donations = defaultdict(int)
    for row in donation_rows:
        if row["status"] == "Accepted":
            monthly_donations[month_key(row["donation_date"])] += int(row["units"])

    low_stock = [item for item in inventory if item["stock_status"] in {"low", "out"}]

    return {
        "counts": counts,
        "inventory": inventory,
        "low_stock": low_stock,
        "monthly_requests": dict(monthly_requests),
        "monthly_donations": dict(monthly_donations),
        "urgency_distribution": dict(urgency_distribution),
        "city_donor_count": [dict(row) for row in donor_city_rows],
    }

