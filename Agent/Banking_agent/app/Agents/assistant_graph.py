"""
Multi-agent banking graph: tool-based routing, ChatPromptTemplate + bind_tools.
greeting_agent is the main entry; routes via to_<agent> tools.
"""
import json
import logging
import re
from typing import Annotated, TypedDict

logger = logging.getLogger("banking_agent.graph")

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.graph import StateGraph, END, START
from langgraph.graph.message import add_messages
from Banking_agent.app.db.redis_chat import get_checkpointer
from Banking_agent.app.Agents.runnables import load_config, create_agent_runnables
from Banking_agent.app.Utils.tool_registry import TOOL_REGISTRY
from Banking_agent.app.Utils.tool_node import create_tool_node
from Banking_agent.app.Utils.prompt_cache_loader import preload_prompts

def _keep_latest_non_empty(old: str, new: str) -> str:
    if new and new.strip():
        return new
    return old


def _keep_latest_non_empty_str(old: str, new: str) -> str:
    """Reducer for string fields: keep the latest non-empty value."""
    if new and new.strip():
        return new
    return old


def _merge_session_context(old: dict, new: dict) -> dict:
    """Reducer for session_context: merge new into old, never lose existing keys."""
    if not old:
        return new or {}
    if not new:
        return old
    return {**old, **{k: v for k, v in new.items() if v is not None}}


def _looks_like_name(text: str) -> bool:
    """Heuristic: 1-4 words, mostly letters, no digits, not a greeting."""
    if not text or len(text) > 80:
        return False
    low = text.strip().lower()
    if low in ("hi", "hello", "hey", "ok", "yes", "no"):
        return False
    parts = text.strip().split()
    if not 1 <= len(parts) <= 4:
        return False
    return all(len(p) >= 2 and p.replace("-", "").replace("'", "").isalpha() for p in parts)

def _extract_text(content) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                parts.append(item.get("text", ""))
            else:
                parts.append(str(item))
        return "".join(parts)
    return str(content)

class State(TypedDict, total=False):
    """Graph state: messages, dialog_state, phone_number, session_id, session_context."""
    messages: Annotated[list, add_messages]
    dialog_state: Annotated[str, _keep_latest_non_empty]
    phone_number: Annotated[str, _keep_latest_non_empty_str]
    session_id: Annotated[str, _keep_latest_non_empty_str]
    session_context: Annotated[dict, _merge_session_context]


