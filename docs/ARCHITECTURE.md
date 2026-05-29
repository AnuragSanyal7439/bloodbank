# BloodBank Architecture

BloodBank is organized as a small modular Flask application with database-backed APIs and a single-page frontend.

## Runtime Flow

```mermaid
flowchart LR
    User["Donor / Recipient / Hospital / Admin"] --> UI["Single-page UI"]
    UI --> Auth["Auth API"]
    UI --> Requests["Requests API"]
    UI --> Inventory["Inventory API"]
    UI --> Dashboard["Dashboard API + SSE"]
    Requests --> Matching["Donor Matching Service"]
    Requests --> InventoryRules["Inventory Transition Rules"]
    Donations["Donation Verification API"] --> InventoryRules
    InventoryRules --> SQLite[(SQLite Database)]
    Matching --> SQLite
    Auth --> SQLite
    Dashboard --> SQLite
```

## Data Model

```mermaid
erDiagram
    USERS ||--o| DONOR_PROFILES : owns
    USERS ||--o| HOSPITAL_PROFILES : owns
    USERS ||--o{ BLOOD_REQUESTS : creates
    DONOR_PROFILES ||--o{ BLOOD_DONATIONS : submits
    DONOR_PROFILES ||--o{ APPOINTMENTS : books
    DONOR_PROFILES ||--o{ REQUEST_MATCHES : matched
    BLOOD_REQUESTS ||--o{ REQUEST_MATCHES : has
    BLOOD_DONATIONS ||--o{ BLOOD_UNITS : produces
    USERS ||--o{ NOTIFICATIONS : receives
    USERS ||--o{ AUDIT_LOGS : performs

    USERS {
        int id
        string name
        string email
        string role
        string city
    }

    DONOR_PROFILES {
        int id
        int user_id
        string blood_group
        string availability_status
        string last_donation_date
    }

    BLOOD_REQUESTS {
        int id
        int requester_id
        string blood_group
        int units_required
        string urgency
        string status
    }

    BLOOD_INVENTORY {
        int id
        string blood_group
        int available_units
        int reserved_units
        int expired_units
    }
```

## Service Boundaries

- `services/compatibility.py`: blood group compatibility rules.
- `services/eligibility.py`: donor age, availability, and cooldown checks.
- `services/inventory.py`: reserve, release, and fulfill inventory transitions.
- `services/matching.py`: donor ranking for new and existing requests.
- `services/analytics.py`: dashboard metrics and chart data.
- `services/notifications.py`: in-app notification creation and external-provider placeholders.

