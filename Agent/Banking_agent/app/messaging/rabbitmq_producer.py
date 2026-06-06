import json
import logging
from datetime import datetime

from Banking_agent.app.messaging.rabbitmq_connection import get_connection
from Banking_agent.app.messaging.queue_names import TRANSCRIPTION_QUEUE

logger = logging.getLogger("banking_agent.rabbitmq")


def _json_serial(obj):
    """JSON serializer for datetime objects → ISO format string."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")


def publish_chat_log(data: dict):

    try:
        connection = get_connection()

        channel = connection.channel()

        channel.queue_declare(
            queue=TRANSCRIPTION_QUEUE,
            durable=True
        )

        channel.basic_publish(
            exchange="",
            routing_key=TRANSCRIPTION_QUEUE,
            body=json.dumps(data, default=_json_serial),
            properties=None
        )

        connection.close()

    except Exception as e:
        logger.error("RabbitMQ publish failed: %s", e)