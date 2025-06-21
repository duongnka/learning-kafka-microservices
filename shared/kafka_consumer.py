"""
Shared Kafka consumer functionality for all microservices
"""
import json
import logging
from typing import Dict, Any, Callable, List
from kafka import KafkaConsumer
from kafka.errors import KafkaError
import os
import signal
import sys
import threading

class KafkaMessageConsumer:
    def __init__(self, 
                 topics: List[str],
                 group_id: str,
                 bootstrap_servers: str = None,
                 auto_offset_reset: str = 'latest'):
        self.topics = topics
        self.group_id = group_id
        self.bootstrap_servers = bootstrap_servers or os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092')
        self.auto_offset_reset = auto_offset_reset
        self.consumer = None
        self.logger = logging.getLogger(__name__)
        self.running = False
        self.message_handlers = {}
        
    def connect(self):
        """Initialize Kafka consumer connection"""
        try:
            self.consumer = KafkaConsumer(
                *self.topics,
                bootstrap_servers=self.bootstrap_servers,
                group_id=self.group_id,
                auto_offset_reset=self.auto_offset_reset,
                enable_auto_commit=True,
                auto_commit_interval_ms=1000,
                value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                key_deserializer=lambda k: k.decode('utf-8') if k else None,
                consumer_timeout_ms=1000  # Timeout to allow checking for shutdown
            )
            self.logger.info(f"Connected to Kafka consumer for topics {self.topics} with group {self.group_id}")
        except Exception as e:
            self.logger.error(f"Failed to connect to Kafka consumer: {e}")
            raise
    
    def register_handler(self, topic: str, handler: Callable[[Dict[str, Any]], None]):
        """
        Register a message handler for a specific topic
        
        Args:
            topic: Kafka topic name
            handler: Function to handle messages from this topic
        """
        self.message_handlers[topic] = handler
        self.logger.info(f"Registered handler for topic: {topic}")
    
    def process_message(self, message):
        """Process a single message"""
        try:
            topic = message.topic
            value = message.value
            key = message.key
            
            self.logger.info(f"Received message from topic '{topic}': {value}")
            
            # Call registered handler if available
            if topic in self.message_handlers:
                handler = self.message_handlers[topic]
                handler(value)
            else:
                self.logger.warning(f"No handler registered for topic '{topic}'")
                
        except Exception as e:
            self.logger.error(f"Error processing message: {e}")
            # In a production system, you might want to send failed messages to a dead letter queue
    
    def start_consuming(self):
        """Start consuming messages from Kafka topics"""
        if not self.consumer:
            self.connect()
        
        self.running = True
        self.logger.info("Starting Kafka message consumption...")
        
        # Set up signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        try:
            while self.running:
                try:
                    # Poll for messages with timeout
                    message_batch = self.consumer.poll(timeout_ms=1000)
                    
                    for topic_partition, messages in message_batch.items():
                        for message in messages:
                            if not self.running:
                                break
                            self.process_message(message)
                    
                except Exception as e:
                    self.logger.error(f"Error during message consumption: {e}")
                    if self.running:
                        # Brief pause before retrying
                        threading.Event().wait(5)
                        
        except KeyboardInterrupt:
            self.logger.info("Received interrupt signal")
        finally:
            self.stop_consuming()
    
    def stop_consuming(self):
        """Stop consuming messages and close connection"""
        self.running = False
        if self.consumer:
            self.consumer.close()
            self.logger.info("Kafka consumer connection closed")
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        self.logger.info(f"Received signal {signum}, shutting down gracefully...")
        self.stop_consuming()
        sys.exit(0)

def create_consumer(topics: List[str], group_id: str, **kwargs) -> KafkaMessageConsumer:
    """
    Factory function to create a Kafka consumer
    
    Args:
        topics: List of Kafka topics to subscribe to
        group_id: Consumer group ID
        **kwargs: Additional configuration options
        
    Returns:
        KafkaMessageConsumer instance
    """
    return KafkaMessageConsumer(topics, group_id, **kwargs)
