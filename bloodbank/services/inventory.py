def apply_inventory_delta(
    inventory: dict,
    available_delta: int = 0,
    reserved_delta: int = 0,
    expired_delta: int = 0,
) -> dict:
    updated = dict(inventory)
    updated["available_units"] = int(updated.get("available_units", 0)) + available_delta
    updated["reserved_units"] = int(updated.get("reserved_units", 0)) + reserved_delta
    updated["expired_units"] = int(updated.get("expired_units", 0)) + expired_delta

    for key in ("available_units", "reserved_units", "expired_units"):
        if updated[key] < 0:
            raise ValueError(f"{key.replace('_', ' ').title()} cannot become negative")
    return updated


def reserve_units(inventory: dict, units: int) -> dict:
    if units <= 0:
        raise ValueError("Units must be greater than zero")
    if int(inventory.get("available_units", 0)) < units:
        raise ValueError("Not enough available units to reserve")
    return apply_inventory_delta(inventory, available_delta=-units, reserved_delta=units)


def fulfill_reserved_units(inventory: dict, units: int) -> dict:
    if units <= 0:
        raise ValueError("Units must be greater than zero")
    if int(inventory.get("reserved_units", 0)) < units:
        raise ValueError("Not enough reserved units to fulfill")
    return apply_inventory_delta(inventory, reserved_delta=-units)


def release_reserved_units(inventory: dict, units: int) -> dict:
    if units <= 0:
        raise ValueError("Units must be greater than zero")
    if int(inventory.get("reserved_units", 0)) < units:
        raise ValueError("Not enough reserved units to release")
    return apply_inventory_delta(inventory, available_delta=units, reserved_delta=-units)


def stock_status(inventory: dict) -> str:
    available = int(inventory.get("available_units", 0))
    threshold = int(inventory.get("low_stock_threshold", 5))
    if available == 0:
        return "out"
    if available <= threshold:
        return "low"
    return "healthy"

