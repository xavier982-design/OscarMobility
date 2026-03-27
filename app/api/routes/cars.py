from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List

from app.api.dependencies import get_db
from app.models.payment import Car

router = APIRouter()

class CarResponse(BaseModel):
    id: int
    license_plate: str
    make: str
    model: str
    year: int
    passengers: int

@router.get("/cars", response_model=List[CarResponse])
def list_cars(db: Session = Depends(get_db)):
    cars = db.query(Car).all()
    return cars