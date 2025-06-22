"""
Notification Service - Sends notifications for order processing events
"""
import os
import signal
import sys
import asyncio
import threading
from datetime import datetime
from uuid import uuid4

import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from loguru import logger

# Add shared modules to path
sys.path.append('/app/shared')

from kafka_producer import get_kafka_producer
from kafka_consumer import create_consumer
from database import get_database_manager
from events import NotificationEvents, Topics

# Configure logging
logger.remove()
logger.add(sys.stdout, level="INFO", format="{time} - {name} - {level} - {message}")

# Initialize services
kafka_producer = get_kafka_producer()
db_manager = get_database_manager()
background_loop = None

# Global consumer instance
consumer = None

class NotificationRequest(BaseModel):
    user_id: str
    notification_type: str
    message: str

class NotificationResponse(BaseModel):
    notification_id: str
    user_id: str
    notification_type: str
    message: str
    status: str
    created_at: datetime

# @app.on_event("startup")
async def startup_event():
    """Initialize connections and start Kafka consumer"""
    global consumer
    global background_loop
    
    try:
        await db_manager.connect_postgres()
        await db_manager.connect_redis()
        kafka_producer.connect()
        
        # Create and configure Kafka consumer
        consumer = create_consumer(
            topics=[
                Topics.ORDER_CREATED,
                Topics.PAYMENT_SUCCESSFUL,
                Topics.PAYMENT_FAILED,
                Topics.INVENTORY_UPDATED
            ],
            group_id="notification-service-group"
        )

        background_loop = asyncio.get_running_loop()
        if not background_loop:
            raise RuntimeError("No running event loop found. Ensure this is called within an async context.")

        signal.signal(signal.SIGINT, consumer.signal_handler)
        signal.signal(signal.SIGTERM, consumer.signal_handler)
        
        # Register message handlers
        consumer.register_handler(Topics.ORDER_CREATED, handle_order_created)
        consumer.register_handler(Topics.PAYMENT_SUCCESSFUL, handle_payment_successful)
        consumer.register_handler(Topics.PAYMENT_FAILED, handle_payment_failed)
        consumer.register_handler(Topics.INVENTORY_UPDATED, handle_inventory_updated)
        
        # Start consumer in background thread
        consumer_thread = threading.Thread(target=consumer.start_consuming, daemon=True)
        consumer_thread.start()
        
        logger.info("Notification service started successfully")
        
    except Exception as e:
        logger.error(f"Failed to start notification service: {e}")
        raise

# @app.on_event("shutdown")
async def shutdown_event():
    """Clean up connections on shutdown"""
    global consumer
    
    if consumer:
        consumer.stop_consuming()
    
    await db_manager.close_connections()
    kafka_producer.close()
    logger.info("Notification service shut down")

async def lifespan(app: FastAPI):
    """Lifespan event to manage startup and shutdown"""
    await startup_event()
    yield
    await shutdown_event()

app = FastAPI(
    title="Notification Service",
    description="Microservice for sending order notifications",
    version="1.0.0",
    lifespan=lifespan
)

@app.get("/")
async def root():
    return {"service": "notification-service", "status": "healthy", "version": "1.0.0"}

@app.get("/health")
async def health_check():
    return {
        "service": "notification-service",
        "status": "healthy",
        "timestamp": datetime.now().isoformat()
    }

@app.post("/notifications", response_model=NotificationResponse)
async def send_notification(notification_request: NotificationRequest):
    """Send a manual notification (for testing)"""
    notification_id = str(uuid4())
    
    try:
        # Simulate sending notification
        success = await send_notification_message(
            notification_request.user_id,
            notification_request.notification_type,
            notification_request.message
        )
        
        status = "sent" if success else "failed"
        
        # Store notification in database
        async with db_manager.get_postgres_connection() as conn:
            await conn.execute(
                """
                INSERT INTO notifications 
                (id, order_id, user_id, notification_type, message, status, sent_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                """,
                notification_id, None, notification_request.user_id,
                notification_request.notification_type, notification_request.message,
                status, datetime.now() if success else None
            )
        
        return NotificationResponse(
            notification_id=notification_id,
            user_id=notification_request.user_id,
            notification_type=notification_request.notification_type,
            message=notification_request.message,
            status=status,
            created_at=datetime.now()
        )
        
    except Exception as e:
        logger.error(f"Failed to send notification: {e}")
        raise HTTPException(status_code=500, detail="Failed to send notification")

@app.get("/notifications")
async def list_notifications(user_id: str = None, limit: int = 10, offset: int = 0):
    """List notifications with optional filtering by user_id"""
    try:
        async with db_manager.get_postgres_connection() as conn:
            if user_id:
                rows = await conn.fetch(
                    """
                    SELECT * FROM notifications 
                    WHERE user_id = $1 
                    ORDER BY created_at DESC 
                    LIMIT $2 OFFSET $3
                    """,
                    user_id, limit, offset
                )
            else:
                rows = await conn.fetch(
                    """
                    SELECT * FROM notifications 
                    ORDER BY created_at DESC 
                    LIMIT $1 OFFSET $2
                    """,
                    limit, offset
                )
            
            notifications = []
            for row in rows:
                notifications.append({
                    "notification_id": row['id'],
                    "order_id": row['order_id'],
                    "user_id": row['user_id'],
                    "notification_type": row['notification_type'],
                    "message": row['message'],
                    "status": row['status'],
                    "sent_at": row['sent_at'].isoformat() if row['sent_at'] else None,
                    "created_at": row['created_at'].isoformat()
                })
            
            return {"notifications": notifications, "count": len(notifications)}
            
    except Exception as e:
        logger.error(f"Failed to list notifications: {e}")
        raise HTTPException(status_code=500, detail="Failed to list notifications")

