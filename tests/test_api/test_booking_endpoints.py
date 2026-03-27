import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_create_booking_endpoint_success():
    response = client.post("/bookings", json={
        "car_id": 1,
        "guest_name": "Test User",
        "guest_email": "test@example.com",
        "pickup": "2026-04-15T10:00:00",
        "return_time": "2026-04-16T10:00:00",
        "total_amount": 100.0,
        "currency": "USD"
    })
    assert response.status_code == 200
    assert "booking_id" in response.json()


def test_create_booking_endpoint_missing_fields():
    response = client.post("/bookings", json={
        "car_id": 1,
        "guest_name": "Test User"
        # Missing required fields
    })
    assert response.status_code >= 400


def test_complete_payment_endpoint_success():
    response = client.post("/payments/1/complete", json={
        "payment_currency": "USD"
    })
    assert response.status_code == 200
    assert "payment_id" in response.json()


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"