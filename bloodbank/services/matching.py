from datetime import datetime

from .compatibility import compatible_donor_groups
from .eligibility import donor_eligibility


def find_matching_donors(db, blood_request: dict, cooldown_days: int = 90) -> list[dict]:
    accepted_groups = compatible_donor_groups(blood_request["blood_group"])
    placeholders = ",".join("?" for _ in accepted_groups)
    rows = db.execute(
        f"""
        SELECT
            donor_profiles.*,
            users.name,
            users.email,
            users.phone,
            users.city,
            users.last_login_at,
            users.created_at AS user_created_at
        FROM donor_profiles
        JOIN users ON users.id = donor_profiles.user_id
        WHERE users.is_active = 1
          AND donor_profiles.blood_group IN ({placeholders})
        """,
        tuple(accepted_groups),
    ).fetchall()

    request_city = (blood_request.get("city") or "").strip().lower()
    matches = []
    for row in rows:
        donor = dict(row)
        eligibility = donor_eligibility(
            donor.get("last_donation_date"),
            donor.get("age"),
            donor.get("availability_status"),
            cooldown_days,
        )

        same_city = (donor.get("city") or "").strip().lower() == request_city
        available = donor.get("availability_status") == "available"
        recently_active = donor.get("last_login_at") or donor.get("updated_at") or donor.get("user_created_at")

        score = 0
        reasons = []
        if same_city:
            score += 50
            reasons.append("same city")
        if eligibility["eligible"]:
            score += 30
            reasons.append("eligible now")
        if available:
            score += 15
            reasons.append("available")
        if donor.get("blood_group") == "O-":
            score += 8
            reasons.append("universal donor group")
        if donor.get("blood_group") == blood_request.get("blood_group"):
            score += 10
            reasons.append("exact blood group")

        matches.append(
            {
                **donor,
                "eligible": eligibility["eligible"],
                "eligibility_reason": eligibility["reason"],
                "same_city": same_city,
                "score": score,
                "reason": ", ".join(reasons) or "compatible blood group",
                "recently_active": recently_active,
            }
        )

    def sort_key(item):
        active_time = item.get("recently_active") or ""
        try:
            parsed_time = datetime.fromisoformat(active_time.replace("Z", ""))
        except ValueError:
            parsed_time = datetime.min
        return (item["same_city"], item["eligible"], parsed_time, item["score"])

    return sorted(matches, key=sort_key, reverse=True)


def persist_matches(db, request_id: int, matches: list[dict]) -> None:
    now = datetime.utcnow().isoformat(timespec="seconds")
    db.execute("DELETE FROM request_matches WHERE request_id = ?", (request_id,))
    for match in matches[:12]:
        db.execute(
            """
            INSERT OR REPLACE INTO request_matches (request_id, donor_id, score, reason, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (request_id, match["id"], match["score"], match["reason"], now),
        )

