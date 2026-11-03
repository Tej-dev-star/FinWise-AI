import os
from datetime import timedelta, datetime, timezone
from decimal import Decimal, InvalidOperation

from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_jwt_extended import (
    JWTManager, create_access_token, get_jwt_identity,
    jwt_required
)
from werkzeug.security import generate_password_hash, check_password_hash

from extensions import db

load_dotenv()
jwt = JWTManager()


def create_app():
    app = Flask(__name__, instance_relative_config=True)
    os.makedirs(app.instance_path, exist_ok=True)

    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-only-change-this")
    app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET_KEY", "dev-only-change-this-too")
    app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(hours=2)
    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
        "DATABASE_URL", "sqlite:///finwise.db"
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)
    jwt.init_app(app)
    CORS(app, resources={r"/api/*": {"origins": os.getenv(
        "FRONTEND_ORIGIN", "http://127.0.0.1:5500"
    )}})

    from models import User, Transaction, Loan, Repayment, IncomeRecord, BankConnection, ImportedBankTransaction
    from csv_import import csv_bp
    app.register_blueprint(csv_bp)

    @app.get("/api/health")
    def health():
        return jsonify({"status": "ok", "service": "FinWise AI API"})

    @app.post("/api/auth/register")
    def register():
        data = request.get_json(silent=True) or {}
        email = str(data.get("email", "")).strip().lower()
        password = str(data.get("password", ""))
        display_name = str(data.get("name", "")).strip()

        if not email or "@" not in email:
            return jsonify({"error": "Enter a valid email address."}), 400
        if len(password) < 10:
            return jsonify({"error": "Password must be at least 10 characters."}), 400
        if not display_name:
            return jsonify({"error": "Name is required."}), 400
        if User.query.filter_by(email=email).first():
            return jsonify({"error": "An account with this email already exists."}), 409

        user = User(
            email=email,
            name=display_name,
            password_hash=generate_password_hash(password)
        )
        db.session.add(user)
        db.session.commit()
        token = create_access_token(identity=str(user.id))
        return jsonify({"access_token": token, "user": user.to_dict()}), 201

    @app.post("/api/auth/login")
    def login():
        data = request.get_json(silent=True) or {}
        email = str(data.get("email", "")).strip().lower()
        password = str(data.get("password", ""))
        user = User.query.filter_by(email=email).first()
        if not user or not check_password_hash(user.password_hash, password):
            return jsonify({"error": "Invalid email or password."}), 401
        token = create_access_token(identity=str(user.id))
        return jsonify({"access_token": token, "user": user.to_dict()})

    def current_user_id():
        return int(get_jwt_identity())

    def parse_amount(value):
        try:
            amount = Decimal(str(value))
            if not amount.is_finite() or amount <= 0 or amount > Decimal("1000000000000"):
                raise ValueError()
            return amount.quantize(Decimal("0.01"))
        except (InvalidOperation, ValueError, TypeError):
            raise ValueError("Amount must be a positive valid number.")

    def json_error(message, code=400):
        return jsonify({"error": message}), code


    # Bank integration scaffold:
    # These endpoints simulate a provider connection for demos. They do NOT connect to a real bank.
    @app.get("/api/bank/connections")
    @jwt_required()
    def list_bank_connections():
        rows = BankConnection.query.filter_by(user_id=current_user_id()).order_by(BankConnection.id.desc()).all()
        return jsonify({"connections": [row.to_dict() for row in rows]})

    @app.post("/api/bank/demo/connect")
    @jwt_required()
    def connect_demo_bank():
        """Create a clearly labelled demo connection to exercise the product flow."""
        user_id = current_user_id()
        existing = BankConnection.query.filter_by(
            user_id=user_id, provider="demo", status="active"
        ).first()
        if existing:
            return jsonify({
                "connection": existing.to_dict(),
                "message": "An active demo connection already exists. This is simulated data, not a real bank connection."
            }), 200

        # Demo consent expires in 30 days. A real provider's consent flow must supply
        # the authoritative consent status/expiry and must not be bypassed by this route.
        connection = BankConnection(
            user_id=user_id,
            provider="demo",
            display_name="FinWise Demo Bank (SIMULATED)",
            status="active",
            consent_status="granted",
            consent_expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        )
        db.session.add(connection)
        db.session.commit()
        return jsonify({
            "connection": connection.to_dict(),
            "message": "Demo connection created. No bank was contacted and no real financial data was accessed."
        }), 201

    @app.post("/api/bank/connections/<int:connection_id>/sync")
    @jwt_required()
    def sync_bank_connection(connection_id):
        """Generate repeatable sample transactions for the demo connection only."""
        connection = BankConnection.query.filter_by(
            id=connection_id, user_id=current_user_id()
        ).first()
        if not connection:
            return json_error("Bank connection not found.", 404)
        if connection.status != "active" or connection.consent_status != "granted":
            return json_error("This connection is not active. Reconnect and grant consent first.", 409)
        
        now = datetime.now(timezone.utc)

        if connection.consent_expires_at:
            expires_at = connection.consent_expires_at

            # SQLite may return a UTC datetime without timezone information.
            # Treat these stored naive timestamps as UTC.
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)

            if expires_at <= now:
                connection.consent_status = "expired"
                db.session.commit()
                return json_error(
                    "Consent has expired. Renew consent before syncing.", 409
                )


        today = now.date()
        samples = [
            {
                "provider_id": f"demo-grocery-{today.isoformat()}",
                "date": today.isoformat(),
                "description": "Demo transaction - Grocery store",
                "amount": "650.00", "kind": "expense", "category": "Groceries",
            },
            {
                "provider_id": f"demo-food-{today.isoformat()}",
                "date": today.isoformat(),
                "description": "Demo transaction - Cafe",
                "amount": "180.00", "kind": "expense", "category": "Food & Dining",
            },
            {
                "provider_id": f"demo-credit-{today.isoformat()}",
                "date": today.isoformat(),
                "description": "Demo transaction - Stipend credit",
                "amount": "5000.00", "kind": "income", "category": "Income",
            },
        ]

        imported = 0
        skipped = 0
        for item in samples:
            already = ImportedBankTransaction.query.filter_by(
                connection_id=connection.id,
                provider_transaction_id=item["provider_id"]
            ).first()
            if already:
                skipped += 1
                continue
            transaction = Transaction(
                user_id=current_user_id(),
                date=item["date"],
                description=item["description"],
                amount=item["amount"],
                category=item["category"],
                kind=item["kind"],
                source="bank_demo",
            )
            db.session.add(transaction)
            db.session.flush()
            ledger = ImportedBankTransaction(
                connection_id=connection.id,
                provider_transaction_id=item["provider_id"],
                transaction_id=transaction.id,
            )
            db.session.add(ledger)
            imported += 1

        connection.last_synced_at = now
        db.session.commit()
        return jsonify({
            "connection": connection.to_dict(),
            "imported_count": imported,
            "skipped_duplicate_count": skipped,
            "message": "Simulated transactions only. This endpoint did not contact a bank."
        })

    @app.delete("/api/bank/connections/<int:connection_id>")
    @jwt_required()
    def revoke_bank_connection(connection_id):
        """Revoke the local connection. Existing imported transactions are retained."""
        connection = BankConnection.query.filter_by(
            id=connection_id, user_id=current_user_id()
        ).first()
        if not connection:
            return json_error("Bank connection not found.", 404)
        connection.status = "revoked"
        connection.consent_status = "revoked"
        db.session.commit()
        return jsonify({
            "revoked": True,
            "connection": connection.to_dict(),
            "message": "Future syncs are blocked. Previously imported transactions remain in your FinWise history."
        })

    @app.get("/api/me")
    @jwt_required()
    def me():
        user = db.session.get(User, current_user_id())
        if not user:
            return json_error("User not found.", 404)
        return jsonify({"user": user.to_dict()})

    @app.get("/api/transactions")
    @jwt_required()
    def get_transactions():
        query = Transaction.query.filter_by(user_id=current_user_id())
        category = request.args.get("category")
        if category:
            query = query.filter_by(category=category)
        rows = query.order_by(Transaction.date.desc(), Transaction.id.desc()).all()
        return jsonify({"transactions": [t.to_dict() for t in rows]})

    @app.post("/api/transactions")
    @jwt_required()
    def add_transaction():
        data = request.get_json(silent=True) or {}
        try:
            amount = parse_amount(data.get("amount"))
        except ValueError as exc:
            return json_error(str(exc))
        description = str(data.get("description", "")).strip()[:180]
        date = str(data.get("date", "")).strip()
        category = str(data.get("category", "Other")).strip()[:60]
        kind = str(data.get("kind", "expense")).lower()
        if not description or not date or kind not in {"income", "expense"}:
            return json_error("Description, date, and a valid kind are required.")
        from datetime import date as date_type
        try:
            date_type.fromisoformat(date)
        except ValueError:
            return json_error("Date must use YYYY-MM-DD format.")
        row = Transaction(
            user_id=current_user_id(), description=description,
            amount=str(amount), date=date, category=category, kind=kind,
            source="manual"
        )
        db.session.add(row)
        db.session.commit()
        return jsonify({"transaction": row.to_dict()}), 201

    @app.patch("/api/transactions/<int:transaction_id>")
    @jwt_required()
    def update_transaction(transaction_id):
        row = Transaction.query.filter_by(
            id=transaction_id, user_id=current_user_id()
        ).first()
        if not row:
            return json_error("Transaction not found.", 404)
        data = request.get_json(silent=True) or {}
        if "description" in data:
            row.description = str(data["description"]).strip()[:180]
        if "category" in data:
            row.category = str(data["category"]).strip()[:60]
        if "kind" in data:
            if data["kind"] not in {"income", "expense"}:
                return json_error("Kind must be income or expense.")
            row.kind = data["kind"]
        if "amount" in data:
            try:
                row.amount = str(parse_amount(data["amount"]))
            except ValueError as exc:
                return json_error(str(exc))
        if "date" in data:
            from datetime import date as date_type
            try:
                date_type.fromisoformat(str(data["date"]))
            except ValueError:
                return json_error("Date must use YYYY-MM-DD format.")
            row.date = str(data["date"])
        db.session.commit()
        return jsonify({"transaction": row.to_dict()})

    @app.delete("/api/transactions/<int:transaction_id>")
    @jwt_required()
    def delete_transaction(transaction_id):
        row = Transaction.query.filter_by(
            id=transaction_id, user_id=current_user_id()
        ).first()
        if not row:
            return json_error("Transaction not found.", 404)
        db.session.delete(row)
        db.session.commit()
        return jsonify({"deleted": True})

    @app.get("/api/loans")
    @jwt_required()
    def get_loans():
        rows = Loan.query.filter_by(user_id=current_user_id()).order_by(Loan.id.desc()).all()
        return jsonify({"loans": [loan.to_dict() for loan in rows]})

    @app.post("/api/loans")
    @jwt_required()
    def add_loan():
        data = request.get_json(silent=True) or {}
        try:
            principal = parse_amount(data.get("principal"))
            rate = Decimal(str(data.get("annual_interest_rate", "0")))
            months = int(data.get("tenure_months", 0))
            if not rate.is_finite() or rate < 0 or rate > 100 or months < 1 or months > 600:
                raise ValueError()
        except (ValueError, InvalidOperation, TypeError):
            return json_error("Provide a valid principal, interest rate (0–100), and tenure (1–600 months).")
        name = str(data.get("name", "")).strip()[:100]
        lender = str(data.get("lender", "")).strip()[:100]
        if not name:
            return json_error("Loan name is required.")
        loan = Loan(
            user_id=current_user_id(), name=name, lender=lender,
            principal=str(principal), annual_interest_rate=str(rate),
            tenure_months=months, outstanding_balance=str(principal)
        )
        db.session.add(loan)
        db.session.commit()
        return jsonify({"loan": loan.to_dict()}), 201

    @app.delete("/api/loans/<int:loan_id>")
    @jwt_required()
    def delete_loan(loan_id):
        loan = Loan.query.filter_by(id=loan_id, user_id=current_user_id()).first()
        if not loan:
            return json_error("Loan not found.", 404)
        db.session.delete(loan)
        db.session.commit()
        return jsonify({"deleted": True})

    
    @app.get("/api/dashboard")
    @jwt_required()
    def dashboard():
        uid = current_user_id()
        txns = Transaction.query.filter_by(user_id=uid).all()
        loans = Loan.query.filter_by(user_id=uid).all()

        # Use Decimal zero to preserve money calculation consistency
        zero = Decimal("0.00")

        income = sum(
            (Decimal(t.amount) for t in txns if t.kind == "income"),
            zero
        )

        expenses = sum(
            (Decimal(t.amount) for t in txns if t.kind == "expense"),
            zero
        )

        emi_total = sum(
            (Decimal(loan.monthly_emi) for loan in loans),
            zero
        )

        return jsonify({
            "currency": "INR",
            "transaction_count": len(txns),
            "monthly_income": str(income.quantize(Decimal("0.01"))),
            "monthly_expenses": str(expenses.quantize(Decimal("0.01"))),
            "active_loan_count": len(loans),
            "estimated_monthly_emis": str(emi_total.quantize(Decimal("0.01"))),
            "note": "Totals cover all saved transactions; add date filters for a true monthly summary."
        })


    @app.post("/api/simulator")
    @jwt_required()
    def simulate():
        data = request.get_json(silent=True) or {}
        try:
            principal = parse_amount(data.get("principal"))
            annual_rate = Decimal(str(data.get("annual_interest_rate", "0")))
            months = int(data.get("tenure_months", 0))
            if not annual_rate.is_finite() or annual_rate < 0 or annual_rate > 100 or months < 1 or months > 600:
                raise ValueError()
        except (ValueError, InvalidOperation, TypeError):
            return json_error("Provide a valid principal, rate, and tenure.")
        p = float(principal)
        r = float(annual_rate) / 1200
        emi = p / months if r == 0 else p * r * (1 + r) ** months / ((1 + r) ** months - 1)
        return jsonify({
            "monthly_emi": round(emi, 2),
            "total_repayment": round(emi * months, 2),
            "total_interest": round(emi * months - p, 2),
            "disclaimer": "Estimate only; fees, taxes, and lender-specific terms may change actual payments."
        })

    @app.delete("/api/account")
    @jwt_required()
    def delete_account():
        # The cascade relationships in models.py remove owned records.
        user = db.session.get(User, current_user_id())
        if not user:
            return json_error("User not found.", 404)
        db.session.delete(user)
        db.session.commit()
        return jsonify({"deleted": True, "message": "Account and associated records deleted."})

    with app.app_context():
        db.create_all()

    return app


app = create_app()

if __name__ == "__main__":
    # Local development only. Do not expose the debug server publicly.
    app.run(host="127.0.0.1", port=5000, debug=True)
