from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from decimal import Decimal
from typing import Optional

from app.api.dependencies import get_db
from app.models import Booking, Payment, PaymentStatus
from app.services.payment_service import PaymentService

router = APIRouter()

class CompletePaymentRequest(BaseModel):
    amount: Decimal
    currency: str
    idempotency_key: Optional[str] = None

class CompletePaymentResponse(BaseModel):
    success: bool
    payment_id: Optional[int] = None
    error: Optional[str] = None

@router.post("/payments/{booking_id}/complete", response_model=CompletePaymentResponse)
def complete_payment(booking_id: int, request: CompletePaymentRequest, db: Session = Depends(get_db)):
    service = PaymentService(db)

    # existing service method signature uses booking and payment objects;
    # for stubbed API we can load booking and payment via DB query.
    from app.models import Booking, Payment

    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    payment = db.query(Payment).filter(Payment.booking_id == booking_id, Payment.status == PaymentStatus.PENDING).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Pending payment not found")

    result = service.complete_payment(
        booking=booking,
        payment=payment,
        payment_currency=request.currency,
        idempotency_key=request.idempotency_key
    )

    if result.success:
        return CompletePaymentResponse(success=True, payment_id=result.payment.id)
    else:
        raise HTTPException(status_code=400, detail=result.error)


class CancelBookingRequest(BaseModel):
    idempotency_key: Optional[str] = None
    reason: Optional[str] = None


class CancelBookingResponse(BaseModel):
    success: bool
    booking_id: Optional[int] = None
    refund_id: Optional[int] = None
    error: Optional[str] = None


@router.post("/bookings/{booking_id}/cancel", response_model=CancelBookingResponse)
def cancel_booking(booking_id: int, request: CancelBookingRequest, db: Session = Depends(get_db)):
    service = PaymentService(db)
    result = service.cancel_booking(
        booking_id=booking_id,
        idempotency_key=request.idempotency_key,
        reason=request.reason,
    )

    if result.success:
        return CancelBookingResponse(
            success=True,
            booking_id=result.booking.id if result.booking else None,
            refund_id=result.refund.id if result.refund else None,
        )
    else:
        raise HTTPException(status_code=400, detail=result.error)