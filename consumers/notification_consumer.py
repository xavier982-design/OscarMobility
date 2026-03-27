import json
import logging
from sqlalchemy.orm import sessionmaker

from consumers.base_consumer import BaseConsumer

logger = logging.getLogger(__name__)


class NotificationConsumer(BaseConsumer):
    def __init__(self, db_session_factory: sessionmaker):
        super().__init__(
            topic='booking.events',
            group_id='notification-service',
            db_session_factory=db_session_factory,
            bootstrap_servers=['kafka:9092'],
        )

    def process_event(self, event: dict):
        event_type = event.get('type')
        if event_type == 'BookingCreated':
            self.send_booking_confirmation(event)
        else:
            logger.warning(f"Unknown event type: {event_type}")

    def send_booking_confirmation(self, event: dict):
        # Empty function for SendGrid integration
        # TODO: Implement SendGrid API call
        guest_email = event['guest_email']
        booking_id = event['booking_id']
        logger.info(f"Sending booking confirmation to {guest_email} for booking {booking_id}")
        pass