def handle_order_created(message):
    """Handle order_created events"""
    try:
        data = message.get('data', {})
        order_id = data.get('order_id')
        user_id = data.get('user_id')
        amount = data.get('amount')
        
        if not all([order_id, user_id, amount]):
            logger.warning(f"Invalid order_created message: {message}")
            return
        
        notification_message = f"Your order #{order_id} for ${amount:.2f} has been received and is being processed."
        
        asyncio.run_coroutine_threadsafe(
            send_order_notification(order_id, user_id, "order_created", notification_message), 
            background_loop
        )
        
    except Exception as e:
        logger.error(f"Error handling order_created event: {e}")

def handle_payment_successful(message):
    """Handle payment_successful events"""
    try:
        data = message.get('data', {})
        order_id = data.get('order_id')
        amount = data.get('amount')
        
        if not all([order_id, amount]):
            logger.warning(f"Invalid payment_successful message: {message}")
            return
        
        # Get user_id from order (in production, you'd query this from order service)
        user_id = "user_1"  # Placeholder
        
        notification_message = f"Payment of ${amount:.2f} for order #{order_id} has been processed successfully."
        
        asyncio.run_coroutine_threadsafe(
            send_order_notification(order_id, user_id, "payment_successful", notification_message), 
            background_loop
        )

    except Exception as e:
        logger.error(f"Error handling payment_successful event: {e}")

def handle_payment_failed(message):
    """Handle payment_failed events"""
    try:
        data = message.get('data', {})
        order_id = data.get('order_id')
        amount = data.get('amount')
        reason = data.get('reason', 'Unknown error')
        
        if not all([order_id, amount]):
            logger.warning(f"Invalid payment_failed message: {message}")
            return
        
        # Get user_id from order (in production, you'd query this from order service)
        user_id = "user_1"  # Placeholder
        
        notification_message = f"Payment of ${amount:.2f} for order #{order_id} failed: {reason}. Please update your payment method."
        
        asyncio.run_coroutine_threadsafe(
            send_order_notification(order_id, user_id, "payment_failed", notification_message), 
            background_loop
        )

    except Exception as e:
        logger.error(f"Error handling payment_failed event: {e}")

def handle_inventory_updated(message):
    """Handle inventory_updated events"""
    try:
        data = message.get('data', {})
        order_id = data.get('order_id')
        items = data.get('items', [])
        
        if not order_id:
            logger.warning(f"Invalid inventory_updated message: {message}")
            return
        
        # Get user_id from order (in production, you'd query this from order service)
        user_id = "user_1"  # Placeholder
        
        notification_message = f"Your order #{order_id} has been fulfilled and will be shipped soon. Thank you for your purchase!"
        
        asyncio.run_coroutine_threadsafe(
            send_order_notification(order_id, user_id, "order_fulfilled", notification_message), 
            background_loop
        )
        
    except Exception as e:
        logger.error(f"Error handling inventory_updated event: {e}")

async def send_order_notification(order_id: str, user_id: str, notification_type: str, message: str):
    """Send notification for order-related events"""
    try:
        notification_id = str(uuid4())
        
        # Simulate sending notification (email, SMS, push notification)
        success = await send_notification_message(user_id, notification_type, message)
        
        status = "sent" if success else "failed"
        
        # Store notification in database
        async with db_manager.get_postgres_connection() as conn:
            await conn.execute(
                """
                INSERT INTO notifications 
                (id, order_id, user_id, notification_type, message, status, sent_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                """,
                notification_id, order_id, user_id, notification_type, message,
                status, datetime.now() if success else None
            )
        
        if success:
            # Publish notification_sent event
            event = NotificationEvents.notification_sent(order_id, user_id, notification_type, message)
            kafka_producer.send_message(Topics.NOTIFICATION_SENT, event, key=order_id)
            
            logger.info(f"Sent {notification_type} notification for order {order_id} to user {user_id}")
        else:
            logger.error(f"Failed to send {notification_type} notification for order {order_id}")
            
    except Exception as e:
        logger.error(f"Error sending notification for order {order_id}: {e}")

async def send_notification_message(user_id: str, notification_type: str, message: str) -> bool:
    """
    Simulate sending notification message via email, SMS, or push notification
    
    Args:
        user_id: User identifier
        notification_type: Type of notification
        message: Notification message
        
    Returns:
        bool: True if notification sent successfully, False otherwise
    """
    try:
        # Simulate notification sending delay
        await asyncio.sleep(1)
        
        # Simulate different notification channels
        if notification_type == "order_created":
            logger.info(f"📧 EMAIL to {user_id}: {message}")
        elif notification_type == "payment_successful":
            logger.info(f"📱 SMS to {user_id}: {message}")
        elif notification_type == "payment_failed":
            logger.info(f"🚨 ALERT to {user_id}: {message}")
        elif notification_type == "order_fulfilled":
            logger.info(f"🎉 PUSH to {user_id}: {message}")
        else:
            logger.info(f"📢 NOTIFICATION to {user_id}: {message}")
        
        # Simulate 95% success rate
        import random
        return random.random() > 0.05
        
    except Exception as e:
        logger.error(f"Error sending notification message: {e}")
        return False

def run_service():
    """Run the notification service"""
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info"
    )

if __name__ == "__main__":
    run_service()
