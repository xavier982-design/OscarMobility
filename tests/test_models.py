import pytest
from datetime import datetime

from app.models import Booking, Car, Currency, Payment, PaymentStatus


def test_car_creation(db_session):
    car = Car(
        license_plate="ABC123",
        make="Toyota",
        model="Camry",
        year=2020,
        passengers=5
    )
    db_session.add(car)
    db_session.commit()
    assert car.id is not None
    assert car.license_plate == "ABC123"


def test_booking_creation(db_session):
    car = Car(license_plate="DEF456", make="Honda", model="Civic", year=2021, passengers=4)
    db_session.add(car)
    db_session.commit()

    booking = Booking(
        car_id=car.id,
        guest_name="John Doe",
        guest_email="john@example.com",
        car_pickup=datetime(2026, 3, 27, 10, 0),
        car_return=datetime(2026, 3, 28, 10, 0),
        total_amount=100.00,
        currency=Currency.USD
    )
    db_session.add(booking)
    db_session.commit()
    assert booking.id is not None
    assert booking.car_id == car.id


def test_payment_creation(db_session):
    car = Car(license_plate="GHI789", make="Ford", model="Focus", year=2019, passengers=5)
    db_session.add(car)
    db_session.commit()

    booking = Booking(
        car_id=car.id,
        guest_name="Jane Doe",
        guest_email="jane@example.com",
        car_pickup=datetime(2026, 3, 29, 10, 0),
        car_return=datetime(2026, 3, 30, 10, 0),
        total_amount=150.00,
        currency=Currency.USD
    )
    db_session.add(booking)
    db_session.commit()

    payment = Payment(
        booking_id=booking.id,
        amount=150.00,
        currency=Currency.USD,
        status=PaymentStatus.PENDING,
        payment_method="CREDIT_CARD"
    )
    db_session.add(payment)
    db_session.commit()
    assert payment.id is not None
    assert payment.booking_id == booking.id


def test_payment_unique_idempotency_key(db_session):
    car = Car(license_plate="JKL012", make="BMW", model="X3", year=2022, passengers=5)
    db_session.add(car)
    db_session.commit()

    booking = Booking(
        car_id=car.id,
        guest_name="Alice",
        guest_email="alice@example.com",
        car_pickup=datetime(2026, 4, 1, 10, 0),
        car_return=datetime(2026, 4, 2, 10, 0),
        total_amount=200.00,
        currency=Currency.USD
    )
    db_session.add(booking)
    db_session.commit()

    payment1 = Payment(
        booking_id=booking.id,
        amount=200.00,
        currency=Currency.USD,
        status=PaymentStatus.PENDING,
        idempotency_key="unique-key-123",
        payment_method="CREDIT_CARD"
    )
    db_session.add(payment1)
    db_session.commit()

    payment2 = Payment(
        booking_id=booking.id,
        amount=200.00,
        currency=Currency.USD,
        status=PaymentStatus.PENDING,
        idempotency_key="unique-key-123",  # Duplicate
        payment_method="CREDIT_CARD"
    )
    db_session.add(payment2)
    with pytest.raises(Exception):  # IntegrityError from unique constraint
        db_session.commit()