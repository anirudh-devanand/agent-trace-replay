import asyncio
import logging

from prometheus_client import start_http_server

from shared.config import get_settings
from worker.consumer_loop import run_consumer_loop

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)


def main() -> None:
    settings = get_settings()
    start_http_server(settings.worker_metrics_port)
    asyncio.run(run_consumer_loop())


if __name__ == "__main__":
    main()
