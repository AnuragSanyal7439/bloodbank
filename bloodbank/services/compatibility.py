BLOOD_GROUPS = ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]

RECIPIENT_COMPATIBILITY = {
    "A+": {"A+", "A-", "O+", "O-"},
    "A-": {"A-", "O-"},
    "B+": {"B+", "B-", "O+", "O-"},
    "B-": {"B-", "O-"},
    "AB+": set(BLOOD_GROUPS),
    "AB-": {"AB-", "A-", "B-", "O-"},
    "O+": {"O+", "O-"},
    "O-": {"O-"},
}


def normalize_blood_group(value: str) -> str:
    group = (value or "").strip().upper()
    if group not in BLOOD_GROUPS:
        raise ValueError("Invalid blood group")
    return group


def compatible_donor_groups(recipient_group: str) -> set[str]:
    recipient = normalize_blood_group(recipient_group)
    return RECIPIENT_COMPATIBILITY[recipient]


def is_compatible(donor_group: str, recipient_group: str) -> bool:
    donor = normalize_blood_group(donor_group)
    return donor in compatible_donor_groups(recipient_group)

