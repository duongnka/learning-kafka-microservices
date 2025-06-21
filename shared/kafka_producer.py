"""
Shared Kafka producer functionality for all microservices
"""
import json
import logging
from typing import Dict, Any, Optional
from kafka import KafkaProducer
from kafka.errors import KafkaError
import os

class KafkaMessageProducer:
    def __init__(self, bootstrap_servers: str = None):
        self.bootstrap_servers = bootstrap_servers or os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092')
        self.producer = None
        self.logger = logging.getLogger(__name__)
        
    def connect(self):
        """Initialize Kafka producer connection"""
        try:
            self.producer = KafkaProducer(
                bootstrap_servers=self.bootstrap_servers,
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                key_serializer=lambda k: k.encode('utf-8') if k else None,
                acks='all',  # Wait for all replicas to acknowledge
                retries=3,
                max_in_flight_requests_per_connection=1,
                enable_idempotence=True
            )
            self.logger.info(f"Connected to Kafka at {self.bootstrap_servers}")
        except Exception as e:
            self.logger.error(f"Failed to connect to Kafka: {e}")
            raise
    
    def send_message(self, topic: str, message: Dict[str, Any], key: Optional[str] = None) -> bool:
        """
        Send a message to a Kafka topic
        
        Args:
            topic: Kafka topic name
            message: Message payload as dictionary
            key: Optional message key for partitioning
            
        Returns:
            bool: True if message sent successfully, False otherwise
        """
        if not self.producer:
            self.connect()
            
        try:
            # Add metadata to message
            message['_timestamp'] = message.get('timestamp')
            message['_service'] = message.get('service', 'unknown')
            
            future = self.producer.send(topic, value=message, key=key)
            record_metadata = future.get(timeout=10)
            
            self.logger.info(
                f"Message sent to topic '{topic}' "
                f"partition={record_metadata.partition} "
                f"offset={record_metadata.offset}"
            )
            return True
            
        except KafkaError as e:
            self.logger.error(f"Failed to send message to topic '{topic}': {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error sending message: {e}")
            return False
    
    def close(self):
        """Close the producer connection"""
        if self.producer:
            self.producer.close()
            self.logger.info("Kafka producer connection closed")

# Singleton instance
_producer_instance = None

def get_kafka_producer() -> KafkaMessageProducer:
    """Get or create a singleton Kafka producer instance"""
    global _producer_instance
    if _producer_instance is None:
        _producer_instance = KafkaMessageProducer()
    return _producer_instance
