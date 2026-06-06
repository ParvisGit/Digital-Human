import logging
from Banking_agent.app.Schemas.fetch_balance import Customer, Account
from Banking_agent.app.Schemas.fetch_N_transaction import Transaction

logger = logging.getLogger("banking_agent.db")


def fetch_last_n_transactions(customer_dict: dict) -> dict:
    """
    Fetches last N transactions for a customer.
    """
    try:
        customer_name = customer_dict.get("customer_name")
        n = customer_dict.get("n", 2)
        logger.info("[TRANSACTIONS] Query: customer_name=%s n=%s", customer_name, n)
        customer = Customer.objects(Full_Name__iexact=customer_name).first()
        logger.info("[TRANSACTIONS] Customer lookup: %s", customer.Full_Name if customer else "NOT FOUND")
        if not customer:
            result = {"error": "Customer not found"}
            logger.info("[TRANSACTIONS] Response: %s", result)
            return result
        account = Account.objects(Customer_ID=customer.Customer_ID).first()
        if not account:
            result = {"error": "Account not found"}
            logger.info("[TRANSACTIONS] Response: %s", result)
            return result
        transactions = (Transaction.objects(Customer_ID=customer.Customer_ID)
                    .order_by("-Transaction_Date", "-TransactionID")
                    .limit(n))
        txn_list = []
        for txn in transactions:
            txn_list.append({"TransactionID": txn.TransactionID,
                            "Transaction_Type": txn.Transaction_Type,
                            "Transaction_Amount": float(txn.Transaction_Amount),
                            "Transaction_Date": txn.Transaction_Date,
                            "Account_Balance_After_Transaction": float(txn.Account_Balance_After_Transaction)})

        result = {"Customer_Name": customer.Full_Name,
                "Account_Type": account.Account_Type,
                "Requested_n": n,
                "Returned_n": len(txn_list),
                "Last_N_Transactions": txn_list}
        logger.info("[TRANSACTIONS] Response: %s", result)
        return result
    except Exception as e:
        logger.exception("[TRANSACTIONS] Error: %s", e)
        return f"Error while running fetch_last_n_transactions: {e}"
