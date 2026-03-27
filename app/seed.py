#!/usr/bin/env python3

import time
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.config import DATABASE_URL
from app.db import Base
from app.models.payment import Car

def wait_for_database(engine, max_attempts=60, delay=2):
    """Wait for database to be ready"""
    for attempt in range(max_attempts):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
                print(f"Database connection successful on attempt {attempt + 1}")
            print("Database is ready!")
            return True
        except Exception as e:
            print(f"Database not ready (attempt {attempt + 1}/{max_attempts}): {e}")
            time.sleep(delay)
    return False

def seed_database():
    # Create engine
    print(f"DATABASE_URL: {DATABASE_URL}")
    engine = create_engine(DATABASE_URL)

    # Wait for database to be ready
    if not wait_for_database(engine):
        raise Exception("Database never became ready")

    # Create all tables
    Base.metadata.create_all(bind=engine)

    # Create session
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()

    try:
        # Check if cars already exist
        existing_cars = db.query(Car).count()
        print(f"Existing cars count: {existing_cars}")
        if existing_cars > 0:
            print(f"Database already has {existing_cars} cars. Skipping seed.")
            return

        # Seed cars
        cars_data = [
            {   
                "id": 1,
                "license_plate": "ABC123",
                "make": "Toyota",
                "model": "Camry",
                "year": 2020,
                "passengers": 5
            },
            {   
                "id": 2,
                "license_plate": "XYZ789",
                "make": "Honda",
                "model": "Civic",
                "year": 2019,
                "passengers": 5
            },
            {   
                "id": 3,
                "license_plate": "DEF456",
                "make": "Ford",
                "model": "Focus",
                "year": 2021,
                "passengers": 5
            }
        ]

        for car_data in cars_data:
            car = Car(**car_data)
            db.add(car)
            print(f"Added car: {car_data}")

        db.commit()
        print("Committed cars to database.")
        print("Seeded database with 3 cars.")

    except Exception as e:
        db.rollback()
        print(f"Error seeding database: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    seed_database()