import csv
import io
from datetime import date as date_type
from decimal import Decimal, InvalidOperation

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from extensions import db
from models import Transaction

csv_bp = Blueprint("csv_import", __name__)


def guess_category(description):
    text = description.lower()
    rules = {
        "Food & Dining": ["restaurant", "zomato", "swiggy", "cafe", "food", "hotel"],
        "Transport": ["uber", "ola", "fuel", "petrol", "bus", "train", "metro"],
        "Utilities": ["electricity", "water bill", "broadband", "recharge", "gas bill"],
        "Shopping": ["amazon", "flipkart", "shopping", "blinkit", "mall"],
        "Housing": ["rent", "landlord", "maintenance"],
        "Income": ["salary", "payroll", "interest credit"]
    }
    for category, words in rules.items():
        if any(word in text for word in words):
            return category
    return "Other"


@csv_bp.post("/api/transactions/import-csv")
@jwt_required()
def import_csv():
    upload = request.files.get("file")
    if not upload or not upload.filename.lower().endswith(".csv"):
        return jsonify({"error": "Upload a CSV file."}), 400
    # Limit input size to reduce accidental or abusive oversized uploads.
    raw = upload.stream.read(2_000_001)
    if len(raw) > 2_000_000:
        return jsonify({"error": "CSV file must be 2 MB or smaller."}), 413
    try:
        text = raw.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text))
    except (UnicodeDecodeError, csv.Error):
        return jsonify({"error": "Could not read CSV. Save it as UTF-8 CSV and try again."}), 400

    # Expected normalized headers: date, description, amount. No raw file is stored.
    if not reader.fieldnames:
        return jsonify({"error": "CSV has no header row."}), 400
    header_map = {h.strip().lower(): h for h in reader.fieldnames if h}
    if not {"date", "description", "amount"}.issubset(header_map):
        return jsonify({
            "error": "CSV needs columns named date, description, amount.",
            "expected_headers": ["date", "description", "amount"],
            "tip": "Export or map your statement columns to this format before importing."
        }), 400

    parsed = []
    errors = []
    for line_no, row in enumerate(reader, start=2):
        try:
            date_value = str(row[header_map["date"]]).strip()
            date_type.fromisoformat(date_value)
            description = str(row[header_map["description"]]).strip()[:180]
            amount_text = str(row[header_map["amount"]]).replace(",", "").replace("₹", "").strip()
            amount = Decimal(amount_text)
            if not description or not amount.is_finite() or amount == 0:
                raise ValueError()
            kind = "income" if amount > 0 else "expense"
            parsed.append({
                "date": date_value, "description": description,
                "amount": str(abs(amount).quantize(Decimal("0.01"))),
                "kind": kind, "category": guess_category(description)
            })
        except (ValueError, InvalidOperation, TypeError, KeyError):
            errors.append({"line": line_no, "message": "Invalid date, description, or amount."})
        if len(parsed) + len(errors) > 5000:
            return jsonify({"error": "Maximum 5,000 rows per import."}), 413

    # Preview mode: return parsed rows without saving.
    if request.args.get("preview") == "1":
        return jsonify({"preview": parsed, "invalid_rows": errors, "count": len(parsed)})

    user_id = int(get_jwt_identity())
    # Conservative duplicate check for demo: same user/date/description/amount/kind.
    existing = {
        (t.date, t.description.lower(), t.amount, t.kind)
        for t in Transaction.query.filter_by(user_id=user_id).all()
    }
    added = 0
    duplicates = 0
    for item in parsed:
        key = (item["date"], item["description"].lower(), item["amount"], item["kind"])
        if key in existing:
            duplicates += 1
            continue
        db.session.add(Transaction(
            user_id=user_id, date=item["date"], description=item["description"],
            amount=item["amount"], category=item["category"], kind=item["kind"], source="csv"
        ))
        existing.add(key)
        added += 1
    db.session.commit()
    return jsonify({
        "imported": added, "possible_duplicates_skipped": duplicates,
        "invalid_rows": errors,
        "note": "Review imported categories. Duplicate matching is heuristic and may need manual review."
    }), 201