def _build_ava_style_graph():
    """Build the AVA-style graph from config."""
    config = load_config()
    agent_runnables = create_agent_runnables(config, TOOL_REGISTRY)

    agent_names = [a["name"] for a in config["agents"]]
    agent_set = set(agent_names)

    # Build delegate tools and tool lists per agent
    agent_descriptions = {a["name"]: a.get("description", "") for a in config["agents"]}

    def make_delegate(name: str):
        from langchain_core.tools import Tool
        desc = agent_descriptions.get(name, "")

        def _delegate(tool_input: dict | str):
            return f"Delegating to {name}"

        return Tool(
            name=f"to_{name}",
            description=f"Delegate to {name}. {desc}. Pass the user's message and context.",
            func=_delegate,
        )

    builder = StateGraph(State)

    for agent_cfg in config["agents"]:
        agent_name = agent_cfg["name"]
        runnable = agent_runnables[agent_name]

        # Tools for this agent (excluding delegates - those are in the runnable)
        available_tools = [
            TOOL_REGISTRY[t] for t in agent_cfg.get("tools", [])
            if t in TOOL_REGISTRY
        ]
        tool_node = create_tool_node(available_tools)

        def create_assistant_node(name: str, runnable=runnable):
            async def _node(state: dict):
                msgs = state.get("messages", [])

                # Skip LLM if direct routing already decided
                last = msgs[-1] if msgs else None
                if isinstance(last, AIMessage) and getattr(last, "tool_calls", None):
                    for tc in last.tool_calls:
                        if tc.get("id", "").startswith("direct_"):
                            logger.info("[%s] Skipping LLM — direct route via %s", name, tc.get("name"))
                            return {"messages": []}

                # Call LLM
                result = await runnable.ainvoke({"messages": msgs})

                _raw_content = getattr(result, "content", "") or ""
                print("RAWWWWWWWWW CONTENT", _raw_content)
                if isinstance(_raw_content, list):
                    # Newer Gemini SDKs (e.g. gemini-2.5-flash) return content as
                    # a list of parts like [{"type": "text", "text": "..."}, ...].
                    # Concatenate text parts so downstream string ops keep working.
                    content = "".join(
                        (
                            part.get("text", "")
                            if isinstance(part, dict)
                            else str(part)
                        )
                        for part in _raw_content
                    )
                    print("CONTENTTTTTT",content)
                else:
                    content = str(_raw_content)
                result_tool_calls = getattr(result, "tool_calls", []) or []
                print("result_tools_Callssssss",result_tool_calls)

                # AUTH GUARD — enforce authentication for protected agents
                _auth_required_agents = {"fraud_detection_agent", "loan_agent", "credit_card_agent"}
                if name in _auth_required_agents:

                    is_authenticated = False

                    for m in reversed(state.get("messages", [])):
                        if isinstance(m, ToolMessage):
                            try:
                                td = json.loads(m.content) if isinstance(m.content, str) else m.content
                                if isinstance(td, dict) and (
                                    td.get("authenticated") is True
                                    or td.get("otp_verified") is True
                                ):
                                    is_authenticated = True
                                    break
                            except:
                                pass

                    # fallback to session_context
                    if not is_authenticated:
                        session = state.get("session_context", {})
                        is_authenticated = session.get("authenticated", False)

                    # fallback to session store (authoritative source)
                    if not is_authenticated:
                        from Banking_agent.app.db.session_store import get_session as _get_session
                        _sid = state.get("session_id", "")
                        if _sid:
                            is_authenticated = _get_session(_sid).get("authenticated", False)

                    if not is_authenticated:
                        logger.info("[%s] Not authenticated → redirecting to auth", name)

                        return {
                            "messages": [
                                AIMessage(
                                    content="",
                                    tool_calls=[{
                                        "name": "to_authentication_agent",
                                        "args": {
                                            "customer_name": "",
                                            "phone_number": "",
                                            "message": f"{name} request"
                                        },
                                        "id": f"auth_redirect_{id(state)}",
                                    }],
                                )
                            ]
                        }

                if name in _auth_required_agents and "routing" in content.lower():
                    logger.warning("[%s] Blocking useless routing response", name)
                    return {"messages": []}

                # AUTH GUARD: block verify if phone wasn't confirmed by customer
                if name == "authentication_agent" and result_tool_calls:
                    for tc in result_tool_calls:
                        if tc.get("name") == "verify_customer_identity_tool":
                            phone_arg = (tc.get("args") or {}).get("phone_number", "")
                            user_provided_phone = False

                            # Check if directive pre-confirmed the phone (from entry node)
                            for m in reversed(msgs):
                                if isinstance(m, SystemMessage):
                                    sc = (getattr(m, "content", "") or "")
                                    if "CONFIRMED their phone" in sc or "ALREADY CONFIRMED" in sc:
                                        user_provided_phone = True
                                        logger.info("[%s] Phone pre-confirmed by directive", name)
                                        break
                                    if "calling from phone number" in sc or "phone number" in sc:
                                        match = re.search(r"phone.?number[\"= ]+(\d+)", sc)
                                        if match:
                                            context_phone_in_history = match.group(1)
                                            if phone_arg.endswith(context_phone_in_history[-10:]):
                                                # Check if user said yes/confirmed in messages
                                                confirm_words = ("yes", "yeah", "yep", "correct", "right", "confirmed")
                                                for hm in msgs:
                                                    if isinstance(hm, HumanMessage):
                                                        ht = (getattr(hm, "content", "") or "").strip().lower()
                                                        if any(ht.startswith(w) for w in confirm_words):
                                                            user_provided_phone = True
                                                            break
                                                        digits = "".join(c for c in ht if c.isdigit())
                                                        if digits and len(digits) >= 10 and phone_arg.endswith(digits[-10:]):
                                                            user_provided_phone = True
                                                            break
                                        break

                            if not user_provided_phone:
                                logger.warning("[%s] Blocked verify — phone not confirmed", name)
                                result = AIMessage(
                                    content="Could you please confirm the phone number registered with your account?"
                                )

                # AUTH POST-ROUTING: always route by intent after successful auth(never letting the LLM's default to_balance_transactions_agent win)
                if name == "authentication_agent":
                    auth_customer = ""
                    for m in reversed(msgs):
                        if isinstance(m, ToolMessage):
                            try:
                                td = json.loads(m.content) if isinstance(m.content, str) else m.content
                                if isinstance(td, dict) and td.get("otp_verified") is True:
                                    auth_customer = td.get("customer_name", "")
                            except:
                                pass
                            break

                    if auth_customer:
                        # full_history = " ".join([
                        #     getattr(m, "content", "").lower()
                        #     for m in msgs if hasattr(m, "content")
                        # ])
                        full_history = " ".join(
                                        _extract_text(getattr(m, "content", "")).lower()
                                        for m in msgs
                                        if hasattr(m, "content")
                                    )
                        # Read original question from MongoDB session store (reliable)
                        # This was saved when the entry node first routed to auth
                        from Banking_agent.app.db.session_store import get_session as _get_oq
                        _oq_session = _get_oq(state.get("session_id", ""))
                        original_user_msg = _oq_session.get("original_question", "")

                        # Fallback: scan message history if session store doesn't have it
                        if not original_user_msg:
                            _confirm_words = {"yes", "no", "yeah", "nope", "correct", "confirmed", "ok", "okay"}
                            for m in reversed(msgs):
                                if isinstance(m, HumanMessage):
                                    text = (getattr(m, "content", "") or "").strip()
                                    _is_customer_name = (
                                        text.lower().strip() == auth_customer.lower().strip()
                                        if auth_customer else False
                                    )
                                    if (
                                        text.lower() not in _confirm_words
                                        and not text.isdigit()
                                        and len(text) > 2
                                        and not _is_customer_name
                                    ):
                                        original_user_msg = text
                                        break
                        logger.info("[%s] original_user_msg=%s (source=%s)", name, original_user_msg, "session_store" if _oq_session.get("original_question") else "history")

                        fraud_kws = [
                            "fraud", "suspicious", "unauthorized", "unauthorised",
                            "stolen", "lost card", "lost my card",
                            "unknown transaction", "unknown debit", "unknown charge",
                            "i didn't", "i didnt", "i did not", "i haven't", "i havent",
                            "not my transaction", "not me", "not mine",
                            "didn't make", "didnt make", "did not make",
                            "didn't authorize", "didnt authorize", "did not authorize",
                            "freeze", "block", "block my card", "block my account",
                            "unblock", "unfreeze", "reactivate",
                            "report fraud", "scam", "hack", "phishing",
                            "compromised", "strange debit", "weird transaction",
                            "scared", "worried about my account",
                            "shared my otp", "shared my password", "clicked a link",
                            "fraud status", "fraud case",
                            "reverse transaction", "refund",
                            "changed my email without", "changed my phone without",
                            "without my permission", "without my knowledge",
                            "someone changed", "tampered",
                            "someone has my account", "account access", "access to my account",
                            "hacked my account", "hacked my", "someone using my",
                            "unauthorized access", "unauthorised access",
                            "someone has access", "has access to my",
                            "is my account safe", "account safe", "am i safe",
                            "is it safe", "is my card safe", "blocking my card",
                            "never made", "didn't do", "didnt do",
                            "monitoring", "watch my account", "keep a watch",
                            "panicked", "entered my details", "entered all my details",
                            "message with a link", "got a link",
                        ]
                        credit_card_kws = [
                            "credit card", "credit limit", "card balance", "minimum payment",
                            "card type", "card details", "card transactions",
                            "increase my limit", "increase credit", "higher limit",
                            "eligible for credit", "apply for credit", "apply for card",
                            "want a credit card", "get a credit card", "qualify for card",
                            "recommend me a card", "recommend a card", "best card",
                            "which card should", "which card is best", "what cards do you",
                            "card is best", "best for me",
                            "available to spend", "minimum amount", "need to pay",
                            "last payment", "close it", "don't use this card",
                            "convert it to emi",
                            "close my card", "cancel my card", "card closure",
                            "card dispute", "dispute a charge",
                            "how much do i owe", "payment due", "available credit",
                            "convert to emi", "reward", "cashback",
                            "missed payment", "late payment",
                        ]
                        loan_kws = [
                            "loan", "emi", "mortgage", "interest rate", "loan status",
                            "loan balance", "loan amount", "repayment", "loan term",
                            "auto loan", "personal loan", "home loan"
                        ]
                        grievance_kws = [
                            "complaint", "complain", "compliant", "grievance", "wrong charge",
                            "incorrect debit", "fee dispute", "service issue",
                            "register complaint", "lodge complaint", "wrong fee",
                            "charged wrongly", "raise a",
                            "issue with", "problem with", "not happy", "not satisfied",
                            "wrong transfer", "wrong upi", "wrong account number",
                            "sent money to wrong", "transferred by mistake",
                            "sent to wrong", "money by mistake", "accidental transfer",
                            "mistaken transfer", "sent money by mistake",
                            "annual fee", "seeing charges", "charges for it",
                            "app crashing", "app not working", "can't login", "cant login",
                            "app has been crashing", "mobile app",
                            "entered the wrong", "wrong number by mistake",
                            "frustrated", "frustrating", "trying to reach",
                            "disappointed", "terrible service", "terrible",
                        ]

                        def _kw_match(kw, text):
                            """Word-boundary keyword match to avoid substring false positives."""
                            if " " in kw:
                                return kw in text
                            return bool(re.search(r'\b' + re.escape(kw) + r'\b', text))

                        # Combine full_history with original_user_msg for intent matching
                        # (full_history may be empty if checkpoint was lost)
                        _intent_text = full_history + " " + (original_user_msg or "").lower()

                        if any(_kw_match(kw, _intent_text) for kw in fraud_kws):
                            logger.info("[%s] Auth success → routing to fraud agent (intent detected)", name)
                            result = AIMessage(
                                content=f"Thank you, {auth_customer}. Your identity has been verified successfully.",
                                tool_calls=[{
                                    "name": "to_fraud_detection_agent",
                                    "args": {"customer_name": auth_customer, "message": original_user_msg or "fraud followup"},
                                    "id": f"auto_fraud_{id(state)}",
                                }],
                            )
                        elif any(_kw_match(kw, _intent_text) for kw in credit_card_kws):
                            logger.info("[%s] Auth success → routing to credit card agent (intent detected)", name)
                            result = AIMessage(
                                content=f"Thank you, {auth_customer}. Your identity has been verified successfully.",
                                tool_calls=[{
                                    "name": "to_credit_card_agent",
                                    "args": {"customer_name": auth_customer, "message": original_user_msg or "credit card details"},
                                    "id": f"auto_credit_card_{id(state)}",
                                }],
                            )
                        elif any(_kw_match(kw, _intent_text) for kw in loan_kws):
                            logger.info("[%s] Auth success → routing to loan agent (intent detected)", name)
                            result = AIMessage(
                                content=f"Thank you, {auth_customer}. Your identity has been verified successfully.",
                                tool_calls=[{
                                    "name": "to_loan_agent",
                                    "args": {"customer_name": auth_customer, "message": original_user_msg or "loan details"},
                                    "id": f"auto_loan_{id(state)}",
                                }],
                            )
                        elif any(_kw_match(kw, _intent_text) for kw in grievance_kws):
                            logger.info("[%s] Auth success → routing to grievance agent (intent detected)", name)
                            result = AIMessage(
                                content=f"Thank you, {auth_customer}. Your identity has been verified successfully.",
                                tool_calls=[{
                                    "name": "to_grievance_agent",
                                    "args": {"customer_name": auth_customer, "message": original_user_msg or "complaint"},
                                    "id": f"auto_grievance_{id(state)}",
                                }],
                            )
                        else:
                            logger.info("[%s] Auth success → routing to balance agent (original_user_msg=%s)", name, original_user_msg)
                            result = AIMessage(
                                content=f"Thank you, {auth_customer}. Your identity has been verified successfully.",
                                tool_calls=[{
                                    "name": "to_balance_transactions_agent",
                                    "args": {"customer_name": auth_customer, "message": original_user_msg or auth_customer},
                                    "id": f"auto_balance_{id(state)}",
                                }],
                            )

                # EMPTY RESPONSE FALLBACK — must cover ALL agents to prevent
                if not content.strip() and not result_tool_calls:
                    logger.warning("[%s] Empty response fallback", name)

                    if name == "authentication_agent":
                        result = AIMessage(
                            content="Could you please provide your full name to proceed?"
                        )

                    elif name == "fraud_detection_agent":
                        result = AIMessage(
                            content="I understand your concern. Let me check this for you."
                        )

                    elif name == "balance_transactions_agent":
                        result = AIMessage(
                            content="I'm sorry, I couldn't retrieve that. Could you please repeat your request?"
                        )

                    elif name == "greeting_agent":
                        result = AIMessage(
                            content="I'm sorry, I didn't quite catch that. Could you please let me know how I can help you today?"
                        )

                    elif name == "loan_agent":
                        result = AIMessage(
                            content="I'm sorry, I couldn't retrieve your loan details. Could you please repeat your request?"
                        )

                    elif name == "credit_card_agent":
                        result = AIMessage(
                            content="I'm sorry, I couldn't retrieve your credit card details. Could you please repeat your request?"
                        )

                    elif name == "grievance_agent":
                        result = AIMessage(
                            content="I'm sorry, I didn't catch that. Could you describe your concern so I can register it for you?"
                        )

                return {"messages": [result]}

            return _node

        def create_entry_node(name: str, agents_list: list):
            def _entry(state: dict):
                msgs = state.get("messages", [])
                last = msgs[-1] if msgs else None
                tool_calls = getattr(last, "tool_calls", []) or []

                # Greeting agent: inject session context when we have a new user message (HumanMessage) and no tool_calls
                if name == "greeting_agent" and not tool_calls and isinstance(last, HumanMessage):
                    sess = state.get("session_context") or {}
                    # DEFENSE-IN-DEPTH: if graph state session_context is empty/stale,
                    # load fresh data from session store to prevent state-loss regressions
                    if not sess.get("customer_name") and not sess.get("greeting_done"):
                        from Banking_agent.app.db.session_store import get_session as _get_fresh_session
                        _sid = state.get("session_id", "")
                        if _sid:
                            _fresh = _get_fresh_session(_sid)
                            if _fresh:
                                sess = {**sess, **_fresh}
                                logger.info("Entry node: recovered session from store for %s: %s", _sid, {k: v for k, v in _fresh.items() if k != "messages"})
                    user_text = (getattr(last, "content", "") or "").strip().lower()
                    cust_name = sess.get("customer_name", "")
                    phone = (state.get("phone_number") or sess.get("phone_number") or "").strip()
                    is_authenticated = sess.get("authenticated", False)
                    balance_kws = [
                        "balance", "transaction", "account", "how much",
                        "cibil", "credit score", "cibil score",
                        "email", "e-mail", "contact", "phone number", "city",
                        "age", "gender", "account number", "branch",
                        "account type", "account opening", "statement",
                        "update my", "change my", "update email", "change email",
                        "update phone", "change phone", "update address",
                        "change address", "update contact", "change contact",
                        "update name", "change name", "update city", "change city",
                    ]
                    # Use MongoDB session store as authoritative source for dialog_state
                    # (InMemorySaver checkpoint is unreliable across invocations)
                    current_dialog = sess.get("last_active_agent", "") or state.get("dialog_state", "")
                    # Fallback: recover from session flags if both are empty
                    if not current_dialog and sess.get("greeting_done") and not is_authenticated:
                        if sess.get("identity_verified"):
                            current_dialog = "authentication_agent"
                            logger.info("Entry node: recovered dialog_state=authentication_agent from session flags")

                    logger.info("Entry node session: authenticated=%s, customer_name=%s, phone=%s, greeting_done=%s, dialog_state=%s",
                                is_authenticated, cust_name, phone, sess.get("greeting_done"), current_dialog)

                    # PRIORITY 0: If user is mid-authentication, route follow-up back to auth agent.
                    if current_dialog == "authentication_agent" and not is_authenticated:
                        _user_digits = "".join(c for c in user_text if c.isdigit())
                        _auth_phone = phone  # default: calling phone
                        _auth_name = cust_name  # default: known customer name
                        _no_words = ("no", "nope", "not", "different", "wrong", "another")

                        from Banking_agent.app.db.session_store import set_session as _set_sess
                        _sid = state.get("session_id", "")

                        if _user_digits and len(_user_digits) >= 10:
                            _auth_phone = _user_digits[-10:]
                            # User provided a phone — look up customer name from DB immediately
                            try:
                                from Banking_agent.app.Services.validation_services import fetch_customer_name
                                _lookup = fetch_customer_name(_auth_phone)
                                if _lookup.get("found") and _lookup.get("customer_name"):
                                    _auth_name = _lookup["customer_name"]
                                    logger.info("Direct route: looked up customer %s from user-provided phone %s", _auth_name, _auth_phone)
                            except Exception as _e:
                                logger.warning("Direct route: customer lookup failed for %s: %s", _auth_phone, _e)
                            _set_sess(_sid, {"user_provided_phone": _auth_phone, "customer_name": _auth_name or "", "greeting_done": True})
                        elif any(w in user_text for w in _no_words):
                            _auth_phone = ""
                            logger.info("Direct route: user rejected calling phone, will ask for registered number")
                        elif _looks_like_name(user_text) and not _auth_name:
                            # User provided their name — save it
                            _auth_name = user_text.strip().title()
                            _set_sess(_sid, {"customer_name": _auth_name, "greeting_done": True})
                            logger.info("Direct route: user provided name %s", _auth_name)
                        else:
                            _saved_phone = sess.get("user_provided_phone", "")
                            if _saved_phone:
                                _auth_phone = _saved_phone

                        logger.info("Direct route: user is mid-authentication (name=%s, phone=%s)", _auth_name, _auth_phone)
                        tool_call_id = f"direct_auth_followup_{id(state)}"
                        return {
                            "messages": [
                                AIMessage(
                                    content="",
                                    tool_calls=[{
                                        "name": "to_authentication_agent",
                                        "args": {"customer_name": _auth_name, "phone_number": "", "context_phone": _auth_phone, "message": user_text},
                                        "id": tool_call_id,
                                    }],
                                ),
                            ],
                            "dialog_state": name,
                        }
                    
                    _sticky_agents = {
                        "fraud_detection_agent": "to_fraud_detection_agent",
                        "loan_agent": "to_loan_agent",
                        "grievance_agent": "to_grievance_agent",
                        "credit_card_agent": "to_credit_card_agent",
                    }
                    if current_dialog in _sticky_agents:
                        def _sticky_kw_match(kw, text):
                            """Word-boundary keyword match to avoid substring false positives."""
                            if " " in kw:
                                return kw in text
                            return bool(re.search(r'\b' + re.escape(kw) + r'\b', text))

                        # Fraud MUST be checked before balance so that "block my account",
                        # "freeze my account", etc. route to fraud_detection_agent and not
                        # balance_transactions_agent (which would escalate to human).
                        _domain_kws = [
                            ({"fraud", "suspicious", "unauthorized", "unauthorised", "stolen",
                              "block my card", "block my account", "block card", "block account",
                              "block", "freeze", "unblock", "unfreeze", "reactivate",
                              "scam", "hack", "phishing", "compromised",
                              "report fraud", "unknown transaction", "unknown debit",
                              "shared my otp", "shared my password", "clicked a link",
                              "fraud status", "fraud case", "reverse transaction", "refund",
                              "changed my email without", "changed my phone without",
                              "without my permission", "without my knowledge",
                              "someone changed", "tampered",
                              "someone has my account", "account access", "access to my account",
                              "hacked my account", "hacked my", "someone using my",
                              "unauthorized access", "unauthorised access",
                              "someone has access", "has access to my",
                              "is my account safe", "account safe", "am i safe",
                              "is it safe", "is my card safe", "blocking my card",
                              "never made", "didn't do", "didnt do",
                              "monitoring", "watch my account", "keep a watch",
                              "panicked", "entered my details", "entered all my details",
                              "message with a link", "got a link"},
                             "fraud_detection_agent", "to_fraud_detection_agent"),
                            ({"balance", "transaction", "account", "how much",
                              "cibil", "credit score", "cibil score",
                              "email", "e-mail", "contact", "city", "age", "gender",
                              "account number", "branch", "account type", "statement",
                              "update my", "change my", "new phone", "new email",
                              "new address", "update phone", "update email",
                              "update address", "update contact", "update name",
                              "change phone", "change email", "change address"},
                             "balance_transactions_agent", "to_balance_transactions_agent"),
                            ({"loan", "emi", "mortgage", "loan status", "loan balance",
                              "loan amount", "repayment", "loan term", "auto loan",
                              "personal loan", "home loan"},
                             "loan_agent", "to_loan_agent"),
                            ({"credit card", "credit limit", "credit due", "credit type",
                              "credit amount", "credit balance", "credit detail",
                              "card limit", "card balance", "card payment", "card due",
                              "card detail", "card type", "card status",
                              "minimum payment", "payment due", "my card",
                              "card transactions", "card closure", "close my card",
                              "cancel my card", "increase my limit", "increase credit",
                              "higher limit", "card dispute", "dispute a charge",
                              "how much do i owe", "available credit",
                              "convert to emi", "reward", "cashback",
                              "missed payment", "late payment",
                              "eligible for credit", "apply for credit", "apply for card",
                              "want a credit card", "get a credit card", "qualify for card",
                              "recommend me a card", "recommend a card", "best card",
                              "which card should", "which card is best", "what cards do you",
                              "card is best", "best for me",
                              "available to spend", "minimum amount", "need to pay",
                              "last payment", "close it", "don't use this card",
                              "convert it to emi"},
                             "credit_card_agent", "to_credit_card_agent"),
                            ({"complaint", "complain", "compliant", "grievance", "wrong charge",
                              "incorrect debit", "fee dispute", "service issue",
                              "register complaint", "lodge complaint", "raise a",
                              "issue with", "problem with", "not happy", "not satisfied",
                              "wrong transfer", "wrong upi", "wrong account number",
                              "sent money to wrong", "transferred by mistake",
                              "sent to wrong", "money by mistake", "accidental transfer",
                              "mistaken transfer", "sent money by mistake",
                              "annual fee", "seeing charges", "charges for it",
                              "app crashing", "app not working", "can't login", "cant login",
                              "app has been crashing", "mobile app",
                              "entered the wrong", "wrong number by mistake",
                              "frustrated", "frustrating", "trying to reach",
                              "disappointed", "terrible service", "terrible"},
                             "grievance_agent", "to_grievance_agent"),
                        ]
                        for kw_set, target_agent, target_tool_name in _domain_kws:
                            if target_agent != current_dialog and any(_sticky_kw_match(kw, user_text) for kw in kw_set):
                                logger.info("Breaking out of %s → routing to %s (intent switch detected)", current_dialog, target_agent)
                                tool_call_id = f"direct_break_{id(state)}"
                                return {
                                    "messages": [
                                        AIMessage(
                                            content="",
                                            tool_calls=[{
                                                "name": target_tool_name,
                                                "args": {"customer_name": cust_name, "message": user_text},
                                                "id": tool_call_id,
                                            }],
                                        ),
                                    ],
                                    "dialog_state": name,
                                }

                        # No intent switch detected — stay in current agent
                        target_tool = _sticky_agents[current_dialog]
                        logger.info("Direct route: user is mid-%s flow → %s", current_dialog, current_dialog)
                        tool_call_id = f"direct_sticky_{id(state)}"
                        return {
                            "messages": [
                                AIMessage(
                                    content="",
                                    tool_calls=[{
                                        "name": target_tool,
                                        "args": {"customer_name": cust_name, "message": user_text},
                                        "id": tool_call_id,
                                    }],
                                ),
                            ],
                            "dialog_state": name,
                        }

                    # PRIORITY 1: Already authenticated → route to appropriate agent
                    # Fraud is checked FIRST so "block my card" routes to fraud, not credit card.
                    if is_authenticated and cust_name:
                        fraud_kws = [
                            "fraud", "suspicious", "unauthorized", "unauthorised",
                            "stolen", "lost card", "lost my card",
                            "unknown transaction", "unknown debit", "unknown charge",
                            "i didn't", "i didnt", "i did not", "i haven't", "i havent",
                            "not my transaction", "not me", "not mine",
                            "didn't make", "didnt make", "did not make",
                            "didn't authorize", "didnt authorize", "did not authorize",
                            "freeze", "block", "block my card", "block my account",
                            "unblock", "unfreeze", "reactivate",
                            "report fraud", "scam", "hack", "phishing",
                            "compromised", "strange debit", "weird transaction",
                            "scared", "worried about my account",
                            "shared my otp", "shared my password", "clicked a link",
                            "fraud status", "fraud case",
                            "reverse transaction", "refund",
                            "changed my email without", "changed my phone without",
                            "without my permission", "without my knowledge",
                            "someone changed", "tampered",
                            "someone has my account", "account access", "access to my account",
                            "hacked my account", "hacked my", "someone using my",
                            "unauthorized access", "unauthorised access",
                            "someone has access", "has access to my",
                            "is my account safe", "account safe", "am i safe",
                            "is it safe", "is my card safe", "blocking my card",
                            "never made", "didn't do", "didnt do",
                            "monitoring", "watch my account", "keep a watch",
                            "panicked", "entered my details", "entered all my details",
                            "message with a link", "got a link",
                        ]
                        credit_kws = [
                            "credit card", "credit limit", "credit due", "credit type",
                            "credit amount", "credit balance", "credit detail",
                            "card limit", "card balance", "card payment", "card due",
                            "card detail", "card type", "card status",
                            "minimum payment", "payment due", "my card",
                            "card transactions", "card closure", "close my card",
                            "cancel my card", "increase my limit", "increase credit",
                            "higher limit", "card dispute", "dispute a charge",
                            "how much do i owe", "available credit",
                            "convert to emi", "reward", "cashback",
                            "missed payment", "late payment",
                        ]
                        loan_kws = [
                            "loan", "emi", "mortgage", "interest rate", "loan status",
                            "loan balance", "loan amount", "repayment", "loan term",
                            "auto loan", "personal loan", "home loan"
                        ]
                        grievance_kws = [
                            "complaint", "complain", "compliant", "grievance", "wrong charge",
                            "incorrect debit", "fee dispute", "service issue",
                            "register complaint", "lodge complaint", "wrong fee",
                            "charged wrongly", "raise a",
                            "issue with", "problem with", "not happy", "not satisfied",
                            "wrong transfer", "wrong upi", "wrong account number",
                            "sent money to wrong", "transferred by mistake",
                            "sent to wrong", "money by mistake", "accidental transfer",
                            "mistaken transfer", "sent money by mistake",
                            "annual fee", "seeing charges", "charges for it",
                            "app crashing", "app not working", "can't login", "cant login",
                            "app has been crashing", "mobile app",
                            "entered the wrong", "wrong number by mistake",
                            "frustrated", "frustrating", "trying to reach",
                            "disappointed", "terrible service", "terrible",
                        ]
                        if any(kw in user_text for kw in fraud_kws):
                            logger.info("Direct route: AUTHENTICATED user → fraud detection agent")
                            tool_call_id = f"direct_fraud_{id(state)}"
                            return {
                                "messages": [AIMessage(content="", tool_calls=[{"name": "to_fraud_detection_agent", "args": {"customer_name": cust_name, "message": user_text}, "id": tool_call_id}])],
                                "dialog_state": name,
                            }
                        if any(kw in user_text for kw in credit_kws):
                            logger.info("Direct route: AUTHENTICATED user → credit card agent")
                            tool_call_id = f"direct_credit_{id(state)}"
                            return {
                                "messages": [AIMessage(content="", tool_calls=[{"name": "to_credit_card_agent", "args": {"customer_name": cust_name, "message": user_text}, "id": tool_call_id}])],
                                "dialog_state": name,
                            }
                        if any(kw in user_text for kw in loan_kws):
                            logger.info("Direct route: AUTHENTICATED user → loan agent")
                            tool_call_id = f"direct_loan_{id(state)}"
                            return {
                                "messages": [AIMessage(content="", tool_calls=[{"name": "to_loan_agent", "args": {"customer_name": cust_name, "message": user_text}, "id": tool_call_id}])],
                                "dialog_state": name,
                            }
                        if any(kw in user_text for kw in grievance_kws):
                            logger.info("Direct route: AUTHENTICATED user → grievance agent")
                            tool_call_id = f"direct_grievance_{id(state)}"
                            return {
                                "messages": [AIMessage(content="", tool_calls=[{"name": "to_grievance_agent", "args": {"customer_name": cust_name, "message": user_text}, "id": tool_call_id}])],
                                "dialog_state": name,
                            }
                        # Default: route all other messages to balance agent (handles follow-ups like "4", "yes", etc.)
                        logger.info("Direct route: ALREADY AUTHENTICATED customer_name=%s → balance agent", cust_name)
                        tool_call_id = f"direct_balance_{id(state)}"
                        return {
                            "messages": [
                                AIMessage(
                                    content="",
                                    tool_calls=[{
                                        "name": "to_balance_transactions_agent",
                                        "args": {"customer_name": cust_name, "message": user_text or cust_name},
                                        "id": tool_call_id,
                                    }],
                                ),
                            ],
                            "dialog_state": name,
                        }

                    # PRIORITY 2: Greeting done + known customer but NOT authenticated then route to auth
                    if sess.get("greeting_done") and cust_name:
                        _auth_trigger_kws = balance_kws + [
                            "fraud", "suspicious", "unauthorized", "unauthorised",
                            "stolen", "lost card", "lost my card",
                            "unknown transaction", "unknown debit", "unknown charge",
                            "i didn't", "i didnt", "i did not",
                            "not my transaction", "not me", "not mine",
                            "didn't make", "didnt make", "did not make",
                            "didn't authorize", "didnt authorize",
                            "freeze", "block", "block my card", "block my account",
                            "unblock", "unfreeze", "reactivate",
                            "report fraud", "scam", "hack", "phishing",
                            "compromised", "strange debit", "scared", "worried",
                            "shared my otp", "shared my password", "clicked a link",
                            "fraud status", "fraud case",
                            "reverse transaction", "refund",
                            "changed my email without", "changed my phone without",
                            "without my permission", "without my knowledge",
                            "someone changed", "tampered",
                            "someone has my account", "account access", "access to my account",
                            "hacked my account", "hacked my", "someone using my",
                            "unauthorized access", "unauthorised access",
                            "someone has access", "has access to my",
                            "is my account safe", "account safe", "am i safe",
                            "is it safe", "is my card safe", "blocking my card",
                            "never made", "didn't do", "didnt do",
                            "monitoring", "watch my account", "keep a watch",
                            "panicked", "entered my details", "entered all my details",
                            "message with a link", "got a link",
                            "loan", "emi", "mortgage", "interest rate", "loan status",
                            "complaint", "complain", "compliant", "grievance", "wrong charge",
                            "raise a", "issue with", "problem with",
                            "wrong transfer", "wrong upi", "wrong account number",
                            "sent money to wrong", "transferred by mistake",
                            "sent to wrong", "money by mistake",
                            "credit card", "credit limit", "card balance", "minimum payment",
                            "card transactions", "card closure", "close my card", "cancel my card",
                            "increase my limit", "dispute", "card dispute",
                            "eligible for credit", "apply for credit", "apply for card",
                            "want a credit card", "get a credit card", "qualify for card",
                            "recommend me a card", "recommend a card", "best card",
                        ]
                        if any(kw in user_text for kw in _auth_trigger_kws):
                            from Banking_agent.app.db.session_store import set_session as _save_q
                            _save_q(state.get("session_id", ""), {"original_question": user_text})
                            logger.info("Direct route: session has customer_name=%s (not yet authenticated), intent detected → route to auth agent (saved question: %s)", cust_name, user_text)
                            tool_call_id = f"direct_auth_{id(state)}"
                            return {
                                "messages": [
                                    AIMessage(
                                        content="",
                                        tool_calls=[{
                                            "name": "to_authentication_agent",
                                            "args": {"customer_name": cust_name, "phone_number": "", "context_phone": phone, "message": user_text},
                                            "id": tool_call_id,
                                        }],
                                    ),
                                ],
                                "dialog_state": name,
                            }

                        ctx = f"[Session context] Greeting ALREADY DONE. Customer name is {cust_name}. Do NOT greet again. If user says hi/hello, respond briefly: 'Hi {cust_name}! How can I help you today?'"
                        return {
                            "messages": [SystemMessage(content=ctx)],
                            "dialog_state": name,
                        }

                    # PRIORITY 3: User provides a name after auth/balance agent asked then route to auth
                    if _looks_like_name(user_text) and len(msgs) > 1:
                        prev_about_balance = any(
                            "balance" in (getattr(m, "content", "") or "").lower()
                            or "provide your name" in (getattr(m, "content", "") or "").lower()
                            or "verify" in (getattr(m, "content", "") or "").lower()
                            for m in msgs[-4:] if hasattr(m, "content")
                        )
                        if prev_about_balance:
                            logger.info("Direct route: user provided name=%s after auth request → route to auth agent", user_text)
                            tool_call_id = f"direct_auth_name_{id(state)}"
                            return {
                                "messages": [
                                    AIMessage(
                                        content="",
                                        tool_calls=[{
                                            "name": "to_authentication_agent",
                                            "args": {"customer_name": user_text.title(), "phone_number": "", "context_phone": phone, "message": user_text.title()},
                                            "id": tool_call_id,
                                        }],
                                    ),
                                ],
                                "dialog_state": name,
                            }

                    # PRIORITY 4: Balance intent without any prior context then route to auth
                    if any(kw in user_text for kw in balance_kws):
                        from Banking_agent.app.db.session_store import set_session as _save_q4
                        _save_q4(state.get("session_id", ""), {"original_question": user_text})
                        logger.info("Direct route: user wants balance (not authenticated) → route to auth agent (saved question: %s)", user_text)
                        tool_call_id = f"direct_auth_nogreet_{id(state)}"
                        return {
                            "messages": [
                                AIMessage(
                                    content="",
                                    tool_calls=[{
                                        "name": "to_authentication_agent",
                                        "args": {"customer_name": cust_name, "phone_number": "", "context_phone": phone, "message": user_text},
                                        "id": tool_call_id,
                                    }],
                                ),
                            ],
                            "dialog_state": name,
                        }

                    # PRIORITY 5: Phone number available then fetch customer name first
                    if phone and len(phone) >= 10:
                        ctx = f"[Session context] The user's phone number is {phone}. You MUST call fetch_customer_name_tool(phone_number=\"{phone}\") as your FIRST action. Do NOT greet before calling the tool. After the tool returns customer_name, greet personally: 'Hello, [Name]! Welcome to GiniBank. How may I help you today?' If the user asked for balance/transactions/account info, delegate to to_authentication_agent with the customer name and phone number."
                        return {
                            "messages": [SystemMessage(content=ctx)],
                            "dialog_state": name,
                        }

                    # PRIORITY 6: First message then warm greeting
                    if len(msgs) == 1:
                        ctx = "[Session context] No phone number provided. Give a warm, general greeting: 'Welcome to GiniBank! How may I help you today?' Do NOT ask for phone number. If the user provides one later, use it."
                        return {
                            "messages": [SystemMessage(content=ctx)],
                            "dialog_state": name,
                        }

                    ctx = "[Session context] No phone number. The user has been greeted. Route based on intent: for balance/account/transaction queries call to_authentication_agent, for credit card call to_credit_card_agent, for fraud call to_fraud_detection_agent, for loan queries call to_loan_agent, for complaints call to_grievance_agent. For general questions, respond directly."
                    return {
                        "messages": [SystemMessage(content=ctx)],
                        "dialog_state": name,
                    }

                for tc in tool_calls:
                    if tc.get("name", "").startswith("to_") and tc["name"][3:] == name:
                        args = tc.get("args", {}) or {}
                        tool_call_id = tc.get("id", f"entry_{name}")
                        msg_val = args.get("message") or args.get("user_message") or args.get("customer_name")
                        if not msg_val or not str(msg_val).strip():
                            for m in reversed(msgs):
                                if isinstance(m, HumanMessage):
                                    txt = (getattr(m, "content", "") or "").strip()
                                    if txt and _looks_like_name(txt):
                                        msg_val = txt
                                        args = {**args, "message": txt, "customer_name": txt}
                                        logger.info("Handoff fallback: using last HumanMessage as customer_name=%s", txt)
                                    break
                        if not msg_val:
                            msg_val = str(args) if args else ""
                        content = json.dumps({
                            "message": msg_val,
                            "data": args,
                        })
                        result_msgs = [
                            ToolMessage(content=content, tool_call_id=tool_call_id)
                        ]
                        if name == "authentication_agent":
                            context_phone = args.get("context_phone", "")
                            handoff_customer_name = args.get("customer_name", "")

                            # Check session for auth progress to give the right directive
                            from Banking_agent.app.db.session_store import get_session as _auth_get_session
                            _auth_sid = state.get("session_id", "")
                            _auth_sess = _auth_get_session(_auth_sid) if _auth_sid else {}
                            _identity_done = _auth_sess.get("identity_verified", False)

                            if _identity_done and handoff_customer_name:
                                # Identity already verified, OTP already sent — just collect OTP
                                directive = (
                                    f"[VERIFICATION DIRECTIVE] The customer is {handoff_customer_name}. "
                                    "Identity verification is ALREADY COMPLETE. An OTP has ALREADY been sent. "
                                    "The customer's latest message is their OTP code. "
                                    f"Call verify_otp_tool immediately with customer_name=\"{handoff_customer_name}\" "
                                    "and otp_input set to the digits from their message. "
                                    "Do NOT ask for name, phone, or re-send OTP. Just verify."
                                )
                            elif handoff_customer_name and context_phone:
                                # Check if user's message is already a phone confirmation
                                _user_msg = (args.get("message", "") or "").strip().lower()
                                _is_confirm = _user_msg in ("yes", "yeah", "yep", "correct", "right", "confirmed", "that's right", "yes it is")
                                if _is_confirm:
                                    # User already confirmed phone — verify immediately
                                    directive = (
                                        f"[VERIFICATION DIRECTIVE] The customer is {handoff_customer_name}. "
                                        f"They have CONFIRMED their phone number {context_phone}. "
                                        "Do NOT ask for name or phone — both are confirmed. "
                                        "Call verify_customer_identity_tool IMMEDIATELY with "
                                        f"customer_name=\"{handoff_customer_name}\" and "
                                        f"phone_number=\"{context_phone}\"."
                                    )
                                else:
                                    # First time — ask to confirm phone
                                    directive = (
                                        f"[VERIFICATION DIRECTIVE] The customer's name is {handoff_customer_name} "
                                        f"and they are calling from phone number {context_phone}. "
                                        "Do NOT ask for their name — it is already known. "
                                        "Ask: \"I can see the number you're reaching us from is "
                                        f"{' '.join(context_phone)}. "
                                        "Is this the phone number registered with your GiniBank account?\" "
                                        "If they confirm, call verify_customer_identity_tool "
                                        f"immediately with customer_name=\"{handoff_customer_name}\" and "
                                        f"phone_number=\"{context_phone}\". "
                                        "If they say no, ask for the correct number."
                                    )
                            elif context_phone:
                                directive = (
                                    f"[VERIFICATION DIRECTIVE] The customer is calling from phone number {context_phone}. "
                                    "Ask for their full name first. Then ask them to CONFIRM whether this phone number "
                                    "is the one registered with their account. If they confirm, use it for verification. "
                                    "If they say no, ask them to provide the correct phone number. "
                                    "NEVER call verify_customer_identity_tool until you have both the full name AND "
                                    "a confirmed/provided phone number."
                                )
                            else:
                                directive = (
                                    "[VERIFICATION DIRECTIVE] You MUST ask the customer for BOTH their full name "
                                    "AND the phone number registered with their account. "
                                    "NEVER call verify_customer_identity_tool until the customer has explicitly "
                                    "provided both values."
                                )
                            result_msgs.append(SystemMessage(content=directive))
                        elif name in ("balance_transactions_agent", "fraud_detection_agent",
                                      "loan_agent", "credit_card_agent", "grievance_agent"):
                            # Inject clear context for service agents after auth handoff
                            handoff_customer = args.get("customer_name", "")
                            handoff_msg = args.get("message", "")
                            if handoff_customer:
                                result_msgs.append(SystemMessage(
                                    content=(
                                        f"[HANDOFF CONTEXT] Customer {handoff_customer} has been fully authenticated. "
                                        f"Their request: \"{handoff_msg}\". "
                                        "Process this request immediately by calling the appropriate tool. "
                                        "Do NOT ask for their name or re-verify."
                                    )
                                ))
                        return {
                            "messages": result_msgs,
                            "dialog_state": name,
                        }
                return {"dialog_state": name}

            return _entry

        builder.add_node(f"enter_{agent_name}", create_entry_node(agent_name, agent_cfg.get("agents", [])))
        builder.add_node(agent_name, create_assistant_node(agent_name))
        builder.add_node(f"{agent_name}_tools", tool_node)

        def route_assistant(state: dict, an=agent_name):
            msgs = state.get("messages", [])
            last = msgs[-1] if msgs else None
            tool_calls = getattr(last, "tool_calls", []) or []
            if tool_calls:
                for c in tool_calls:
                    n = c.get("name", "")
                    if n.startswith("to_"):
                        target = n[3:]
                        if target in agent_set:
                            return f"enter_{target}"
                return f"{an}_tools"
            return END

        def route_after_tools(state: dict, an=agent_name):
            msgs = state.get("messages", [])
            last_ai = next((m for m in reversed(msgs) if getattr(m, "tool_calls", None)), None)
            if not last_ai:
                return an
            for c in (last_ai.tool_calls or []):
                n = c.get("name", "")
                if n.startswith("to_"):
                    target = n[3:]
                    if target in agent_set:
                        return f"enter_{target}"
            return an

        builder.add_edge(f"enter_{agent_name}", agent_name)

        builder.add_conditional_edges(
            agent_name,
            route_assistant,
            [f"enter_{n}" for n in agent_names]  
            + [f"{agent_name}_tools", END],
        )

        builder.add_conditional_edges(
            f"{agent_name}_tools",
            route_after_tools,
            [f"enter_{n}" for n in agent_names if n in agent_cfg.get("agents", [])] + [agent_name],
        )

    builder.add_edge(START, "enter_greeting_agent")

    return builder.compile(checkpointer=get_checkpointer())

