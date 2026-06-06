from Banking_agent.app.Schemas.credit_card import CreditCard
from Banking_agent.app.Schemas.fetch_balance import Customer


def get_credit_card_details(customer_name: str):
    customer = Customer.objects(Full_Name__iexact=customer_name).first()
    if not customer:
        return {"error": "Customer not found"}

    card = CreditCard.objects(Customer_ID=customer.Customer_ID).first()
    if not card:
        return {"error": "No credit card record found for this customer"}

    available_credit = float(card.Credit_Limit) - float(card.Credit_Card_Balance)
    return {
        "card_type": card.Card_Type,
        "credit_limit": float(card.Credit_Limit),
        "current_balance": float(card.Credit_Card_Balance),
        "available_credit": round(available_credit, 2),
        "minimum_payment_due": float(card.Minimum_Payment_Due),
        "payment_due_date": card.Payment_Due_Date,
        "last_payment_date": card.Last_Credit_Card_Payment_Date,
    }


def get_credit_card_transactions(customer_name: str, n: int = 5):
    from Banking_agent.app.Schemas.fetch_N_transaction import Transaction

    customer = Customer.objects(Full_Name__iexact=customer_name).first()
    if not customer:
        return {"error": "Customer not found"}

    card = CreditCard.objects(Customer_ID=customer.Customer_ID).first()
    if not card:
        return {"error": "No credit card record found for this customer"}

    txns = Transaction.objects(Customer_ID=customer.Customer_ID).order_by("-Transaction_Date")[:n]

    if not txns:
        return {"message": "No recent transactions found.", "transactions": []}

    return {
        "card_type": card.Card_Type,
        "transactions": [
            {
                "amount": float(t.Transaction_Amount),
                "type": t.Transaction_Type,
                "date": str(t.Transaction_Date),
                "balance_after": float(t.Account_Balance_After_Transaction)
            } for t in txns
        ]
    }


CARD_TIERS = [
    {
        "tier": "Signature",
        "min_cibil": 800,
        "credit_limit": "Up to 5 lakh rupees",
        "benefits": "Airport lounge access, 5x reward points on travel and dining, complimentary travel insurance, zero forex markup",
        "annual_fee": "2500 rupees (waived on annual spend above 3 lakh rupees)",
    },
    {
        "tier": "Platinum",
        "min_cibil": 750,
        "credit_limit": "Up to 3 lakh rupees",
        "benefits": "2x reward points on all spends, fuel surcharge waiver, movie ticket discounts, complimentary lounge access 4 times per year",
        "annual_fee": "1000 rupees (waived on annual spend above 1.5 lakh rupees)",
    },
    {
        "tier": "Gold",
        "min_cibil": 700,
        "credit_limit": "Up to 1.5 lakh rupees",
        "benefits": "1.5x reward points on online shopping, fuel surcharge waiver, EMI conversion on purchases above 3000 rupees",
        "annual_fee": "500 rupees (waived on annual spend above 75 thousand rupees)",
    },
    {
        "tier": "Silver",
        "min_cibil": 650,
        "credit_limit": "Up to 75 thousand rupees",
        "benefits": "1x reward points on all spends, basic fuel surcharge waiver, EMI conversion available",
        "annual_fee": "250 rupees",
    },
]


def check_credit_card_eligibility(customer_name: str):
    customer = Customer.objects(Full_Name__iexact=customer_name).first()
    if not customer:
        return {"error": "Customer not found"}

    age = customer.Age or 0
    cibil = customer.Cibil_score or 0

    # Check if customer already has a credit card
    existing_card = CreditCard.objects(Customer_ID=customer.Customer_ID).first()
    has_existing_card = existing_card is not None

    # Credit utilization (if they already have a card)
    credit_utilization = 0.0
    if has_existing_card and float(existing_card.Credit_Limit) > 0:
        credit_utilization = round(
            (float(existing_card.Credit_Card_Balance) / float(existing_card.Credit_Limit)) * 100, 1
        )

    result = {
        "customer_name": customer.Full_Name,
        "age": age,
        "cibil_score": cibil,
        "has_existing_card": has_existing_card,
        "credit_utilization": credit_utilization,
    }

    # Eligibility rules
    if age < 21:
        result["eligible"] = False
        result["reason"] = f"Minimum age requirement is 21 years. Customer is {age} years old."
        return result

    if cibil < 650:
        result["eligible"] = False
        result["reason"] = f"Minimum CIBIL score required is 650. Customer's CIBIL score is {cibil}."
        if cibil > 0:
            result["suggestion"] = "Customer can improve their CIBIL score by paying bills on time, reducing outstanding debt, and maintaining a healthy credit utilization ratio."
        return result

    if credit_utilization > 80:
        result["eligible"] = True
        result["high_utilization_warning"] = True
        result["reason"] = f"Customer is eligible but has high credit utilization at {credit_utilization} percent. Recommend reducing outstanding balance before applying for a new card."
    else:
        result["eligible"] = True
        result["reason"] = "Customer meets all eligibility criteria."

    return result


def recommend_credit_card(customer_name: str):
    customer = Customer.objects(Full_Name__iexact=customer_name).first()
    if not customer:
        return {"error": "Customer not found"}

    cibil = customer.Cibil_score or 0

    if cibil < 650:
        return {
            "eligible": False,
            "message": "Customer does not meet the minimum CIBIL score of 650 for any credit card."
        }

    # Find all eligible tiers (customer qualifies for all tiers at or below their CIBIL)
    eligible_cards = [tier for tier in CARD_TIERS if cibil >= tier["min_cibil"]]

    if not eligible_cards:
        return {
            "eligible": False,
            "message": "No suitable credit card found for the customer's profile."
        }

    # Best card is the first match (highest tier they qualify for)
    best_card = eligible_cards[0]
    other_options = eligible_cards[1:] if len(eligible_cards) > 1 else []

    return {
        "eligible": True,
        "cibil_score": cibil,
        "best_recommendation": {
            "tier": best_card["tier"],
            "credit_limit": best_card["credit_limit"],
            "benefits": best_card["benefits"],
            "annual_fee": best_card["annual_fee"],
        },
        "other_options": [
            {"tier": card["tier"], "credit_limit": card["credit_limit"], "annual_fee": card["annual_fee"]}
            for card in other_options
        ],
        "message": f"Based on the customer's CIBIL score of {cibil}, the best suited card is the {best_card['tier']} card."
    }


def get_credit_card_balance(customer_name: str):
    customer = Customer.objects(Full_Name__iexact=customer_name).first()
    if not customer:
        return {"error": "Customer not found"}

    card = CreditCard.objects(Customer_ID=customer.Customer_ID).first()
    if not card:
        return {"error": "No credit card record found"}

    return {
        "current_balance": float(card.Credit_Card_Balance),
        "minimum_payment_due": float(card.Minimum_Payment_Due),
        "payment_due_date": card.Payment_Due_Date,
    }
