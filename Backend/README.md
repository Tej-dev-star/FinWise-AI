# FinWise AI — Flask backend starter

This backend starter provides:
- User registration and login with hashed passwords
- JWT-protected endpoints
- SQLite database, created automatically on startup
- Per-user transaction CRUD
- Loan CRUD and EMI calculation
- Dashboard summary
- Loan simulator API
- CSV transaction import (normalized CSV headers: `date,description,amount`)
- Account deletion endpoint
- CSV upload is parsed in memory; the original uploaded file is not saved

## 1. Setup in VS Code (Windows)

Open this `finwise-backend` folder in VS Code. In Terminal > New Terminal:

```powershell
py -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Copy `.env.example` to `.env` and replace both secret values with long random strings.
For the default Live Server URL, `FRONTEND_ORIGIN` may need to be `http://127.0.0.1:5500` or `http://localhost:5500`, depending on your Live Server settings.

Run:

```powershell
python app.py
```

API health check: `http://127.0.0.1:5000/api/health`

The SQLite database file is created automatically. With the default URI, Flask-SQLAlchemy stores it under the app's `instance` directory.

## 2. Important endpoints

- `POST /api/auth/register` JSON `{ "name": "Alex", "email": "alex@example.com", "password": "at-least-10-characters" }`
- `POST /api/auth/login` JSON `{ "email": "alex@example.com", "password": "..." }`
- `GET /api/me`
- `GET /api/dashboard`
- `GET /api/transactions`
- `POST /api/transactions` JSON `{ "date":"2026-10-30", "description":"Coffee", "amount":"250.00", "category":"Food & Dining", "kind":"expense" }`
- `PATCH /api/transactions/<id>`
- `DELETE /api/transactions/<id>`
- `GET /api/loans`
- `POST /api/loans` JSON `{ "name":"Personal Loan", "lender":"Example Bank", "principal":"50000", "annual_interest_rate":"12", "tenure_months":12 }`
- `DELETE /api/loans/<id>`
- `POST /api/simulator` JSON `{ "principal":"50000", "annual_interest_rate":"12", "tenure_months":12 }`
- `POST /api/transactions/import-csv?preview=1` multipart form with file field `file`
- `POST /api/transactions/import-csv` multipart form with file field `file`
- `DELETE /api/account`

All endpoints except `/api/health`, `/api/auth/register`, and `/api/auth/login` require an `Authorization: Bearer <access_token>` header.

## 3. CSV format

For this first version, CSV must have these headers:

```csv
date,description,amount
2026-10-21,UPI payment to restaurant,-350
2026-10-22,Monthly salary,40000
2026-10-23,Electricity bill,-1250
```

Positive amounts are treated as income and negative amounts as expenses. This is a prototype convention; bank exports vary, so production import should have a column-mapping and debit/credit review screen. The endpoint supports preview with `?preview=1`; the current starter's save endpoint imports all valid rows after parsing. Wire the preview response to a review UI before using this with real data.

## 4. Connecting the frontend

Your current frontend is still a static mockup. It does not call this API yet. Set up the backend and test `/api/health` first; then wire the frontend forms, transactions table, loans section, and dashboard to the endpoints. API requests should use the bearer token returned by login.

## 5. Privacy and security caveats

This is an educational prototype, not production-ready financial software:
- Change secrets in `.env`; never commit `.env`.
- Use HTTPS in deployment and disable debug mode.
- Add rate limiting, email verification, password reset, stronger schema validation, audit logging, and tested backup/deletion processes before a public launch.
- JWT in browser localStorage is vulnerable if your site has XSS; prefer secure, HttpOnly cookies for a production browser app.
- CSV duplicate detection is heuristic and must be reviewed.
- The example CORS origin must match your frontend URL.
- Never collect bank passwords, UPI PINs, card PINs or OTPs.


## 6. Bank integration scaffold (DEMO ONLY)

This version adds a simulated bank-connection flow so the frontend can demonstrate the concept:
- `GET /api/bank/connections`
- `POST /api/bank/demo/connect`
- `POST /api/bank/connections/<id>/sync`
- `DELETE /api/bank/connections/<id>` (revokes the connection)

All four endpoints require a JWT bearer token. The demo connection creates clearly labelled sample transactions; it does **not** contact a bank, read SMS, or access real financial data. Repeated syncs on the same day skip already-imported sample transaction IDs.

### Example sequence

1. Register/login and copy the returned `access_token`.
2. Send `POST /api/bank/demo/connect` with `Authorization: Bearer <token>`.
3. Copy `connection.id` from the response.
4. Send `POST /api/bank/connections/<id>/sync`.
5. Call `GET /api/transactions` or `GET /api/dashboard` to see the demo transactions.
6. Send `DELETE /api/bank/connections/<id>` to revoke the demo connection.

For requests with a JSON body, use `Content-Type: application/json`; the connect/sync/revoke endpoints do not require a body.

### Database notes

The starter uses SQLite and creates the new `bank_connections` and `imported_bank_transactions` tables on startup. `create_all()` does not migrate an existing table schema. If you already ran an older version, back up any data first; for a disposable prototype, stop the server and remove `instance/finwise.db` to create a fresh database. Do not delete a database containing data you need.

`ImportedBankTransaction` stores provider transaction IDs for deduplication; it does not store raw provider payloads or bank credentials. In a real integration, add a provider adapter and use the provider's actual transaction identifiers, consent state, expiry and sync cursor. Never accept a client-provided claim that bank consent was granted as proof of real consent.

### Before connecting a real bank

This is only an API/data-model scaffold. It is **not** a live Account Aggregator integration and is not production-ready. A real connection requires an eligible integration path/partner, provider-specific authentication and consent flows, verified server-to-server callbacks where applicable, secure secret storage, reconciliation, audit logging, retention/deletion rules, and legal/compliance review. Do not add endpoints that ask users for bank passwords, UPI PINs, card PINs or OTPs.


### Import fix
The shared SQLAlchemy instance lives in `extensions.py` so `app.py`, `models.py`, and `csv_import.py` can import it without a circular import. Run `python app.py` from this folder after installing requirements.
