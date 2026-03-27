"""Kafka producer for sending booking and payment events."""
import json
from kafka import KafkaProducer

from app.config import KAFKA_BROKER


def send_booking_event(booking_id: int, car_id: int, guest_name: str):
    """Send a booking event to Kafka.
    
    Args:
        booking_id: The booking ID.
        car_id: The car ID.
        guest_name: The guest name.
    """
    producer = KafkaProducer(bootstrap_servers=[KAFKA_BROKER])
    message = {
        "booking_id": booking_id,
        "car_id": car_id,
        "guest_name": guest_name
    }
    producer.send(
        topic="booking-events",
        key=f"booking-{booking_id}".encode(),
        value=json.dumps(message).encode()
    )


def send_payment_event(payment_id: int, booking_id: int, status: str):
    """Send a payment event to Kafka.
    
    Args:
        payment_id: The payment ID.
        booking_id: The booking ID.
        status: The payment status.
    """
    producer = KafkaProducer(bootstrap_servers=[KAFKA_BROKER])
    message = {
        "payment_id": payment_id,
        "booking_id": booking_id,
        "status": status
    }
    producer.send(
        topic="payment-events",
        key=f"payment-{payment_id}".encode(),
        value=json.dumps(message).encode()
    )