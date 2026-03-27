import json
import logging
import time
from kafka import KafkaConsumer
from kafka.errors import NoBrokersAvailable
from sqlalchemy.orm import sessionmaker

logger = logging.getLogger(__name__)


class BaseConsumer:
    def __init__(
        self,
        topic: str,
        group_id: str,
        db_session_factory: sessionmaker,
        bootstrap_servers=None,
        retries: int = 10,
        retry_delay: int = 5,
    ):
        if bootstrap_servers is None:
            bootstrap_servers = ['kafka:9092']

        self.consumer = None
        for attempt in range(1, retries + 1):
            try:
                self.consumer = KafkaConsumer(
                    topic,
                    bootstrap_servers=bootstrap_servers,
                    group_id=group_id,
                    value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                    auto_offset_reset='earliest',
                )
                logger.info(f"Kafka consumer connected on attempt {attempt}")
                break
            except NoBrokersAvailable as e:
                logger.warning(
                    f"No Kafka brokers available (attempt {attempt}/{retries}), retrying in {retry_delay}s: {e}"
                )
                time.sleep(retry_delay)
        else:
            raise

        self.db_factory = db_session_factory

    def run(self):
        logger.info(f"Starting {self.__class__.__name__}")
        try:
            for message in self.consumer:
                try:
                    self.process_event(message.value)
                except Exception as e:
                    logger.exception(f"Error processing event: {e}")
        except KeyboardInterrupt:
            logger.info(f"Stopping {self.__class__.__name__}")
        finally:
            self.consumer.close()

    def process_event(self, event: dict):
        raise NotImplementedError("Subclasses must implement process_event")
