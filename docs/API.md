# BloodBank API Reference

All API responses are JSON. Authenticated routes use the Flask session cookie created by `/api/auth/login` or `/api/auth/register`.

## Auth

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `POST` | `/api/auth/register` | Register donor, recipient, or hospital users. |
| `POST` | `/api/auth/login` | Login with email and password. |
| `POST` | `/api/auth/logout` | Clear the active session. |
| `GET` | `/api/auth/me` | Return the current logged-in user. |

## Dashboard

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/api/dashboard/public` | Public landing-page stock and critical request snapshot. |
| `GET` | `/api/dashboard/overview` | Authenticated dashboard analytics and recent activity. |
| `GET` | `/api/dashboard/events` | Server-Sent Events stream for live dashboard updates. |

## Donors

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/api/donors` | Search and filter donors by name, city, blood group, and sort order. |
| `GET` | `/api/donors/me` | Donor profile, eligibility, and completion details. |
| `PUT` | `/api/donors/me` | Update the logged-in donor profile. |

## Blood Requests

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/api/requests` | List requests with status, urgency, blood group, and sorting filters. |
| `POST` | `/api/requests` | Create a recipient or hospital blood request. |
| `GET` | `/api/requests/<id>/matches` | Return ranked compatible donors for a request. |
| `PATCH` | `/api/requests/<id>/status` | Admin action: approve, reject, fulfill, or cancel. |

## Inventory

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/api/inventory` | List inventory by blood group and sync expired units. |
| `PATCH` | `/api/inventory/<blood_group>` | Admin inventory update for available, reserved, expired, and threshold values. |

## Appointments And Donations

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/api/appointments` | List donor appointments or admin appointment queue. |
| `POST` | `/api/appointments` | Donor appointment booking. |
| `PATCH` | `/api/appointments/<id>/status` | Admin appointment approval, reschedule, or cancellation. |
| `GET` | `/api/donations` | Donation history or admin donation verification queue. |
| `POST` | `/api/donations` | Donor submits a donation for verification. |
| `PATCH` | `/api/donations/<id>/verify` | Admin accepts or rejects a donation. |

## Admin

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/api/admin/users` | Admin user list. |
| `PATCH` | `/api/admin/users/<id>` | Super admin user status or role update. |
| `GET` | `/api/admin/audit-logs` | Latest admin and system audit trail. |

