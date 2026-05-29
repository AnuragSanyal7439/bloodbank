# BloodBank

BloodBank is a production-style academic demo platform for managing donors, recipients, hospitals, blood requests, appointments, inventory, emergency alerts, and admin operations from one real-time dashboard.

> Disclaimer: This project is for academic, portfolio, hackathon, and placement showcase use only. It is not a certified medical system and must not be used for real clinical decisions without licensed workflows, regulatory compliance, and verified integrations.

## Key Features

- Role-based login and protected dashboards for donor, recipient, hospital, blood bank admin, and super admin users.
- Donor profiles with eligibility checks, profile completion, donation history, appointments, and emergency alerts.
- Blood request workflow with Pending, Matched, Fulfilled, and Cancelled states.
- Smart donor matching using blood compatibility, city, availability, eligibility, and activity.
- Real SQLite-backed inventory with available, reserved, expired units, low-stock warnings, and expiry sync.
- Donation verification that increases inventory only after admin approval.
- Appointment scheduling with admin approval, reschedule, and cancellation.
- Analytics charts for stock, monthly donations, monthly requests, urgency, and donor cities.
- In-app notifications plus clean placeholders for SMTP, EmailJS, Twilio SMS, and WhatsApp.
- Audit logs for inventory changes, request handling, donation verification, and user management.
- Server-Sent Events realtime dashboard updates with a polling fallback.

## Tech Stack

- Backend: Python, Flask, SQLite
- Frontend: HTML, CSS, vanilla JavaScript
- Charts: Chart.js
- Icons: Lucide
- Auth: Flask secure sessions with Werkzeug password hashing
- Realtime: Server-Sent Events
- Tests: Python `unittest`

## Folder Structure

```text
bloodbank/
  routes/          API route modules
  services/        Compatibility, eligibility, inventory, matching, analytics
  config.py        Environment and app config
  db.py            SQLite schema, indexes, and seed data
static/
  assets/          Project visuals
  css/styles.css   Responsive UI
  js/app.js        Single-page app logic
templates/
  index.html       Main web UI
tests/
  test_domain.py   Core business-rule tests
app.py             Flask entrypoint
mian.py            Legacy-compatible runner
```

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python app.py
```

Open `http://127.0.0.1:5000`.

The SQLite database is created automatically at `instance/bloodbank.sqlite` with active demo data. To reset the demo, stop the server, delete that file, and run `python app.py` again.

## Demo Credentials

| Role | Email | Password |
| --- | --- | --- |
| Donor | `donor@bloodbank.demo` | `Donor@123` |
| Hospital | `hospital@bloodbank.demo` | `Hospital@123` |
| Blood Bank Admin | `admin@bloodbank.demo` | `Admin@123` |
| Super Admin | `superadmin@bloodbank.demo` | `Super@123` |
| Recipient | `recipient@bloodbank.demo` | `Patient@123` |

## Environment Variables

Copy `.env.example` to `.env` and adjust as needed.

```text
SECRET_KEY=change-this-for-production
DATABASE_PATH=instance/bloodbank.sqlite
DONATION_COOLDOWN_DAYS=90
DEFAULT_LOW_STOCK_THRESHOLD=5
```

Optional notification variables are included for future SMTP, EmailJS, Twilio SMS, or WhatsApp integration. The app does not call paid APIs unless you add provider credentials and implementation logic.

## Tests

```powershell
python -m unittest discover -s tests
```

Covered logic:

- Blood compatibility
- Donor eligibility cooldown
- Inventory reserve, release, and fulfillment rules
- Request status transitions

## API Documentation

See [docs/API.md](docs/API.md) for the route map across auth, dashboard, donors, requests, inventory, appointments, donations, and admin operations.

## Screenshots

Add screenshots here after deployment:

- Landing page
- Admin dashboard
- Donor dashboard
- Inventory and analytics
- Emergency request workflow

## Deployment

For a simple demo deployment:

1. Set a strong `SECRET_KEY`.
2. Use a persistent database path.
3. Install dependencies with `pip install -r requirements.txt`.
4. Run with a production WSGI server such as Waitress.
5. Serve behind HTTPS.

Example local production-style command:

```powershell
waitress-serve --listen=0.0.0.0:5000 wsgi:app
```

This repo also includes `Procfile` and `render.yaml` for deployment-friendly hosting.

## Future Scope

- Real SMS, WhatsApp, and email provider integrations.
- Hospital verification documents and admin approval workflow.
- Map-based donor distance matching.
- PDF reports and printable donation certificates.
- More granular audit export and role permissions.
- Full CSRF protection for public deployments.
