from datetime import date, datetime, timedelta


def parse_date(value: str | None) -> date | None:
    if not value:
        return None
    if isinstance(value, date):
        return value
    return datetime.fromisoformat(value[:10]).date()


def donor_eligibility(
    last_donation_date: str | None,
    age: int | None = None,
    availability_status: str | None = "available",
    cooldown_days: int = 90,
) -> dict:
    if age is not None and (age < 18 or age > 65):
        return {
            "eligible": False,
            "days_remaining": None,
            "next_eligible_date": None,
            "reason": "Donor age must be between 18 and 65 years.",
        }

    if availability_status and availability_status.lower() != "available":
        return {
            "eligible": False,
            "days_remaining": None,
            "next_eligible_date": None,
            "reason": "Donor is currently marked unavailable.",
        }

    last_date = parse_date(last_donation_date)
    if not last_date:
        return {
            "eligible": True,
            "days_remaining": 0,
            "next_eligible_date": None,
            "reason": "No recent donation recorded.",
        }

    next_date = last_date + timedelta(days=cooldown_days)
    today = date.today()
    if today >= next_date:
        return {
            "eligible": True,
            "days_remaining": 0,
            "next_eligible_date": next_date.isoformat(),
            "reason": "Cooldown period completed.",
        }

    return {
        "eligible": False,
        "days_remaining": (next_date - today).days,
        "next_eligible_date": next_date.isoformat(),
        "reason": f"Next eligible on {next_date.isoformat()}.",
    }

