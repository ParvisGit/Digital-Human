import pika


def get_connection():

    connection = pika.BlockingConnection(
        pika.ConnectionParameters(
            host="localhost",
            heartbeat=600,
            blocked_connection_timeout=300
        )
    )

    return connection