import json
import logging
from sqlalchemy.orm import sessionmaker
from app.models import Car

from consumers.base_consumer import BaseConsumer

logger = logging.getLogger(__name__)


class InventoryConsumer(BaseConsumer):
    def __init__(self, db_session_factory: sessionmaker):
        super().__init__(
            topic='booking.events',
            group_id='inventory-service',
            db_session_factory=db_session_factory,
            bootstrap_servers=['kafka:9092'],
        )

    def process_event(self, event: dict):
        event_type = event.get('type')
        if event_type == 'BookingCreated':
            self.update_car_status(event)
        else:
            logger.warning(f"Unknown event type: {event_type}")

    def update_car_status(self, event: dict):
        car_id = event['car_id']
        session = self.db_factory()
        try:
            car = session.query(Car).filter(Car.id == car_id).first()
            if car:
                car.status = 'RESERVED'
                session.commit()
                logger.info(f"Updated car {car_id} status to RESERVED")
            else:
                logger.error(f"Car {car_id} not found")
        except Exception as e:
            session.rollback()
            logger.error(f"Error updating car status: {e}")
        finally:
            session.close()