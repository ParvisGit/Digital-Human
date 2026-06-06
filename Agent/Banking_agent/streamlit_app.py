import os
import re
import sys
import asyncio

_script_dir = os.path.dirname(os.path.abspath(__file__))
_bfsi_dir = os.path.dirname(_script_dir)
if _bfsi_dir not in sys.path:
    sys.path.insert(0, _bfsi_dir)

from Banking_agent.app.Utils.logging_config import setup_app_logging
setup_app_logging()

import streamlit as st
import grpc
from Banking_agent.generated import aivoice_pb2
from Banking_agent.generated import aivoice_pb2_grpc

_DIGIT_WORDS_INV = {"zero": "0", "one": "1", "two": "2", "three": "3", "four": "4",
                    "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9"}
_DIGIT_TOKEN_RE = re.compile(
    r"\b(?:[0-9]|zero|one|two|three|four|five|six|seven|eight|nine)"
    r"(?:\s+(?:[0-9]|zero|one|two|three|four|five|six|seven|eight|nine)){2,}\b",
    re.IGNORECASE,
)


def _to_digits(text: str) -> str:
    """For UI display: collapse 3+ consecutive digit tokens (words or numerals)
    back into a clean numeric string. e.g. 'seven zero two six' → '7026'."""
    if not text:
        return text

    def _collapse(m):
        return "".join(
            t if t.isdigit() else _DIGIT_WORDS_INV[t.lower()]
            for t in m.group(0).split()
        )
    return _DIGIT_TOKEN_RE.sub(_collapse, text)


GRPC_SERVER = os.environ.get("GRPC_SERVER", "localhost:8008")
DEFAULT_BOT_ID = os.environ.get("BOT_ID", "banking_agent")
DEFAULT_BOT_NAME = os.environ.get("BOT_NAME", "Digital Human Banking")
# Must match PRIMARY_BOT_ID in bfsi-rabbitmq-consumer/.env — this bot writes
# to the plain `chat_logs` collection, any other bot_id gets its own suffixed
# collection on first insert.
MONGO_COLLECTION_PREFIX = os.environ.get("MONGO_COLLECTION_PREFIX", "chat_logs")
PRIMARY_BOT_ID = os.environ.get("PRIMARY_BOT_ID", "banking_agent")


def _resolve_bot_id() -> str:
    """Resolve bot_id from ?bot_id=... query param, falling back to env default."""
    try:
        qp_bot = st.query_params.get("bot_id")
        if qp_bot:
            return qp_bot.strip()
    except Exception:
        pass
    return DEFAULT_BOT_ID


def _sanitize_bot_id(raw: str) -> str:
    """Mirror of consumer-side sanitization so the UI preview matches reality."""
    if not raw:
        return "default"
    cleaned = re.sub(r"[^a-zA-Z0-9_-]", "_", raw.strip())[:64]
    return cleaned or "default"


def _preview_target_collection(bot_id: str) -> str:
    """Predict which Mongo collection will hold messages for this bot_id."""
    safe = _sanitize_bot_id(bot_id)
    if safe == PRIMARY_BOT_ID:
        return MONGO_COLLECTION_PREFIX
    return f"{MONGO_COLLECTION_PREFIX}_{safe}"


