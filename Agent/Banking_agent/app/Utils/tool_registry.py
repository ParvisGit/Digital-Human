"""
AVA-style tool registry: collect all tools by name for agent assignment.
"""
from Banking_agent.app.Tools.balance_tools import fetch_account_balance_tool
from Banking_agent.app.Tools.transaction_tools import fetch_last_n_transactions_tool
from Banking_agent.app.Tools.account_tools import fetch_account_field_tool
from Banking_agent.app.Tools.transaction_field_tools import fetch_transaction_field_tool
from Banking_agent.app.Tools.customer_tools import fetch_customer_field_tool
from Banking_agent.app.Tools.validation_tools import fetch_customer_name_tool, verify_customer_identity_tool
from Banking_agent.app.Tools.fraud_tools import (
    suspicious_transactions_tool,
    block_card_tool,
    freeze_account_tool,
    flag_account_tool,
    report_fraud_tool,
    unblock_card_tool,
    unfreeze_account_tool,
    check_fraud_case_status_tool
)
from Banking_agent.app.Tools.loan_tools import fetch_loan_details_tool, fetch_loan_status_tool
from Banking_agent.app.Tools.credit_card_tools import (
    fetch_credit_card_details_tool,
    fetch_credit_card_balance_tool,
    fetch_credit_card_transactions_tool,
    credit_card_eligibility_tool,
    credit_card_recommendation_tool,
)
from Banking_agent.app.Tools.service_request_tools import raise_service_request_tool
from Banking_agent.app.Tools.grievance_tools import register_complaint_tool
from Banking_agent.app.Tools.profile_update_tools import raise_profile_update_request_tool
from Banking_agent.app.Tools.escalation_tools import escalate_to_human_tool
from Banking_agent.app.Tools.otp_tools import send_otp_tool, send_otp_email_tool, verify_otp_tool

TOOL_REGISTRY = {
    "fetch_account_balance_tool": fetch_account_balance_tool,
    "fetch_last_n_transactions_tool": fetch_last_n_transactions_tool,
    "fetch_account_field_tool": fetch_account_field_tool,
    "fetch_transaction_field_tool": fetch_transaction_field_tool,
    "fetch_customer_field_tool": fetch_customer_field_tool,
    "fetch_customer_name_tool": fetch_customer_name_tool,
    "verify_customer_identity_tool": verify_customer_identity_tool,
    "suspicious_transactions_tool": suspicious_transactions_tool,
    "block_card_tool": block_card_tool,
    "freeze_account_tool": freeze_account_tool,
    "flag_account_tool": flag_account_tool,
    "report_fraud_tool": report_fraud_tool,
    "unblock_card_tool": unblock_card_tool,
    "unfreeze_account_tool": unfreeze_account_tool,
    "check_fraud_case_status_tool": check_fraud_case_status_tool,
    "fetch_loan_details_tool": fetch_loan_details_tool,
    "fetch_loan_status_tool": fetch_loan_status_tool,
    "fetch_credit_card_details_tool": fetch_credit_card_details_tool,
    "fetch_credit_card_balance_tool": fetch_credit_card_balance_tool,
    "fetch_credit_card_transactions_tool": fetch_credit_card_transactions_tool,
    "credit_card_eligibility_tool": credit_card_eligibility_tool,
    "credit_card_recommendation_tool": credit_card_recommendation_tool,
    "raise_service_request_tool": raise_service_request_tool,
    "register_complaint_tool": register_complaint_tool,
    "raise_profile_update_request_tool": raise_profile_update_request_tool,
    "escalate_to_human_tool": escalate_to_human_tool,
    "send_otp_tool": send_otp_tool,
    "send_otp_email_tool": send_otp_email_tool,
    "verify_otp_tool": verify_otp_tool,
}
