import os
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

GRPC_SERVER = os.environ.get("GRPC_SERVER", "localhost:8008")


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

    async with grpc.aio.insecure_channel(GRPC_SERVER) as channel:
        stub = aivoice_pb2_grpc.ChatServiceStub(channel)
        request = aivoice_pb2.ChatRequest(
            unique_id=st.session_state.session_id,
            message=prompt,
            metadata=aivoice_pb2.Metadata(
                user_no=phone_number,
                email_id="",
                bot_id="banking_agent",
                bot_name="Digital Human Banking",
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

with st.sidebar:
    st.markdown("### GiniBank")
    st.caption(f"Session: `{st.session_state.session_id[:20]}...`")
    st.caption(f"Backend: `{GRPC_SERVER}`")
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
        st.markdown(msg["content"])

user_input = st.chat_input("How can we help you today?")

if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    try:
        rendered_chunks = []

        def render_chunk(text: str):
            """Render each chunk immediately as a chat bubble when it arrives."""
            container = st.chat_message("assistant")
            with container:
                st.markdown(text)
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
