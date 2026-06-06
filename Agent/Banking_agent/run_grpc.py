"""
gRPC server for Digital Human Banking Agent.
Implements ChatService.StreamMessages using the multi-agent workflow.
"""
from datetime import datetime
import time
import os
import sys
import asyncio
import logging
import uuid

os.environ.setdefault(
    "GOOGLE_APPLICATION_CREDENTIALS",
    os.path.join(os.path.dirname(__file__), "../vertex-gemini-agent.json"),
)

_script_dir = os.path.dirname(os.path.abspath(__file__))
_bfsi_dir = os.path.dirname(_script_dir)
sys.path.insert(0, _bfsi_dir)
os.chdir(_bfsi_dir)

from Banking_agent.app.Utils.logging_config import setup_app_logging
LOG_FILE = setup_app_logging(level=os.environ.get("LOG_LEVEL", "INFO"))

import grpc

from Banking_agent.generated import aivoice_pb2_grpc
from Banking_agent.generated import aivoice_pb2

from Banking_agent.app.db.mongo import connect_db
from Banking_agent.app.db.redis_chat import get_checkpointer, is_using_redis
from Banking_agent.app.Agents.assistant_graph import run_multi_agent_workflow_stream_ava as run_multi_agent_workflow_stream

from Banking_agent.app.messaging.rabbitmq_producer import publish_chat_log

logger = logging.getLogger("banking_grpc")
logger.info("Full application logs: %s (LOG_LEVEL=DEBUG for verbose)", LOG_FILE)

DEFAULT_PORT = int(os.environ.get("GRPC_PORT", "8008"))

# Track sessions that have ended (hangup sent) — reject further messages
_ended_sessions: set = set()


