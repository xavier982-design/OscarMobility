from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from threading import Lock
from typing import Optional
import json
import redis
from kafka import KafkaProducer

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import KAFKA_BROKER
from app.models import Booking, BookingStatus, Car, Currency, ExchangeRate, Payment, PaymentMethod, PaymentStatus, Refund, RefundStatus

_booking_locks: dict[int, Lock] = {}
_booking_locks_lock = Lock()
_payment_locks: dict[int, Lock] = {}
_payment_locks_lock = Lock()


def _get_booking_lock(car_id: int) -> Lock:
    with _booking_locks_lock:
        if car_id not in _booking_locks:
            _booking_locks[car_id] = Lock()
        return _booking_locks[car_id]


def _get_payment_lock(booking_id: int) -> Lock:
    with _payment_locks_lock:
        if booking_id not in _payment_locks:
            _payment_locks[booking_id] = Lock()
        return _payment_locks[booking_id]


@dataclass
class CurrencyConversion:
    original_amount: Decimal
    original_currency: str
    converted_amount: Decimal
    converted_currency: str
    exchange_rate: ExchangeRate


@dataclass
class AvailabilityResult:
    available: bool
    conflicting_bookings: list[Booking] | None = None


@dataclass
class BookingResult:
    success: bool
    booking: Optional[Booking] = None
    error: Optional[str] = None


@dataclass
class PaymentResult:
    success: bool
    payment: Optional[Payment] = None
    currency_conversion: Optional[CurrencyConversion] = None
    error: Optional[str] = None


@dataclass
class CancelResult:
    success: bool
    booking: Optional[Booking] = None
    refund: Optional["Refund"] = None
    error: Optional[str] = None


