#!/bin/sh

# Run database seeding
echo "Starting database seeding..."
python -m app.seed

# Start the application
echo "Starting Uvicorn..."
exec uvicorn app.api.main:app --host 0.0.0.0 --port 8000