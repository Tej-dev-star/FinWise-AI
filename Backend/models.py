from datetime import datetime, timezone
from extensions import db


class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(254), unique=True, nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    transactions = db.relationship("Transaction", backref="user", cascade="all, delete-orphan")
    loans = db.relationship("Loan", backref="user", cascade="all, delete-orphan")
    income_records = db.relationship("IncomeRecord", backref="user", cascade="all, delete-orphan")

    def to_dict(self):
        return {"id": self.id, "name": self.name, "email": self.email}


class Transaction(db.Model):
    __tablename__ = "transactions"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    date = db.Column(db.String(10), nullable=False, index=True)
    description = db.Column(db.String(180), nullable=False)
    amount = db.Column(db.String(32), nullable=False)  # Decimal string to avoid binary float storage.
    category = db.Column(db.String(60), nullable=False, default="Other")
    kind = db.Column(db.String(10), nullable=False)  # income or expense
    source = db.Column(db.String(20), nullable=False, default="manual")
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    def to_dict(self):
        return {
            "id": self.id, "date": self.date, "description": self.description,
            "amount": self.amount, "category": self.category,
            "kind": self.kind, "source": self.source
        }


class Loan(db.Model):
    __tablename__ = "loans"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    lender = db.Column(db.String(100), nullable=True)
    principal = db.Column(db.String(32), nullable=False)
    annual_interest_rate = db.Column(db.String(16), nullable=False, default="0")
    tenure_months = db.Column(db.Integer, nullable=False)
    outstanding_balance = db.Column(db.String(32), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    @property
    def monthly_emi(self):
        p = float(self.principal)
        r = float(self.annual_interest_rate) / 1200
        n = self.tenure_months
        return p / n if r == 0 else p * r * (1 + r) ** n / ((1 + r) ** n - 1)

    def to_dict(self):
        return {
            "id": self.id, "name": self.name, "lender": self.lender,
            "principal": self.principal,
            "annual_interest_rate": self.annual_interest_rate,
            "tenure_months": self.tenure_months,
            "outstanding_balance": self.outstanding_balance,
            "monthly_emi": round(self.monthly_emi, 2)
        }


class Repayment(db.Model):
    __tablename__ = "repayments"
    id = db.Column(db.Integer, primary_key=True)
    loan_id = db.Column(db.Integer, db.ForeignKey("loans.id", ondelete="CASCADE"), nullable=False, index=True)
    amount = db.Column(db.String(32), nullable=False)
    due_date = db.Column(db.String(10), nullable=False)
    paid_date = db.Column(db.String(10), nullable=True)
    status = db.Column(db.String(20), nullable=False, default="upcoming")
    loan = db.relationship("Loan", backref=db.backref("repayments", cascade="all, delete-orphan"))

    def to_dict(self):
        return {"id": self.id, "loan_id": self.loan_id, "amount": self.amount,
                "due_date": self.due_date, "paid_date": self.paid_date, "status": self.status}


class IncomeRecord(db.Model):
    __tablename__ = "income_records"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    source = db.Column(db.String(100), nullable=False)
    amount = db.Column(db.String(32), nullable=False)
    date = db.Column(db.String(10), nullable=False)

    def to_dict(self):
        return {"id": self.id, "source": self.source, "amount": self.amount, "date": self.date}


class BankConnection(db.Model):
    """Stores connection/consent metadata only; never store bank login credentials."""
    __tablename__ = "bank_connections"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"),
                        nullable=False, index=True)
    provider = db.Column(db.String(40), nullable=False, default="demo")
    display_name = db.Column(db.String(100), nullable=False, default="Demo Bank")
    status = db.Column(db.String(20), nullable=False, default="active")  # active/revoked
    consent_status = db.Column(db.String(20), nullable=False, default="granted")
    consent_expires_at = db.Column(db.DateTime, nullable=True)
    last_synced_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    user = db.relationship("User", backref=db.backref("bank_connections", cascade="all, delete-orphan"))

    def to_dict(self):
        return {
            "id": self.id,
            "provider": self.provider,
            "display_name": self.display_name,
            "status": self.status,
            "consent_status": self.consent_status,
            "consent_expires_at": self.consent_expires_at.isoformat() if self.consent_expires_at else None,
            "last_synced_at": self.last_synced_at.isoformat() if self.last_synced_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "is_demo": self.provider == "demo",
        }


class ImportedBankTransaction(db.Model):
    """Idempotency ledger linking provider transaction IDs to internal transactions."""
    __tablename__ = "imported_bank_transactions"
    id = db.Column(db.Integer, primary_key=True)
    connection_id = db.Column(db.Integer, db.ForeignKey("bank_connections.id", ondelete="CASCADE"),
                              nullable=False, index=True)
    provider_transaction_id = db.Column(db.String(160), nullable=False)
    transaction_id = db.Column(db.Integer, db.ForeignKey("transactions.id", ondelete="CASCADE"),
                               nullable=False, unique=True)
    imported_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        db.UniqueConstraint("connection_id", "provider_transaction_id", name="uq_bank_provider_txn"),
    )
    connection = db.relationship("BankConnection", backref=db.backref("imports", cascade="all, delete-orphan"))
    transaction = db.relationship("Transaction")
