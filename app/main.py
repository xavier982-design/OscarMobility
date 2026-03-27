"""FastAPI application for Oscar booking and payment system."""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel


class CreateBookingRequest(BaseModel):
    car_id: int
    guest_name: str
    guest_email: str
    pickup: str
    return_time: str
    total_amount: float
    currency: str = "USD"


class CompletePaymentRequest(BaseModel):
    payment_currency: str


app = FastAPI(title="Oscar", description="Booking and Payment System")


@app.post("/bookings")
def create_booking(request: CreateBookingRequest):
    """Create a new booking."""
    return {"booking_id": 1}


@app.post("/payments/{payment_id}/complete")
def complete_payment(payment_id: int, request: CompletePaymentRequest):
    """Complete a payment."""
    return {"payment_id": payment_id}

@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "ok"}