class ChatServiceServicer(aivoice_pb2_grpc.ChatServiceServicer):
    """gRPC service implementation for Banking Agent chat."""

    async def StreamMessages(self, request, context):
        """Process chat message and stream response(s) back to client."""
        session_id = request.unique_id or f"grpc_{id(request)}"
        user_message = request.message or ""

        try:
            if not user_message.strip():
                yield self._create_response(request, "Please provide a message.")
                return

            if user_message.strip().lower() == "<healthcheck>":
                yield aivoice_pb2.ChatResponse()
                return

            # Block messages after hangup — call has ended
            if session_id in _ended_sessions:
                logger.info(f"BLOCKED|{session_id}|call ended, ignoring: {user_message[:80]}")
                yield self._create_response(
                    request,
                    "This call has already ended. Please start a new conversation if you need further assistance. Thank you!",
                )
                return

            # Extracting phone number from request metadata
            phone_number = ""
            if request.metadata and request.metadata.user_no:
                phone_number = request.metadata.user_no.strip()

            logger.info(f"RECEIVED|{session_id}|{user_message[:100]}")

            output = None
            print("IAM HERE MATE!!!!")
            request_start_time = time.time()
            tools_used = []
            async for chunk in run_multi_agent_workflow_stream(
                user_message, session_id, phone_number=phone_number
            ):
                logger.info(f"GRAPH_CHUNK|{chunk}")
                msg_type = chunk.get("type")
                msg_content = chunk.get("message", "")
                agent_name = chunk.get("agent")
                tool_used = chunk.get("tool_used")
                print("IAM HERE 22222222")
                if tool_used and tool_used not in tools_used and not tool_used.startswith("to_"):
                    tools_used.append(tool_used)

                if msg_type == "interim":
                    yield self._create_response(request, msg_content)
                elif msg_type == "final":
                    output = msg_content

                    latency_ms = int((time.time() - request_start_time) * 1000)
                    logger.info(f"RESPONSE|{session_id}|{msg_content[:100]}")

                    # Log user message
                    publish_chat_log({
                        "trace_id": str(uuid.uuid4()),
                        "session_id": session_id,
                        "phone_number": phone_number,
                        "message": user_message,
                        "sender_type": "User",
                        "agent": agent_name or "unknown_agent",
                        "tool": tools_used,
                        "latency": 0,
                        "status": "success",
                        "timestamp": datetime.utcnow(),
                    })
                    # Log bot response
                    publish_chat_log({
                        "trace_id": str(uuid.uuid4()),
                        "session_id": session_id,
                        "phone_number": phone_number,
                        "message": msg_content,
                        "sender_type": "Bot",
                        "agent": agent_name or "unknown_agent",
                        "tool": tools_used,
                        "latency": latency_ms / 1000,
                        "status": "success",
                        "timestamp": datetime.utcnow(),
                    })

                    yield self._create_response(request, msg_content)

                elif msg_type == "hangup":
                    output = msg_content
                    _ended_sessions.add(session_id)
                    latency_ms = int((time.time() - request_start_time) * 1000)
                    logger.info(f"HANGUP|{session_id}|{msg_content[:100]}")

                    publish_chat_log({
                        "trace_id": str(uuid.uuid4()),
                        "session_id": session_id,
                        "phone_number": phone_number,
                        "message": user_message,
                        "sender_type": "User",
                        "agent": "greeting_agent",
                        "tool": [],
                        "latency": 0,
                        "status": "hangup",
                        "timestamp": datetime.utcnow(),
                    })
                    publish_chat_log({
                        "trace_id": str(uuid.uuid4()),
                        "session_id": session_id,
                        "phone_number": phone_number,
                        "message": msg_content,
                        "sender_type": "Bot",
                        "agent": "greeting_agent",
                        "tool": [],
                        "latency": latency_ms / 1000,
                        "status": "hangup",
                        "timestamp": datetime.utcnow(),
                    })

                    yield self._create_hangup_response(request, msg_content)

                elif msg_type == "escalate":
                    output = msg_content
                    latency_ms = int((time.time() - request_start_time) * 1000)
                    logger.info(f"ESCALATE|{session_id}|agent={agent_name}|{msg_content[:100]}")

                    publish_chat_log({
                        "trace_id": str(uuid.uuid4()),
                        "session_id": session_id,
                        "phone_number": phone_number,
                        "message": user_message,
                        "sender_type": "User",
                        "agent": agent_name or "unknown_agent",
                        "tool": tools_used or ["escalate_to_human_tool"],
                        "latency": 0,
                        "status": "escalated",
                        "timestamp": datetime.utcnow(),
                    })
                    publish_chat_log({
                        "trace_id": str(uuid.uuid4()),
                        "session_id": session_id,
                        "phone_number": phone_number,
                        "message": msg_content,
                        "sender_type": "Bot",
                        "agent": agent_name or "unknown_agent",
                        "tool": tools_used or ["escalate_to_human_tool"],
                        "latency": latency_ms / 1000,
                        "status": "escalated",
                        "timestamp": datetime.utcnow(),
                    })

                    yield self._create_escalation_response(request, msg_content)

            if not output:
                yield self._create_response(
                    request,
                    "I couldn't process that request. Please try again.",
                )

        except Exception as e:
            logger.exception(f"Error processing message for {session_id}: {e}")
            yield self._create_response(
                request,
                f"Sorry, an error occurred: {str(e)}",
            )

    def _create_response(self, request, message: str):
        """Build a ChatResponse from the agent output."""
        content = aivoice_pb2.Content()
        content.type = aivoice_pb2.Content.ContentType.TEXT
        content.message = str(message) if message else ""

        action = aivoice_pb2.Action()
        action.type = aivoice_pb2.Action.ActionType.NoAction
        action.uri = ""

        metadata = aivoice_pb2.MetadataResponse()
        metadata.disposition = "COMPLETED"
        metadata.SPEECH_DTMF_MAXLEN = ""
        metadata.asr_timeout = "0"

        return aivoice_pb2.ChatResponse(
            channel_id=request.channel or "WEB",
            unique_id=request.unique_id,
            content=[content],
            action=action,
            metadata=metadata,
        )

    def _create_hangup_response(self, request, message: str):
        """Build a ChatResponse with HANGUP action for call termination."""
        content = aivoice_pb2.Content()
        content.type = aivoice_pb2.Content.ContentType.TEXT
        content.message = str(message) if message else "Thank you for banking with GiniBank. Goodbye."

        action = aivoice_pb2.Action()
        action.type = aivoice_pb2.Action.ActionType.HANGUP
        action.uri = ""

        metadata = aivoice_pb2.MetadataResponse()
        metadata.disposition = "COMPLETED"
        metadata.SPEECH_DTMF_MAXLEN = ""
        metadata.asr_timeout = "0"

        return aivoice_pb2.ChatResponse(
            channel_id=request.channel or "WEB",
            unique_id=request.unique_id,
            content=[content],
            action=action,
            metadata=metadata,
        )

    def _create_escalation_response(self, request, message: str):
        """Build a ChatResponse with TRUNK_TRANSFER action for human escalation."""
        content = aivoice_pb2.Content()
        content.type = aivoice_pb2.Content.ContentType.TEXT
        content.message = str(message) if message else "Connecting you to a banking specialist. Please hold."

        action = aivoice_pb2.Action()
        action.type = aivoice_pb2.Action.ActionType.TRUNK_TRANSFER
        action.uri = ""

        metadata = aivoice_pb2.MetadataResponse()
        metadata.disposition = "ESCALATED"
        metadata.SPEECH_DTMF_MAXLEN = ""
        metadata.asr_timeout = "0"

        return aivoice_pb2.ChatResponse(
            channel_id=request.channel or "WEB",
            unique_id=request.unique_id,
            content=[content],
            action=action,
            metadata=metadata,
        )