def run_async(coro):
    """Run async coroutine from sync Streamlit context."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


async def stream_grpc_responses(prompt: str, on_chunk=None):
    """
    Call BFSI gRPC backend and invoke on_chunk(text) for each message as it arrives.
    Returns list of all chunks received.
    """
    phone_raw = st.session_state.get("sidebar_phone", "") or st.session_state.get("user_ani", "")
    phone_number = "".join(c for c in str(phone_raw) if c.isdigit())[:11]

    bot_id = (st.session_state.get("bot_id") or "").strip() or PRIMARY_BOT_ID

    async with grpc.aio.insecure_channel(GRPC_SERVER) as channel:
        stub = aivoice_pb2_grpc.ChatServiceStub(channel)
        request = aivoice_pb2.ChatRequest(
            unique_id=st.session_state.session_id,
            message=prompt,
            metadata=aivoice_pb2.Metadata(
                user_no=phone_number,
                email_id="",
                bot_id=bot_id,
                bot_name=DEFAULT_BOT_NAME,
            ),
            channel="WEB",
        )
        all_chunks = []
        async for response in stub.StreamMessages(request):
            for content in response.content:
                text = content.message.strip()
                if text:
                    all_chunks.append(text)
                    if on_chunk:
                        on_chunk(text)
        return all_chunks

st.set_page_config(
    page_title="GiniBank Assistant",
    page_icon="🏦",
    layout="centered",
)

st.markdown(
    """
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .stChatMessage [data-testid="chatAvatarIcon-assistant"] {
        background-color: #1a5276;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown("### 🏦 GiniBank Assistant")

if "messages" not in st.session_state:
    st.session_state.messages = []
if "session_id" not in st.session_state:
    import uuid
    st.session_state.session_id = f"streamlit_{uuid.uuid4().hex[:12]}"
if "bot_id" not in st.session_state:
    st.session_state.bot_id = _resolve_bot_id()

with st.sidebar:
    st.markdown("### GiniBank")
    st.caption(f"Session: `{st.session_state.session_id[:20]}...`")
    st.caption(f"Backend: `{GRPC_SERVER}`")
    st.divider()

    st.markdown("**Bot ID**")
    st.caption(
        f"Default `{PRIMARY_BOT_ID}` stores in the primary collection. "
        "Any other name creates its own collection automatically."
    )
    st.text_input(
        "Bot ID",
        key="bot_id",
        label_visibility="collapsed",
        placeholder=PRIMARY_BOT_ID,
    )
    _effective_bot_id = (st.session_state.get("bot_id") or "").strip() or PRIMARY_BOT_ID
    st.caption(f"→ Stores in: `{_preview_target_collection(_effective_bot_id)}`")
    st.divider()

    st.markdown("**Phone Number**")
    st.caption("Enter your phone number for a personalised experience.")
    st.text_input(
        "Phone",
        placeholder="e.g. 19458794854",
        key="sidebar_phone",
        label_visibility="collapsed",
    )
    st.divider()

    if st.button("New Conversation", use_container_width=True):
        import uuid
        st.session_state.session_id = f"streamlit_{uuid.uuid4().hex[:12]}"
        st.session_state.messages = []
        st.rerun()

    if st.session_state.messages:
        st.markdown("**Conversation History**")
        for msg in st.session_state.messages:
            role = "You" if msg["role"] == "user" else "Assistant"
            preview = msg["content"][:80] + ("..." if len(msg["content"]) > 80 else "")
            st.caption(f"**{role}:** {preview}")

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(_to_digits(msg["content"]) if msg["role"] == "assistant" else msg["content"])

user_input = st.chat_input("How can we help you today?")

if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    try:
        rendered_chunks = []

        def render_chunk(text: str):
            """Render each chunk immediately as a chat bubble when it arrives."""
            display_text = _to_digits(text)
            container = st.chat_message("assistant")
            with container:
                st.markdown(display_text)
            rendered_chunks.append(text)

        all_chunks = run_async(
            stream_grpc_responses(user_input, on_chunk=render_chunk)
        )

        if not all_chunks:
            with st.chat_message("assistant"):
                st.markdown("No response received.")
            st.session_state.messages.append(
                {"role": "assistant", "content": "No response received."}
            )
        else:
            for chunk in all_chunks:
                st.session_state.messages.append(
                    {"role": "assistant", "content": chunk}
                )

    except grpc.RpcError as e:
        error_msg = f"We're experiencing a connection issue. Please try again shortly. ({e.code().name})"
        with st.chat_message("assistant"):
            st.error(error_msg)
        st.session_state.messages.append(
            {"role": "assistant", "content": error_msg}
        )
    except Exception as e:
        error_msg = f"Something went wrong. Please try again. ({str(e)})"
        with st.chat_message("assistant"):
            st.error(error_msg)
        st.session_state.messages.append(
            {"role": "assistant", "content": error_msg}
        )
