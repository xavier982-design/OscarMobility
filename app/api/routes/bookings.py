from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, ConfigDict
from datetime import datetime
from decimal import Decimal
from typing import Optional

from app.api.dependencies import get_db
from app.services.payment_service import PaymentService
from app.models import Currency

router = APIRouter()

class BookingRequest(BaseModel):
    car_id: int
    guest_name: str
    guest_email: str
    pickup: datetime
    return_time: datetime
    total_amount: Decimal
    currency: str = Currency.USD.value
    payment_amount: Optional[Decimal] = None
    payment_currency: Optional[str] = None
    payment_idempotency_key: Optional[str] = None

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "car_id": 1,
            "guest_name": "John Doe",
            "guest_email": "john@example.com",
            "pickup": "2026-03-27T10:00:00Z",
            "return_time": "2026-03-28T10:00:00Z",
            "total_amount": 150.00,
            "currency": "USD",
            "payment_amount": 150.00,
            "payment_currency": "USD",
            "payment_idempotency_key": "booking-001"
        }
    })

class BookingResponse(BaseModel):
    success: bool
    booking_id: Optional[int] = None
    error: Optional[str] = None

@router.post("/bookings", response_model=BookingResponse)
def create_booking(request: BookingRequest, db: Session = Depends(get_db)):
    service = PaymentService(db)
    result = service.create_booking(
        car_id=request.car_id,
        guest_name=request.guest_name,
        guest_email=request.guest_email,
        pickup=request.pickup,
        return_time=request.return_time,
        total_amount=request.total_amount,
        currency=request.currency,
        payment_amount=request.payment_amount,
        payment_currency=request.payment_currency,
        payment_idempotency_key=request.payment_idempotency_key
    )
    
    if result.success:
        return BookingResponse(success=True, booking_id=result.booking.id)
    else:
        raise HTTPException(status_code=400, detail=result.error)