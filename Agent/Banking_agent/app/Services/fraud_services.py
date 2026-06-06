from datetime import datetime
from Banking_agent.app.Schemas.fraud_audit import FraudAudit
from Banking_agent.app.Schemas.fetch_balance import Customer, Account
from Banking_agent.app.Schemas.fetch_N_transaction import Transaction

def create_fraud_case(customer_name: str, reason: str):
    FraudAudit(
        Customer_Name=customer_name,
        Action="FRAUD_REPORTED",
        Metadata={"reason": reason},
        Timestamp=datetime.utcnow()
    ).save()

    return {
        "status": "case_created",
        "message": "A fraud case has been registered and our team will investigate."
    }


def flag_account(customer_name: str):
    from Banking_agent.app.Schemas.fetch_balance import Customer, Account

    customer = Customer.objects(Full_Name__iexact=customer_name).first()
    if not customer:
        return {"error": "Customer not found"}
    
    account = Account.objects(Customer_ID=customer.Customer_ID).first()
    if not account:
        return {"error": "Account not found"}


    account.update(set__Fraud_Flag="YES")
    FraudAudit(Customer_Name=customer_name, Action="Account_flagged").save()
    return {"status": "flagged"}

def block_card(customer_name: str):
    from Banking_agent.app.Schemas.fetch_balance import Customer

    customer = Customer.objects(Full_Name__iexact=customer_name).first()
    if not customer:
        return {"error": "Customer not found"}

    latest_txn = Transaction.objects(Customer_ID=customer.Customer_ID).order_by("-Transaction_Date").first()
    if not latest_txn:
        return {"error": "No transactions found for this customer"}

    if getattr(latest_txn, "card_status", "ACTIVE") == "BLOCKED":
        return {"status": "already_blocked", "message": "Your card is already blocked."}

    Transaction.objects(Customer_ID=customer.Customer_ID).update(set__card_status="BLOCKED")
    FraudAudit(Customer_Name=customer_name, Action="Card Blocked").save()
    return {
        "status": "blocked",
        "message": "Your card has been blocked successfully for security reasons."
    }

def freeze_account(customer_name: str):
    customer = Customer.objects(Full_Name__iexact=customer_name).first()
    if not customer:
        return {"error": "Customer not found"}

    latest_txn = Transaction.objects(Customer_ID=customer.Customer_ID).order_by("-Transaction_Date").first()
    if not latest_txn:
        return {"error": "No transactions found for this customer"}

    if getattr(latest_txn, "Account_status", "ACTIVE") == "FROZEN":
        return {"status": "already_frozen", "message": "Your account is already frozen."}

    Transaction.objects(Customer_ID=customer.Customer_ID).update(set__Account_status="FROZEN")
    FraudAudit(Customer_Name=customer_name, Action="Account Freezed").save()
    return {"status": "frozen", "message": "Your account has been frozen successfully for security."}

def unblock_card(customer_name: str):
    customer = Customer.objects(Full_Name__iexact=customer_name).first()
    if not customer:
        return {"error": "Customer not found"}

    latest_txn = Transaction.objects(Customer_ID=customer.Customer_ID).order_by("-Transaction_Date").first()
    if not latest_txn:
        return {"error": "No transactions found for this customer"}

    if getattr(latest_txn, "card_status", "ACTIVE") != "BLOCKED":
        return {"status": "already_active", "message": "Your card is already active. No action is needed."}

    Transaction.objects(Customer_ID=customer.Customer_ID).update(set__card_status="ACTIVE")
    FraudAudit(Customer_Name=customer_name, Action="Card Unblocked", Timestamp=datetime.utcnow()).save()
    return {
        "status": "unblocked",
        "message": "Your card has been unblocked successfully. You can now use it for transactions."
    }


def unfreeze_account(customer_name: str):
    customer = Customer.objects(Full_Name__iexact=customer_name).first()
    if not customer:
        return {"error": "Customer not found"}

    latest_txn = Transaction.objects(Customer_ID=customer.Customer_ID).order_by("-Transaction_Date").first()
    if not latest_txn:
        return {"error": "No transactions found for this customer"}

    if getattr(latest_txn, "Account_status", "ACTIVE") != "FROZEN":
        return {"status": "already_active", "message": "Your account is already active. No action is needed."}

    Transaction.objects(Customer_ID=customer.Customer_ID).update(set__Account_status="ACTIVE")
    FraudAudit(Customer_Name=customer_name, Action="Account Unfrozen", Timestamp=datetime.utcnow()).save()
    return {
        "status": "unfrozen",
        "message": "Your account has been unfrozen successfully. You can now perform transactions."
    }


def check_fraud_case_status(customer_name: str):
    cases = FraudAudit.objects(Customer_Name__iexact=customer_name).order_by("-Timestamp")[:10]

    if not cases:
        return {
            "status": "no_cases",
            "message": "No fraud cases found for your account."
        }

    case_list = []
    for case in cases:
        case_list.append({
            "action": case.Action,
            "timestamp": str(case.Timestamp),
            "metadata": case.Metadata or {}
        })

    return {
        "status": "found",
        "total_cases": len(case_list),
        "cases": case_list,
        "message": f"Found {len(case_list)} fraud-related records for your account."
    }


def get_and_flag_suspicious_transactions(customer_name: str):
    customer = Customer.objects(Full_Name__iexact=customer_name).first()
    if not customer:
        return {"error": "Customer not found"}

    txns = Transaction.objects(Customer_ID=customer.Customer_ID).order_by("-Transaction_Date")[:5]

    FraudAudit(Customer_Name=customer_name, Action="SUSPICIOUS_ACTIVITY_REPORTED").save()

    return {
        "status": "review_started",
        "transactions": [
            {
                "amount": t.Transaction_Amount,
                "date": str(t.Transaction_Date),
                "type": t.Transaction_Type
            } for t in txns
        ]
    }