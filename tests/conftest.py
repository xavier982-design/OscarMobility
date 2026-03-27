import pytest
import sys
import json
from unittest.mock import MagicMock, patch

# Create proper mock objects BEFORE any app imports
kafka_mock = MagicMock()
kafka_mock.KafkaProducer = MagicMock(return_value=MagicMock())
sys.modules['kafka'] = kafka_mock
sys.modules['kafka.errors'] = MagicMock()

# Mock Redis with proper JSON handling
redis_mock = MagicMock()
redis_client = MagicMock()

# Mock Redis get/set to properly handle JSON
def mock_redis_get(key):
    return None  # Return None for cache misses

def mock_redis_set(key, value, ex=None):
    return True

redis_client.get = mock_redis_get
redis_client.set = mock_redis_set
redis_mock.Redis = MagicMock(return_value=redis_client)
sys.modules['redis'] = redis_mock

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base


@pytest.fixture(scope="session")
def engine():
    return create_engine("sqlite:///:memory:")


@pytest.fixture(scope="session")
def tables(engine):
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture
def db_session(engine, tables):
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.rollback()
    session.close()


@pytest.fixture
def mock_kafka_producer(mocker):
    return mocker.patch('kafka.KafkaProducer')


@pytest.fixture
def mock_kafka_consumer(mocker):
    return mocker.patch('kafka.KafkaConsumer')