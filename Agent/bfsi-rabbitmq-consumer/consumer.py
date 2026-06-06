import json
import logging

import pika

from .mongo_writer import save_chat

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger("bfsi-rabbitmq-consumer")

logger.info("Connecting to RabbitMQ...")

connection = pika.BlockingConnection(
    pika.ConnectionParameters(host="localhost")
)

channel = connection.channel()

channel.queue_declare(
    queue="bfsi_chat_logs_queue",
    durable=True
)

logger.info("Connected to RabbitMQ")
logger.info("Queue declared: bfsi_chat_logs_queue")


def callback(ch, method, properties, body):
    try:
        logger.info("Message received")

        data = json.loads(body)
        logger.info(
    "Payload received: %s",
    json.dumps(data, default=str)
)
        logger.info(
            "Processing session_id=%s",
            data.get("session_id", "UNKNOWN")
        )

        save_chat(data)

        logger.info(
            "Chat log stored successfully. session_id=%s",
            data.get("session_id", "UNKNOWN")
        )

        ch.basic_ack(delivery_tag=method.delivery_tag)

        logger.info(
            "ACK sent. delivery_tag=%s",
            method.delivery_tag
        )

    except Exception:
        logger.exception(
            "Error processing message. delivery_tag=%s",
            method.delivery_tag
        )

        ch.basic_nack(
            delivery_tag=method.delivery_tag,
            requeue=True
        )

        logger.warning(
            "NACK sent with requeue=True. delivery_tag=%s",
            method.delivery_tag
        )


channel.basic_consume(
    queue="bfsi_chat_logs_queue",
    on_message_callback=callback,
    auto_ack=False
)

logger.info("Waiting for messages on bfsi_chat_logs_queue...")

try:
    channel.start_consuming()

except KeyboardInterrupt:
    logger.info("Consumer stopped by user")

except Exception:
    logger.exception("Fatal consumer error")

finally:
    try:
        connection.close()
        logger.info("RabbitMQ connection closed")
    except Exception:
        logger.exception("Error while closing RabbitMQ connection")