import pytest
from datetime import datetime
from decimal import Decimal

from app.models import Booking, BookingStatus, Car, Currency, Payment, PaymentMethod, PaymentStatus, Refund, RefundStatus
from app.services.payment_service import PaymentService


def test_create_booking_success(db_session):
    car = Car(license_plate="MNO345", make="Tesla", model="Model 3", year=2023, passengers=5)
    db_session.add(car)
    db_session.commit()

    service = PaymentService(db_session)
    result = service.create_booking(
        car_id=car.id,
        guest_name="Bob",
        guest_email="bob@example.com",
        pickup=datetime(2026, 4, 3, 10, 0),
        return_time=datetime(2026, 4, 4, 10, 0),
        total_amount=Decimal("250.00"),
        currency=Currency.USD
    )
    assert result.success
    assert result.booking.guest_name == "Bob"
    assert result.booking.total_amount == Decimal("250.00")


def test_create_booking_car_not_found(db_session):
    service = PaymentService(db_session)
    result = service.create_booking(
        car_id=999,
        guest_name="Charlie",
        guest_email="charlie@example.com",
        pickup=datetime(2026, 4, 5, 10, 0),
        return_time=datetime(2026, 4, 6, 10, 0),
        total_amount=Decimal("100.00"),
        currency=Currency.USD
    )
    assert not result.success
    assert "not found" in result.error


def test_create_booking_with_payment(db_session):
    car = Car(license_plate="PQR678", make="Audi", model="A4", year=2021, passengers=5)
    db_session.add(car)
    db_session.commit()

    service = PaymentService(db_session)
    result = service.create_booking(
        car_id=car.id,
        guest_name="Diana",
        guest_email="diana@example.com",
        pickup=datetime(2026, 4, 7, 10, 0),
        return_time=datetime(2026, 4, 8, 10, 0),
        total_amount=Decimal("300.00"),
        currency=Currency.USD,
        payment_amount=Decimal("300.00"),
        payment_currency=Currency.USD,
        payment_idempotency_key="payment-key-456"
    )
    if not result.success:
        print(f"Booking creation failed: {result.error}")
    assert result.success, f"Booking failed with error: {result.error}"
    assert len(result.booking.payments) > 0, "No payments created"
    assert result.booking.payments[0].status == PaymentStatus.COMPLETED


def test_check_car_availability_available(db_session):
    car = Car(license_plate="STU901", make="Mercedes", model="C-Class", year=2020, passengers=5)
    db_session.add(car)
    db_session.commit()

    service = PaymentService(db_session)
    result = service.check_car_availability(
        car_id=car.id,
        pickup=datetime(2026, 4, 9, 10, 0),
        return_time=datetime(2026, 4, 10, 10, 0)
    )
    assert result.available


def test_check_car_availability_conflict(db_session):
    car = Car(license_plate="VWX234", make="Nissan", model="Altima", year=2019, passengers=5)
    db_session.add(car)
    db_session.commit()

    booking = Booking(
        car_id=car.id,
        guest_name="Eve",
        guest_email="eve@example.com",
        car_pickup=datetime(2026, 4, 11, 10, 0),
        car_return=datetime(2026, 4, 12, 10, 0),
        total_amount=Decimal("200.00"),
        currency=Currency.USD
    )
    db_session.add(booking)
    db_session.commit()

    service = PaymentService(db_session)
    result = service.check_car_availability(
        car_id=car.id,
        pickup=datetime(2026, 4, 11, 12, 0),  # Overlapping
        return_time=datetime(2026, 4, 12, 8, 0)
    )
    assert not result.available
    assert len(result.conflicting_bookings) == 1


def test_convert_currency_no_exchange_rate(db_session):
    service = PaymentService(db_session)
    result = service.convert_currency(
        amount=Decimal("100.00"),
        from_currency=Currency.USD,
        to_currency=Currency.EUR
    )
    # When no rate exists, should return amount unchanged
    assert result.converted_amount == Decimal("100.00")
    assert result.exchange_rate is None


