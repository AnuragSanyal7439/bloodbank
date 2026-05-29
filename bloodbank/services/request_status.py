REQUEST_STATUSES = ["Pending", "Matched", "Fulfilled", "Cancelled"]

ALLOWED_TRANSITIONS = {
    "Pending": {"Matched", "Cancelled"},
    "Matched": {"Fulfilled", "Cancelled"},
    "Fulfilled": set(),
    "Cancelled": set(),
}

ACTION_TO_STATUS = {
    "approve": "Matched",
    "match": "Matched",
    "fulfill": "Fulfilled",
    "cancel": "Cancelled",
    "reject": "Cancelled",
}


def next_status_for_action(action: str) -> str:
    normalized = (action or "").strip().lower()
    if normalized not in ACTION_TO_STATUS:
        raise ValueError("Unsupported request action")
    return ACTION_TO_STATUS[normalized]


def validate_status_transition(current_status: str, target_status: str) -> str:
    if current_status not in REQUEST_STATUSES:
        raise ValueError("Unknown current status")
    if target_status not in REQUEST_STATUSES:
        raise ValueError("Unknown target status")
    if target_status not in ALLOWED_TRANSITIONS[current_status]:
        raise ValueError(f"Cannot move request from {current_status} to {target_status}")
    return target_status