_compiled_graph = None

def get_compiled_graph():
    global _compiled_graph
    if _compiled_graph is None:
        preload_prompts()         
        _compiled_graph = _build_ava_style_graph()
    return _compiled_graph

async def run_multi_agent_workflow_stream_ava(
    user_input: str, session_id: str, phone_number: str | None = None
):
    """
    Run the AVA-style workflow and stream results.
    Yields interim and final messages.
    phone_number: Optional. If provided (e.g. from ANI/metadata), used to auto-fetch customer name on session start.
    """
    from Banking_agent.app.Utils.interim_config import get_interim_message
    from Banking_agent.app.db.session_store import get_session, set_session, save_greeting_done, save_authenticated, parse_fetch_customer_result, save_identity_verified, save_otp_failure, save_auth_failure

    # Secondary call_ended check (primary guard is in gRPC server)
    _sess = get_session(session_id)
    if _sess.get("call_ended"):
        logger.info("BLOCKED|%s|call already ended, ignoring: %s", session_id, user_input[:80])
        return

    _goodbye_kws = {
        "bye", "goodbye", "good bye", "no thanks", "no thank you",
        "nothing else", "that's all", "thats all", "no more", "nothing more",
        "i'm done", "im done", "end call", "hang up", "take care",
        "thank you bye", "thanks bye", "nothing", "i'm good", "im good"
    }
    user_lower = user_input.lower().strip()
    if user_lower in _goodbye_kws or any(kw in user_lower for kw in _goodbye_kws):
        set_session(session_id, {"call_ended": True})
        yield {"type": "hangup", "message": "Thank you for banking with GiniBank. Have a wonderful day! Goodbye.", "agent": "greeting_agent", "tool_used": None}
        return

    _repeat_kws = {"repeat", "say again", "say that again", "can you repeat", "pardon", "come again"}
    if any(kw in user_lower for kw in _repeat_kws):
        _graph = get_compiled_graph()
        _cfg = {"configurable": {"thread_id": session_id}}
        try:
            state_snap = await _graph.aget_state(_cfg)
            if state_snap and state_snap.values:
                for m in reversed(state_snap.values.get("messages", [])):
                    if isinstance(m, AIMessage):
                        c = (getattr(m, "content", "") or "").strip()
                        if c and not c.startswith("{") and "Delegating" not in c and not c.lower().startswith("[session"):
                            yield {"type": "final", "message": c, "agent": "repeat", "tool_used": None}
                            return
        except Exception as _e:
            logger.warning("Repeat detection failed: %s", _e)

    last_tool_used = None
    last_agent_used = None

    graph = get_compiled_graph()
    config = {"configurable": {"thread_id": session_id}}

    # DEBUG: check checkpoint BEFORE we do anything
    try:
        _snap = await graph.aget_state(config)
        if _snap and _snap.values:
            _sv = _snap.values
            logger.info(
                "CHECKPOINT_PRE|%s|dialog_state=%s|session_context=%s|msg_count=%d",
                session_id,
                _sv.get("dialog_state", ""),
                {k: v for k, v in (_sv.get("session_context") or {}).items() if k != "messages"},
                len(_sv.get("messages", [])),
            )
        else:
            logger.info("CHECKPOINT_PRE|%s|EMPTY", session_id)
    except Exception as _e:
        logger.warning("CHECKPOINT_PRE|%s|ERROR: %s", session_id, _e)

    phone = (phone_number or "").strip() if phone_number else ""
    session_context = get_session(session_id)
    logger.info("SESSION_STORE|%s|%s", session_id, {k: v for k, v in session_context.items() if k != "messages"})
    if phone and not session_context.get("phone_number"):
        session_context = {**session_context, "phone_number": phone}
    initial_state = {
        "messages": [HumanMessage(content=user_input)],
        "dialog_state": "",
        "phone_number": phone,
        "session_id": session_id,
        "session_context": session_context,
    }

    tool_interim_names = {
        "fetch_account_balance_tool", "fetch_last_n_transactions_tool",
        "fetch_customer_field_tool", "fetch_account_field_tool",
        "fetch_transaction_field_tool", "fetch_customer_name_tool",
        "suspicious_transactions_tool",
        "freeze_account_tool",
        "block_card_tool",
        "flag_account_tool",
        "report_fraud_tool",
        "fetch_loan_details_tool",
        "fetch_loan_status_tool",
        "fetch_credit_card_details_tool",
        "fetch_credit_card_balance_tool",
        "register_complaint_tool",
        "escalate_to_human_tool",
    }

    _last_active_agent = None

    async for chunk in graph.astream(
        initial_state, config=config, stream_mode="updates"
    ):
        print("CHUNKKKKKKK",chunk)
        for node_name, node_output in chunk.items():
            # Track which agent node is active (not entry/tool nodes)
            if not node_name.startswith("enter_") and not node_name.endswith("_tools"):
                _last_active_agent = node_name
            msgs = node_output.get("messages", [])
            if not msgs:
                continue
            for m in msgs:
                if isinstance(m, ToolMessage):
                    customer_name = parse_fetch_customer_result(m.content)
                    if customer_name:
                        save_greeting_done(session_id, customer_name, phone)
                    try:
                        tool_data = json.loads(m.content) if isinstance(m.content, str) else m.content
                        if isinstance(tool_data, dict):
                            if tool_data.get("otp_verified") is True:
                                # Full authentication complete — OTP passed
                                auth_name = tool_data.get("customer_name", "")
                                auth_phone = get_session(session_id).get("phone_number", phone)
                                save_authenticated(session_id, auth_name, auth_phone)
                                logger.info("Session %s: OTP verified, auth saved (name=%s)", session_id, auth_name)
                            elif tool_data.get("otp_verified") is False:
                                if tool_data.get("attempts_left", 1) == 0:
                                    yield {
                                        "type": "final",
                                        "message": "For your security, we are unable to verify your identity after multiple OTP attempts. Please visit your nearest GiniBank branch or contact our helpline for assistance. Goodbye.",
                                        "agent": "authentication_agent",
                                        "tool_used": None
                                    }
                                    return
                                failures = save_otp_failure(session_id)
                                logger.info("Session %s: OTP failure count=%d", session_id, failures)
                            elif tool_data.get("identity_verified") is True:
                                # Identity (name+phone) verified — auto-send OTP email
                                id_name  = tool_data.get("customer_name", "")
                                id_phone = tool_data.get("phone_number", phone)
                                save_identity_verified(session_id, id_name, id_phone)
                                # Force send OTP email immediately (don't rely on LLM to call the tool)
                                try:
                                    from Banking_agent.app.Services.otp_service import generate_and_send_otp_email
                                    _otp_result = generate_and_send_otp_email(id_name, id_phone)
                                    logger.info("Auto OTP email sent for %s: %s", id_name, _otp_result.get("status", "unknown"))
                                except Exception as _otp_err:
                                    logger.error("Auto OTP email FAILED for %s: %s", id_name, _otp_err)
                            elif tool_data.get("identity_verified") is False:
                                failures = save_auth_failure(session_id)
                                if failures >= 3:
                                    yield {
                                        "type": "final",
                                        "message": "For your security, we are unable to verify your identity after multiple attempts. Please visit your nearest GiniBank branch or contact our helpline for assistance. Goodbye.",
                                        "agent": "authentication_agent",
                                        "tool_used": None
                                    }
                                    return
                            elif tool_data.get("escalated") is True:
                                yield {
                                    "type": "escalate",
                                    "message": "Connecting you to a banking specialist. Please hold.",
                                    "agent": node_name,
                                    "tool_used": "escalate_to_human_tool"
                                }
                                return
                    except (json.JSONDecodeError, TypeError):
                        pass
            last = msgs[-1]
            if isinstance(last, (ToolMessage, SystemMessage)):
                continue

            if getattr(last, "tool_calls", None):
                for tc in last.tool_calls:
                    tc_name = tc.get("name", "")

                    last_tool_used = tc_name
                    last_agent_used = node_name

                    if tc_name in tool_interim_names:
                        interim_msg = get_interim_message(tc_name)
                        yield {"type": "interim", "message": interim_msg}
                continue
            content = getattr(last, "content", None)
            if isinstance(content, list):
                content = "".join(
                    part.get("text", "")
                    for part in content
                    if isinstance(part, dict)
                )
            print("__________________")
            print(type(last.content))
            print(last.content)
            print("__________________")
            # if not content or not isinstance(content, str):
            #     continue
            if not content:
                continue
            # content = content.strip()
            content = str(content).strip()
            if (
                content.startswith("{")
                or "Delegating" in content
                or content.lower().startswith("[session context")
            ):
                continue
            if content:
                yield {
                    "type": "final",
                    "message": content,
                    "agent": last_agent_used,
                    "tool_used": last_tool_used
                }

    # Persist the active agent to MongoDB session store so the entry node
    # always knows the correct dialog_state, even if InMemorySaver loses data
    if _last_active_agent:
        set_session(session_id, {"last_active_agent": _last_active_agent})


def run_multi_agent_workflow_ava(
    user_input: str, session_id: str, phone_number: str | None = None
):
    """Sync run - invoke and return final output."""
    import asyncio
    graph = get_compiled_graph()
    config = {"configurable": {"thread_id": session_id}}
    phone = (phone_number or "").strip() if phone_number else ""
    initial_state = {
        "messages": [HumanMessage(content=user_input)],
        "dialog_state": "",
        "phone_number": phone,
    }
    final_state = asyncio.run(graph.ainvoke(initial_state, config=config))
    msgs = final_state.get("messages", [])
    if msgs:
        last = msgs[-1]
        return {"final_output": getattr(last, "content", str(last)), "intent": None}
    return {"final_output": "", "intent": None}
