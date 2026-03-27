import pytest
from unittest.mock import MagicMock, patch


def test_kafka_producer_send_booking_event():
    with patch('app.kafka.producer.KafkaProducer') as mock_producer_class:
        mock_producer = MagicMock()
        mock_producer_class.return_value = mock_producer
        
        from app.kafka.producer import send_booking_event
        send_booking_event(booking_id=1, car_id=2, guest_name="Test")
        
        # Verify producer was instantiated and send was called
        mock_producer_class.assert_called_once()
        mock_producer.send.assert_called_once()


def test_kafka_producer_send_failure():
    with patch('app.kafka.producer.KafkaProducer') as mock_producer_class:
        mock_producer = MagicMock()
        mock_producer.send.side_effect = Exception("Kafka error")
        mock_producer_class.return_value = mock_producer
        
        from app.kafka.producer import send_booking_event
        with pytest.raises(Exception, match="Kafka error"):
            send_booking_event(booking_id=1, car_id=2, guest_name="Test")