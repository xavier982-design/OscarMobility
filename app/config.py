import os

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://user:password@postgres/oscar"
)

KAFKA_BROKER = os.getenv(
    "KAFKA_BROKER",
    "kafka:9092"
)
