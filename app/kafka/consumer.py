"""Kafka consumer for processing booking and payment events."""
import json
import logging
from kafka import KafkaConsumer
from sqlalchemy.orm import Session

from app.config import KAFKA_BROKER
from app.services.payment_service import PaymentService


logger = logging.getLogger(__name__)


def process_payment_update(db_session: Session):
    """Process payment update events from Kafka.
    
    Args:
        db_session: SQLAlchemy session for DB operations.
    """
    consumer = KafkaConsumer(
        'payment-events',
        bootstrap_servers=[KAFKA_BROKER],
        value_deserializer=lambda m: json.loads(m.decode('utf-8'))
    )
    
    service = PaymentService(db_session)
    
    for message in consumer:
        try:
            data = message.value
            payment_id = data.get('payment_id')
            status = data.get('status')
            
            # Process payment update
            logger.info(f"Processing payment {payment_id} with status {status}")
            # Additional logic would go here
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON in message: {message.value}")
        except Exception as e:
            logger.error(f"Error processing payment event: {e}")


def process_booking_event(db_session: Session):
    """Process booking events from Kafka.
    
    Args:
        db_session: SQLAlchemy session for DB operations.
    """
    consumer = KafkaConsumer(
        'booking-events',
        bootstrap_servers=[KAFKA_BROKER],
        value_deserializer=lambda m: json.loads(m.decode('utf-8'))
    )
    
    for message in consumer:
        try:
            data = message.value
            booking_id = data.get('booking_id')
            
            # Process booking event
            logger.info(f"Processing booking {booking_id}")
            # Additional logic would go here
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON in message: {message.value}")
        except Exception as e:
            logger.error(f"Error processing booking event: {e}")