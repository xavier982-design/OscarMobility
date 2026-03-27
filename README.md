# OscarMobility Booking & Payment System

This project is a Python-based booking and payment management system built with FastAPI, SQLAlchemy, Kafka and Redis. It features robust data integrity through row-level locking, idempotency patterns, and event-driven architecture.

### Prerequisites
- Python 3.11 or higher

## Setup Instructions

1. Clone the repo locally
2. Run ```docker-compose up``` (you will see some errors in the log output, this is normal. It's the Kafka consumers trying to connect to the Kafka broker before the broker is ready. This will eventually quiet down once connection is established).
3. Go to http://localhost:8000/docs to see the OpenAPI docs, where you can interact with the endpoints.

## Running the tests

The tests are set up to run in their own docker container. All other services are mocked so the only service running is the api.

1. Run ```docker build -f Dockerfile.test -t oscar-tests . ``` to build the container
2. Run ```docker run --rm oscar-tests``` to run the tests.

## Key Design Decisions

### 1. Row-Level Database Locking (`SELECT ... FOR UPDATE`)
- Used SQLAlchemy's `with_for_update()` for critical paths in booking and payment operations. This prevents race conditions across multiple processes/servers. In-memory locks (threading.Lock) only work within a single process, but DB-level locks coordinate access across the entire system.


### 2. Idempotency with Double-Checked Locking Pattern
- Implemented idempotency keys with a two-phase check: early return if key exists, then re-check inside the lock. This makes the API resilient to client-side retries without creating duplicate bookings/payments.

### 3. Separate `Refund` Model
Created a dedicated `Refund` table linked to `Payment` and `Booking`, rather than adding refund fields to the `Payment` model. This keeps concerns separated and provides a cleaner schema.

### 4. Event-Driven Architecture with Kafka
Publish events (BookingCreated, PaymentCompleted, etc.) to Kafka topics after successful operations.



## Tradeoffs Considered

### 1. In-Memory vs. Distributed Locking
I chose in-memory locks (threading.Lock) combined with DB row locks over Redis-based distributed locks. This is a simpler implementation, but it doesn't scale for multi-server setups. The DB row lock, for example, only works if all business operations are kept within one DB shard, which may not be the case.


### 3. Single Database vs. Microservices
I kept everything in one service with shared database, which could be broken up into microservices with their own database if this were to scale up. Some obvious microservices would be "Booking", "Payment", "Refund", maybe even "Currency Exchange".


## Production Environment Changes

### 1. Infrastructure & Deployment
- **Database**: Use PostgreSQL with connection pooling (SQLAlchemy's pool_pre_ping). Implement database migrations with Alembic.
- **Kafka/Redis**: Deploy managed instances (AWS MSK, ElastiCache) with proper security (TLS, authentication).
- **Application**: Containerize with Docker, deploy on Kubernetes with horizontal scaling. Use Gunicorn/Uvicorn workers.

### 2. Security & Configuration
- **Secrets Management**: Use environment variables or tools like AWS Secrets Manager for API keys, DB credentials.
- **Authentication**: Add JWT/OAuth for API endpoints. Implement rate limiting and input validation.
- **Monitoring**: Add structured logging (structlog), metrics (Prometheus), and tracing (OpenTelemetry).

### 3. Testing & CI/CD
- **Testing**: Add integration tests with a real Kafka/Redis, end-to-end tests with Selenium or Playwright.
- **CI/CD**: GitHub Actions for automated testing, linting (black, flake8), and deployment.

## Assumptions Made

1. **Single Database Instance**: Assumed one database for simplicity; production might need sharding or read replicas.
2. **Kafka Availability**: Assumed Kafka brokers are always available; in reality, need retry logic and fallback mechanisms, implement a Dead Letter Queue.
3. **Currency Conversion**: Assumed exchange rates are cached and refreshed periodically; no real-time API integration.
4. **Full Refunds Only**: Implemented full refunds; partial refunds or complex refund rules not handled.

