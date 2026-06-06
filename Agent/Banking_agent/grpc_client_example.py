#!/usr/bin/env python3
"""
Example gRPC client for testing the Banking Agent ChatService.
Usage: python grpc_client_example.py [--port 50051] [message]
"""
import os
import sys

# Path setup
_script_dir = os.path.dirname(os.path.abspath(__file__))
_bfsi_dir = os.path.dirname(_script_dir)
sys.path.insert(0, _bfsi_dir)

import grpc
from Banking_agent.generated import aivoice_pb2
from Banking_agent.generated import aivoice_pb2_grpc


def run_client(host="localhost", port=50051, message="What is my balance?"):
    """Send a message to the gRPC server and print the response."""
    channel = grpc.insecure_channel(f"{host}:{port}")
    stub = aivoice_pb2_grpc.ChatServiceStub(channel)

        request = aivoice_pb2.ChatRequest(
            unique_id="test_session_001",
            message=message,
            metadata=aivoice_pb2.Metadata(
                user_no="",
                email_id="",
                bot_id="banking_agent",
                bot_name="Digital Human Banking",
            ),
            channel="WEB",
        )

    print(f"Sending: {message}")
    print("-" * 40)

    try:
        responses = stub.StreamMessages(request)
        for i, response in enumerate(responses):
            for content in response.content:
                print(f"Response {i+1}: {content.message}")
            if response.action.type != aivoice_pb2.Action.NoAction:
                print(f"Action: {response.action.type}, URI: {response.action.uri}")
    except grpc.RpcError as e:
        print(f"gRPC error: {e.code()}: {e.details()}")
    finally:
        channel.close()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=50051)
    parser.add_argument("message", nargs="?", default="Hello, what can you help me with?")
    args = parser.parse_args()
    run_client(args.host, args.port, args.message)
