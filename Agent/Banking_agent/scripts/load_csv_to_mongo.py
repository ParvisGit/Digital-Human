#!/usr/bin/env python3
"""
Load Updated_database.csv into MongoDB using the Banking agent schemas.
Collections: Customers_Collection, Accounts_Collection, Transactions_Collection
"""
import os
import sys
import csv
from datetime import datetime
from decimal import Decimal
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger("csv_loader")

# Add parent to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))
os.chdir(os.path.join(os.path.dirname(__file__), "../.."))

# Set credentials before any Google imports (vertex-gemini-agent.json is in Agent/BFSI/)
_script_dir = os.path.dirname(os.path.abspath(__file__))
_bfsi_dir = os.path.dirname(os.path.dirname(_script_dir))
os.environ.setdefault(
    "GOOGLE_APPLICATION_CREDENTIALS",
    os.path.join(_bfsi_dir, "vertex-gemini-agent.json"),
)

from Banking_agent.app.db.mongo import connect_db
from Banking_agent.app.Schemas.fetch_balance import Customer, Account
from Banking_agent.app.Schemas.fetch_N_transaction import Transaction
from Banking_agent.app.Schemas.loan import Loan
from Banking_agent.app.Schemas.credit_card import CreditCard


def parse_date(value):
    """Parse date string to datetime."""
    if not value:
        return None
    try:
        return datetime.strptime(value.strip(), "%Y-%m-%d")
    except ValueError:
        return None


def parse_decimal(value):
    """Parse string to Decimal."""
    if value is None or value == "":
        return Decimal("0")
    try:
        return Decimal(str(value).strip())
    except Exception:
        return Decimal("0")


def parse_int(value):
    """Parse string to int."""
    if value is None or value == "":
        return None
    try:
        return int(float(str(value).strip()))
    except (ValueError, TypeError):
        return None


def load_csv_to_mongo(csv_path: str, clear_existing: bool = True):
    """Load CSV data into MongoDB collections."""
    connect_db()
    logger.info("MongoDB connection established.")

    if clear_existing:
        print("Clearing existing collections...")
        logger.info("Clearing existing collections...")
        Customer.objects.delete()
        Account.objects.delete()
        Transaction.objects.delete()
        Loan.objects.delete()
        CreditCard.objects.delete()
        print("Cleared.")
        logger.info("Collections cleared successfully.")

    csv_path = os.path.abspath(csv_path)
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"CSV not found: {csv_path}")

    customers_created = set()
    accounts_created = set()
    loans_created = set()
    cards_created = set()

    with open(csv_path, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    print(f"Loading {len(rows)} rows from {csv_path}...")
    logger.info(
    "Loading %s rows from %s",
    len(rows),
    csv_path
)

    for row in rows:
        customer_id = parse_int(row.get("Customer_ID"))
        if customer_id is None:
            logger.warning("Skipping row with invalid Customer_ID: %s", row )
            continue

        # 1. Create Customer (if not exists)
        if customer_id not in customers_created:
            try:
                Customer(
                    Customer_ID=customer_id,
                    Full_Name=row.get("Full_Name", "").strip(),
                    Age=parse_int(row.get("Age")),
                    Gender=row.get("Gender", "").strip(),
                    Address=row.get("Address", "").strip(),
                    City=row.get("City", "").strip(),
                    Contact_Number=row.get("Contact_Number", "").strip(),
                    Email=row.get("Email", "").strip(),
                    Cibil_score=parse_int(row.get("Cibil_score")),
                ).save()
                customers_created.add(customer_id)
            except Exception as e:
                print(f"  Skip customer {customer_id}: {e}")

        # 2. Create Account (if not exists)
        if customer_id not in accounts_created:
            try:
                Account(
                    Customer_ID=customer_id,
                    Account_Number=f"ACC{customer_id:06d}",
                    Account_Type=row.get("Account_Type", "Current").strip(),
                    Account_Balance=parse_decimal(row.get("Account_Balance")),
                    Date_Of_Account_Opening=parse_date(row.get("Date_Of_Account_Opening")),
                    Branch_ID=str(row.get("Branch_ID", "")).strip() or None,
                ).save()
                accounts_created.add(customer_id)
            except Exception as e:
                print(f"  Skip account for customer {customer_id}: {e}")

        # 3. Create Transaction (each row = one transaction)
        try:
            Transaction(
                Customer_ID=customer_id,
                TransactionID=parse_int(row.get("TransactionID")) or 0,
                Transaction_Amount=parse_decimal(row.get("Transaction_Amount")),
                Transaction_Type=row.get("Transaction_Type", "").strip(),
                Transaction_Date=parse_date(row.get("Transaction_Date")) or datetime.now(),
                Account_Balance_After_Transaction=parse_decimal(row.get("Account_Balance_After_Transaction")),
                Account_status=row.get("Account_status", "").strip(),
                card_status=row.get("card_status", "").strip(),
            ).save()
        except Exception as e:
            print(f"  Skip transaction {row.get('TransactionID')} for customer {customer_id}: {e}")

        # 4. Create Loan (if not exists)

        loan_id = parse_int(row.get("LoanID"))

        if loan_id and loan_id not in loans_created:
            try:
                Loan(
                    Customer_ID=customer_id,
                    LoanID=loan_id,
                    Loan_Amount=parse_decimal(row.get("Loan_Amount")),
                    Loan_Type=row.get("Loan_Type", "").strip(),
                    Interest_Rate=parse_decimal(row.get("Interest_Rate")),
                    Loan_Term=parse_int(row.get("Loan_Term")),
                    Approval_Rejection_Date=row.get(
                        "Approval/Rejection_Date", ""
                    ).strip(),
                    Loan_Status=row.get("Loan_Status", "").strip(),
                ).save()

                loans_created.add(loan_id)

            except Exception as e:
                print(f"  Skip loan {loan_id}: {e}")

        print( f"Done.\n"
                f"Customers: {len(customers_created)}\n"
                f"Accounts: {len(accounts_created)}\n"
                f"Transactions: {len(rows)}\n"
                f"Loans: {len(loans_created)}\n"
                f"Credit Cards: {len(cards_created)}"
            )

        # 5. Create Credit Card (if not exists)

        card_id = parse_int(row.get("CardID"))

        if card_id and card_id not in cards_created:
            try:
                CreditCard(
                    Customer_ID=customer_id,
                    CardID=card_id,
                    Card_Type=row.get("Card_Type", "").strip(),
                    Credit_Limit=parse_decimal(
                        row.get("Credit_Limit")
                    ),
                    Credit_Card_Balance=parse_decimal(
                        row.get("Credit_Card_Balance")
                    ),
                    Minimum_Payment_Due=parse_decimal(
                        row.get("Minimum_Payment_Due")
                    ),
                    Payment_Due_Date=row.get(
                        "Payment_Due_Date", ""
                    ).strip(),
                    Last_Credit_Card_Payment_Date=row.get(
                        "Last_Credit_Card_Payment_Date", ""
                    ).strip(),
                ).save()

                cards_created.add(card_id)

            except Exception as e:
                print(f"  Skip credit card {card_id}: {e}")


if __name__ == "__main__":
    csv_path = os.path.join(
        os.path.dirname(__file__), "..", "Updated_database.csv"
    )
    clear = "--keep" not in sys.argv
    load_csv_to_mongo(csv_path, clear_existing=clear)