def test_complete_payment_success(db_session):
    car = Car(license_plate="YZA567", make="Chevrolet", model="Malibu", year=2022, passengers=5)
    db_session.add(car)
    db_session.commit()

    booking = Booking(
        car_id=car.id,
        guest_name="Frank",
        guest_email="frank@example.com",
        car_pickup=datetime(2026, 4, 13, 10, 0),
        car_return=datetime(2026, 4, 14, 10, 0),
        total_amount=Decimal("400.00"),
        currency=Currency.USD
    )
    db_session.add(booking)
    db_session.commit()

    payment = Payment(
        booking_id=booking.id,
        amount=Decimal("400.00"),
        currency=Currency.USD,
        status=PaymentStatus.PENDING,
        payment_method="CREDIT_CARD"
    )
    db_session.add(payment)
    db_session.commit()

    service = PaymentService(db_session)
    result = service.complete_payment(
        booking=booking,
        payment=payment,
        payment_currency=Currency.USD
    )
    assert result.success
    assert result.payment.status == PaymentStatus.COMPLETED


def test_cancel_booking_without_payment(db_session):
    car = Car(license_plate="CXL123", make="Toyota", model="Corolla", year=2020, passengers=5)
    db_session.add(car)
    db_session.commit()

    booking = Booking(
        car_id=car.id,
        guest_name="Gina",
        guest_email="gina@example.com",
        car_pickup=datetime(2026, 4, 20, 10, 0),
        car_return=datetime(2026, 4, 21, 10, 0),
        total_amount=Decimal("120.00"),
        currency=Currency.USD,
    )
    db_session.add(booking)
    db_session.commit()

    service = PaymentService(db_session)
    result = service.cancel_booking(
        booking_id=booking.id,
        idempotency_key="cancel-key-001",
        reason="Plans changed",
    )
    assert result.success
    assert result.booking.status == BookingStatus.CANCELLED
    assert result.refund is None


def test_cancel_booking_with_completed_payment(db_session):
    car = Car(license_plate="CXL999", make="Honda", model="Civic", year=2020, passengers=5)
    db_session.add(car)
    db_session.commit()

    booking = Booking(
        car_id=car.id,
        guest_name="Helen",
        guest_email="helen@example.com",
        car_pickup=datetime(2026, 4, 22, 10, 0),
        car_return=datetime(2026, 4, 23, 10, 0),
        total_amount=Decimal("180.00"),
        currency=Currency.USD,
    )
    db_session.add(booking)
    db_session.commit()

    payment = Payment(
        booking_id=booking.id,
        amount=Decimal("180.00"),
        currency=Currency.USD,
        amount_in_base_currency=Decimal("180.00"),
        status=PaymentStatus.COMPLETED,
        payment_method=PaymentMethod.CREDIT_CARD.value,
        transaction_ref="TXN-REFUND-001"
    )
    db_session.add(payment)
    db_session.commit()

    service = PaymentService(db_session)
    result = service.cancel_booking(
        booking_id=booking.id,
        idempotency_key="cancel-key-002",
        reason="Change of plans",
    )
    assert result.success
    assert result.booking.status == BookingStatus.CANCELLED
    assert result.refund is not None
    assert result.refund.status == RefundStatus.COMPLETED
    assert result.refund.amount == Decimal("180.00")


def test_cancel_booking_idempotent(db_session):
    car = Car(license_plate="CXL777", make="Volvo", model="S60", year=2021, passengers=5)
    db_session.add(car)
    db_session.commit()

    booking = Booking(
        car_id=car.id,
        guest_name="Ivan",
        guest_email="ivan@example.com",
        car_pickup=datetime(2026, 4, 24, 10, 0),
        car_return=datetime(2026, 4, 25, 10, 0),
        total_amount=Decimal("130.00"),
        currency=Currency.USD,
    )
    db_session.add(booking)
    db_session.commit()

    payment = Payment(
        booking_id=booking.id,
        amount=Decimal("130.00"),
        currency=Currency.USD,
        amount_in_base_currency=Decimal("130.00"),
        status=PaymentStatus.COMPLETED,
        payment_method=PaymentMethod.CREDIT_CARD.value,
        transaction_ref="TXN-REFUND-002"
    )
    db_session.add(payment)
    db_session.commit()

    service = PaymentService(db_session)
    first = service.cancel_booking(booking_id=booking.id, idempotency_key="cancel-key-003", reason="Changed mind")
    second = service.cancel_booking(booking_id=booking.id, idempotency_key="cancel-key-003", reason="Changed mind")

    assert first.success
    assert second.success
    assert first.refund is not None
    assert second.refund is not None
    assert first.refund.id == second.refund.id
