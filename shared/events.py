"""
Common event schemas and utilities for the microservices
"""
from datetime import datetime
from typing import Dict, Any, Optional
from uuid import uuid4
import json

class EventSchema:
    """Base class for event schemas"""
    
    @staticmethod
    def create_base_event(event_type: str, service: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a base event structure with metadata"""
        return {
            "event_id": str(uuid4()),
            "event_type": event_type,
            "service": service,
            "timestamp": datetime.now().isoformat(),
            "data": data
        }

class OrderEvents:
    """Order service event schemas"""
    
    @staticmethod
    def order_created(order_id: str, user_id: str, amount: float, items: list = None) -> Dict[str, Any]:
        return EventSchema.create_base_event(
            event_type="order_created",
            service="order-service",
            data={
                "order_id": order_id,
                "user_id": user_id,
                "amount": amount,
                "items": items or [],
                "status": "pending"
            }
        )
    
    @staticmethod
    def order_cancelled(order_id: str, reason: str) -> Dict[str, Any]:
        return EventSchema.create_base_event(
            event_type="order_cancelled",
            service="order-service",
            data={
                "order_id": order_id,
                "reason": reason
            }
        )

class PaymentEvents:
    """Payment service event schemas"""
    
    @staticmethod
    def payment_successful(order_id: str, payment_id: str, amount: float, payment_method: str) -> Dict[str, Any]:
        return EventSchema.create_base_event(
            event_type="payment_successful",
            service="payment-service",
            data={
                "order_id": order_id,
                "payment_id": payment_id,
                "amount": amount,
                "payment_method": payment_method,
                "transaction_id": str(uuid4())
            }
        )
    
    @staticmethod
    def payment_failed(order_id: str, amount: float, reason: str) -> Dict[str, Any]:
        return EventSchema.create_base_event(
            event_type="payment_failed",
            service="payment-service",
            data={
                "order_id": order_id,
                "amount": amount,
                "reason": reason
            }
        )

class InventoryEvents:
    """Inventory service event schemas"""
    
    @staticmethod
    def inventory_reserved(order_id: str, items: list) -> Dict[str, Any]:
        return EventSchema.create_base_event(
            event_type="inventory_reserved",
            service="inventory-service",
            data={
                "order_id": order_id,
                "items": items
            }
        )
    
    @staticmethod
    def inventory_updated(order_id: str, items: list) -> Dict[str, Any]:
        return EventSchema.create_base_event(
            event_type="inventory_updated",
            service="inventory-service",
            data={
                "order_id": order_id,
                "items": items
            }
        )
    
    @staticmethod
    def inventory_insufficient(order_id: str, items: list) -> Dict[str, Any]:
        return EventSchema.create_base_event(
            event_type="inventory_insufficient",
            service="inventory-service",
            data={
                "order_id": order_id,
                "items": items
            }
        )

class NotificationEvents:
    """Notification service event schemas"""
    
    @staticmethod
    def notification_sent(order_id: str, user_id: str, notification_type: str, message: str) -> Dict[str, Any]:
        return EventSchema.create_base_event(
            event_type="notification_sent",
            service="notification-service",
            data={
                "order_id": order_id,
                "user_id": user_id,
                "notification_type": notification_type,
                "message": message
            }
        )

# Kafka Topics Configuration
class Topics:
    ORDER_CREATED = "order_created"
    ORDER_CANCELLED = "order_cancelled"
    PAYMENT_SUCCESSFUL = "payment_successful"
    PAYMENT_FAILED = "payment_failed"
    INVENTORY_RESERVED = "inventory_reserved"
    INVENTORY_UPDATED = "inventory_updated"
    INVENTORY_INSUFFICIENT = "inventory_insufficient"
    NOTIFICATION_SENT = "notification_sent"
    
    @classmethod
    def get_all_topics(cls) -> list:
        """Get all topic names"""
        return [
            cls.ORDER_CREATED,
            cls.ORDER_CANCELLED,
            cls.PAYMENT_SUCCESSFUL,
            cls.PAYMENT_FAILED,
            cls.INVENTORY_RESERVED,
            cls.INVENTORY_UPDATED,
            cls.INVENTORY_INSUFFICIENT,
            cls.NOTIFICATION_SENT
        ]