def _generate_execution_graph():
    """Generate execution graph from LangGraph compiled graph on startup.

    Tries (in order):
    1. draw_png() via pygraphviz  → execution_graph.png
    2. draw_mermaid_png() via Mermaid API → execution_graph.png
    3. Fallback: Mermaid .mmd + self-contained .html
    """
    try:
        from Banking_agent.app.Agents.assistant_graph import get_compiled_graph
        graph = get_compiled_graph()
        drawable = graph.get_graph(xray=True)

        docs_dir = os.path.join(_script_dir, "docs")
        os.makedirs(docs_dir, exist_ok=True)
        png_path = os.path.join(docs_dir, "execution_graph.png")
        png_saved = False

        try:
            png_data = drawable.draw_png()
            with open(png_path, "wb") as f:
                f.write(png_data)
            png_saved = True
            logger.info("Execution graph (pygraphviz PNG): %s", png_path)
        except Exception:
            pass

        if not png_saved:
            try:
                png_data = drawable.draw_mermaid_png(max_retries=2, retry_delay=1.0)
                with open(png_path, "wb") as f:
                    f.write(png_data)
                png_saved = True
                logger.info("Execution graph (Mermaid PNG): %s", png_path)
            except Exception:
                pass

        mermaid_text = drawable.draw_mermaid()
        with open(os.path.join(docs_dir, "execution_graph.mmd"), "w") as f:
            f.write(mermaid_text)

        html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Banking Agent - Execution Graph</title>
<script src="https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js"></script>
<style>body{{font-family:sans-serif;margin:2rem;background:#fafafa}}
h1{{color:#333;font-size:1.4rem}}
.mermaid{{background:#fff;padding:2rem;border-radius:8px;box-shadow:0 1px 4px rgba(0,0,0,.1)}}
p{{color:#666;font-size:.85rem}}</style>
</head><body>
<h1>Banking Agent &mdash; Execution Graph</h1>
<p>Auto-generated on service startup. Solid lines = fixed edges, dashed = conditional routing.</p>
<div class="mermaid">
{mermaid_text}
</div>
<script>mermaid.initialize({{startOnLoad:true,theme:'default'}});</script>
</body></html>"""
        html_path = os.path.join(docs_dir, "execution_graph.html")
        with open(html_path, "w") as f:
            f.write(html)

        if not png_saved:
            logger.info("Execution graph (HTML+Mermaid fallback): %s", html_path)
    except Exception as e:
        logger.warning("Could not generate execution graph: %s", e)


def serve(port: int = DEFAULT_PORT):
    """Start the gRPC server."""
    connect_db()

    get_checkpointer()
    logger.info(
        "Session persistence: %s",
        "Redis" if is_using_redis() else "InMemory (set REDIS_HOST to use Redis)",
    )
    _generate_execution_graph()
    logger.info(f"Starting gRPC server on port {port}...")

    async def run():
        server = grpc.aio.server()
        aivoice_pb2_grpc.add_ChatServiceServicer_to_server(
            ChatServiceServicer(), server
        )
        server.add_insecure_port(f"[::]:{port}")
        await server.start()
        logger.info(f"gRPC server listening on [::]:{port}")
        try:
            await server.wait_for_termination()
        except asyncio.CancelledError:
            pass
        finally:
            await server.stop(grace=5)

    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        logger.info("Shutting down gRPC server...")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="gRPC server port")
    args = parser.parse_args()
    serve(port=args.port)
