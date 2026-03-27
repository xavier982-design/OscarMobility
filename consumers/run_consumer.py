#!/usr/bin/env python3
import argparse
import logging
import sys
import os

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.config import DATABASE_URL

from consumers.notification_consumer import NotificationConsumer
from consumers.inventory_consumer import InventoryConsumer

logging.basicConfig(level=logging.INFO)

CONSUMER_MAP = {
    'notification': NotificationConsumer,
    'inventory': InventoryConsumer,
}


def main():
    parser = argparse.ArgumentParser(description='Run a Kafka consumer')
    parser.add_argument('consumer', choices=CONSUMER_MAP.keys(), help='Consumer type to run')
    args = parser.parse_args()

    engine = create_engine(DATABASE_URL)
    session_factory = sessionmaker(bind=engine)

    consumer_cls = CONSUMER_MAP[args.consumer]
    consumer = consumer_cls(session_factory)
    consumer.run()


if __name__ == '__main__':
    main()