class PaymentService:
    def __init__(self, db: Session):
        self.db = db
        self.redis = redis.Redis(host='localhost', port=6379, decode_responses=True)
        self.kafka_producer = KafkaProducer(
            bootstrap_servers=[KAFKA_BROKER],
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )

    def create_booking(
        self,
        car_id: int,
        guest_name: str,
        guest_email: str,
        pickup: datetime,
        return_time: datetime,
        total_amount: Decimal,
        currency: str = Currency.USD.value,
        payment_amount: Optional[Decimal] = None,
        payment_currency: Optional[str] = None,
        payment_idempotency_key: Optional[str] = None,
    ) -> BookingResult:
        lock = _get_booking_lock(car_id)
        with lock:
            try:
                car = self.db.execute(
                    select(Car).where(Car.id == car_id).with_for_update()
                ).scalar_one_or_none()
                if not car:
                    return BookingResult(success=False, error=f"Car with id {car_id} not found")

                if payment_idempotency_key:
                    existing_by_key = self.db.execute(
                        select(Payment).where(Payment.idempotency_key == payment_idempotency_key).with_for_update()
                    ).scalar_one_or_none()
                    if existing_by_key:
                        booking = self.db.execute(
                            select(Booking).where(Booking.id == existing_by_key.booking_id)
                        ).scalar_one_or_none()
                        if booking:
                            return BookingResult(success=True, booking=booking)
                        return BookingResult(success=False, error="Idempotent payment key found but booking missing")

                availability = self.check_car_availability(car_id, pickup, return_time, for_update=True)
                if not availability.available:
                    return BookingResult(
                        success=False,
                        error="Car is not available for the selected dates",
                    )

                booking = Booking(
                    car_id=car_id,
                    guest_name=guest_name,
                    guest_email=guest_email,
                    car_pickup=pickup,
                    car_return=return_time,
                    total_amount=total_amount,
                    currency=currency,
                )
                self.db.add(booking)
                self.db.flush()

                payment_result = None
                if payment_amount is not None and payment_currency is not None:
                    payment = Payment(
                        booking_id=booking.id,
                        amount=payment_amount,
                        currency=payment_currency,
                        status=PaymentStatus.PENDING,
                        payment_method=PaymentMethod.CREDIT_CARD.value,
                        idempotency_key=payment_idempotency_key,
                    )
                    self.db.add(payment)
                    self.db.flush()

                    payment_lock = _get_payment_lock(booking.id)
                    with payment_lock:
                        existing_payment = self.db.execute(
                            select(Payment)
                            .where(
                                Payment.booking_id == booking.id,
                                Payment.status == PaymentStatus.COMPLETED,
                            )
                        ).scalar_one_or_none()
                        if existing_payment:
                            self.db.rollback()
                            return BookingResult(success=False, error="Payment already processed for this booking")

                        conversion = self.convert_currency(payment_amount, payment_currency, currency)
                        payment.status = PaymentStatus.COMPLETED
                        payment.exchange_rate_id = conversion.exchange_rate.id if conversion.exchange_rate else None
                        payment.amount_in_base_currency = conversion.converted_amount
                        payment.transaction_ref = f"TXN-{booking.id}-{int(datetime.now(timezone.utc).timestamp())}"
                        payment_result = payment

                self.db.commit()
            except IntegrityError as e:
                self.db.rollback()
                return BookingResult(success=False, error=f"Integrity error: {str(e)}")
            except Exception as e:
                self.db.rollback()
                return BookingResult(success=False, error=str(e))

        self.db.refresh(booking)
        if payment_result:
            self.db.refresh(payment_result)

        # Publish booking created event
        self.kafka_producer.send(
            'booking.events',
            key=str(booking.id).encode('utf-8'),
            value={
                'type': 'BookingCreated',
                'booking_id': booking.id,
                'car_id': car_id,
                'guest_name': guest_name,
                'guest_email': guest_email,
                'total_amount': str(total_amount),
                'currency': currency,
                'pickup': pickup.isoformat(),
                'return_time': return_time.isoformat(),
                'payment_amount': str(payment_amount) if payment_amount else None,
                'payment_currency': payment_currency,
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
        )
        self.kafka_producer.flush()

        return BookingResult(success=True, booking=booking)

    def check_car_availability(
        self,
        car_id: int,
        pickup: datetime,
        return_time: datetime,
        exclude_booking_id: Optional[int] = None,
        for_update: bool = False,
    ) -> AvailabilityResult:
        query = select(Booking).where(
            Booking.car_id == car_id,
            Booking.car_pickup < return_time,
            Booking.car_return > pickup,
        )
        if exclude_booking_id:
            query = query.where(Booking.id != exclude_booking_id)
        if for_update:
            query = query.with_for_update()

        conflicting = list(self.db.execute(query).scalars().all())
        return AvailabilityResult(
            available=len(conflicting) == 0,
            conflicting_bookings=conflicting if conflicting else None,
        )

    def get_exchange_rate(self, from_currency: str, to_currency: str) -> Optional[ExchangeRate]:
        if from_currency == to_currency:
            return None
        
        cache_key = f"exchange_rate:{from_currency}:{to_currency}"
        cached = self.redis.get(cache_key)
        if cached:
            try:
                data = json.loads(cached)
                fetched_at = datetime.fromisoformat(data['fetched_at'])
                if datetime.now() - fetched_at < timedelta(hours=1):
                    return ExchangeRate(
                        id=data['id'],
                        base_currency=data['base_currency'],
                        target_currency=data['target_currency'],
                        rate=Decimal(data['rate']),
                        fetched_at=fetched_at
                    )
            except (json.JSONDecodeError, KeyError, ValueError):
                pass  # invalid cache, proceed to DB
        
        result = self.db.execute(
            select(ExchangeRate)
            .where(
                ExchangeRate.base_currency == from_currency,
                ExchangeRate.target_currency == to_currency,
            )
            .order_by(ExchangeRate.fetched_at.desc())
            .limit(1)
        ).scalar_one_or_none()
        
        if result:
            data = {
                'id': result.id,
                'base_currency': result.base_currency,
                'target_currency': result.target_currency,
                'rate': str(result.rate),
                'fetched_at': result.fetched_at.isoformat()
            }
            self.redis.setex(cache_key, 3600, json.dumps(data))
        
        return result

    def convert_currency(
        self, amount: Decimal, from_currency: str, to_currency: str
    ) -> CurrencyConversion:
        exchange_rate = self.get_exchange_rate(from_currency, to_currency)
        
        if not exchange_rate:
            return CurrencyConversion(
                original_amount=amount,
                original_currency=from_currency,
                converted_amount=amount,
                converted_currency=to_currency,
                exchange_rate=None,
            )
        
        converted = amount * exchange_rate.rate
        return CurrencyConversion(
            original_amount=amount,
            original_currency=from_currency,
            converted_amount=converted.quantize(Decimal("0.01")),
            converted_currency=to_currency,
            exchange_rate=exchange_rate,
        )

    def cancel_booking(
        self,
        booking_id: int,
        idempotency_key: Optional[str] = None,
        reason: Optional[str] = None,
    ) -> CancelResult:
        # Offer full booking+payment cancellation with optional refund.
        # Uses both in-memory and DB row locks for correctness.
        existing_refund = None
        try:
            booking = self.db.execute(
                select(Booking).where(Booking.id == booking_id).with_for_update()
            ).scalar_one_or_none()

            if not booking:
                return CancelResult(success=False, error=f"Booking {booking_id} not found")

            if idempotency_key:
                existing_refund = self.db.execute(
                    select(Refund).where(
                        Refund.idempotency_key == idempotency_key,
                        Refund.booking_id == booking_id,
                    ).with_for_update()
                ).scalar_one_or_none()
                if existing_refund:
                    return CancelResult(success=True, booking=booking, refund=existing_refund)

            if booking.status == BookingStatus.CANCELLED:
                return CancelResult(success=False, error="Booking already cancelled")

            lock = _get_booking_lock(booking.car_id)
            with lock:
                # idempotency check already done at transaction entrance
                # second path after booking lock can safely proceed with a new refund

                # mark booking cancelled
                booking.status = BookingStatus.CANCELLED
                booking.cancelled_at = datetime.now(timezone.utc)
                booking.cancellation_reason = reason

                # If completed payment exists, refund it
                payment = self.db.execute(
                    select(Payment)
                    .where(
                        Payment.booking_id == booking_id,
                        Payment.status == PaymentStatus.COMPLETED,
                    )
                    .with_for_update()
                ).scalar_one_or_none()

                refund_obj = None
                if payment:
                    payment_lock = _get_payment_lock(booking_id)
                    with payment_lock:
                        # check existing refund by idempotency if provided
                        if idempotency_key:
                            existing_refund = self.db.execute(
                                select(Refund).where(
                                    Refund.idempotency_key == idempotency_key,
                                    Refund.payment_id == payment.id,
                                ).with_for_update()
                            ).scalar_one_or_none()
                            if existing_refund:
                                return CancelResult(success=True, booking=booking, refund=existing_refund)

                        # Validate we haven't already refunded payment as a separate model row
                        already_refunded = self.db.execute(
                            select(Refund).where(Refund.payment_id == payment.id, Refund.status == RefundStatus.COMPLETED)
                        ).scalars().first()
                        if already_refunded:
                            return CancelResult(success=False, error="Payment already refunded")

                        # Payment gateway refund stub (synchronous)
                        refund_tx_ref = f"RFND-{payment.id}-{int(datetime.now(timezone.utc).timestamp())}"

                        # create refund row
                        refund_obj = Refund(
                            payment_id=payment.id,
                            booking_id=booking.id,
                            idempotency_key=idempotency_key,
                            amount=payment.amount_in_base_currency or payment.amount,
                            currency=booking.currency,
                            status=RefundStatus.COMPLETED,
                            refund_transaction_ref=refund_tx_ref,
                        )
                        self.db.add(refund_obj)
                        self.db.flush()

                        # payment status update
                        payment.status = PaymentStatus.REFUNDED

                self.db.commit()

                self.kafka_producer.send(
                    'booking.events',
                    key=str(booking.id).encode('utf-8'),
                    value={
                        'type': 'BookingCancelled',
                        'booking_id': booking.id,
                        'cancelled_at': booking.cancelled_at.isoformat() if booking.cancelled_at else None,
                        'reason': booking.cancellation_reason,
                        'timestamp': datetime.now(timezone.utc).isoformat(),
                    },
                )

                if refund_obj:
                    self.kafka_producer.send(
                        'payment.events',
                        key=str(payment.id).encode('utf-8'),
                        value={
                            'type': 'PaymentRefunded',
                            'payment_id': payment.id,
                            'booking_id': booking.id,
                            'refund_id': refund_obj.id,
                            'amount': str(refund_obj.amount),
                            'currency': refund_obj.currency,
                            'refund_transaction_ref': refund_obj.refund_transaction_ref,
                            'timestamp': datetime.now(timezone.utc).isoformat(),
                        },
                    )
                self.kafka_producer.flush()

                return CancelResult(success=True, booking=booking, refund=refund_obj)

        except IntegrityError as e:
            self.db.rollback()
            return CancelResult(success=False, error=f"Integrity error: {e}")
        except Exception as e:
            self.db.rollback()
            return CancelResult(success=False, error=str(e))

    def complete_payment(
        self,
        booking: Booking,
        payment: Payment,
        payment_currency: str,
        idempotency_key: Optional[str] = None,
    ) -> PaymentResult:
        lock = _get_booking_lock(booking.car_id)
        with lock:
            try:
                booking = self.db.execute(
                    select(Booking).where(Booking.id == booking.id).with_for_update()
                ).scalar_one()
                availability = self.check_car_availability(
                    booking.car_id, booking.car_pickup, booking.car_return, exclude_booking_id=booking.id, for_update=True
                )
                if not availability.available:
                    return PaymentResult(
                        success=False,
                        error=f"Car is not available for the selected dates. Conflicting bookings: {[b.id for b in availability.conflicting_bookings]}",
                    ) if availability.conflicting_bookings else PaymentResult(
                        success=False,
                        error="Car is not available for the selected dates",
                    )

                payment_lock = _get_payment_lock(booking.id)
                with payment_lock:
                    if idempotency_key:
                        existing_by_key = self.db.execute(
                            select(Payment).where(
                                Payment.idempotency_key == idempotency_key,
                                Payment.booking_id == booking.id,
                            ).with_for_update()
                        ).scalar_one_or_none()
                        if existing_by_key:
                            return PaymentResult(success=True, payment=existing_by_key)

                    self.db.refresh(payment)
                    if payment.status == PaymentStatus.COMPLETED:
                        return PaymentResult(success=False, error="Payment already completed")

                    conversion = self.convert_currency(
                        payment.amount, payment_currency, booking.currency
                    )

                    payment.status = PaymentStatus.COMPLETED
                    payment.exchange_rate_id = conversion.exchange_rate.id if conversion.exchange_rate else None
                    payment.amount_in_base_currency = conversion.converted_amount
                    payment.transaction_ref = f"TXN-{booking.id}-{int(datetime.now(timezone.utc).timestamp())}"
                    if not payment.payment_method:
                        payment.payment_method = PaymentMethod.CREDIT_CARD.value
                    if idempotency_key and not payment.idempotency_key:
                        payment.idempotency_key = idempotency_key

                    self.db.commit()
                    self.db.refresh(payment)

                    # Publish payment completed event
                    self.kafka_producer.send(
                        'payment.events',
                        key=str(booking.id).encode('utf-8'),
                        value={
                            'type': 'PaymentCompleted',
                            'payment_id': payment.id,
                            'booking_id': booking.id,
                            'amount': str(payment.amount),
                            'currency': payment_currency,
                            'original_currency': booking.currency,
                            'exchange_rate': str(conversion.exchange_rate.rate) if conversion.exchange_rate else None,
                            'amount_in_base_currency': str(payment.amount_in_base_currency),
                            'transaction_ref': payment.transaction_ref,
                            'timestamp': datetime.now(timezone.utc).isoformat()
                        }
                    )
                    self.kafka_producer.flush()

                return PaymentResult(success=True, payment=payment, currency_conversion=conversion)
            except IntegrityError as e:
                self.db.rollback()
                return PaymentResult(success=False, error=f"Integrity error: {str(e)}")
            except Exception as e:
                self.db.rollback()
                return PaymentResult(success=False, error=str(e))
