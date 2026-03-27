from fastapi import FastAPI
from app.api.routes.bookings import router as bookings_router
from app.api.routes.payments import router as payments_router
from app.api.routes.cars import router as cars_router

app = FastAPI(
    title="Oscar Payment API",
    description="API for booking and payment management",
    version="1.0.0"
)

app.include_router(bookings_router)
app.include_router(payments_router)
app.include_router(cars_router)

@app.get("/")
def read_root():
    return {"message": "Oscar Payment API"}