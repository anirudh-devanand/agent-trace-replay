from confluent_kafka.admin import AdminClient

from shared.config import Settings


def check_kafka_connection(settings: Settings) -> tuple[bool, str]:
    try:
        admin = AdminClient({"bootstrap.servers": settings.kafka_bootstrap_servers})
        metadata = admin.list_topics(timeout=5)
        if metadata is None:
            return False, "kafka metadata unavailable"
        return True, "ok"
    except Exception as exc:
        return False, str(exc)
