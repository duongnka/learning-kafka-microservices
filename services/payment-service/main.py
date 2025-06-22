"""
Payment Service - Consumes order_created events and processes payments
"""
import os
import signal
import sys
import asyncio
import threading
from datetime import datetime
from uuid import uuid4
import random

import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from loguru import logger

# Add shared modules to path
sys.path.append('/app/shared')

from kafka_producer import get_kafka_producer
from kafka_consumer import create_consumer
from database import get_database_manager
from events import PaymentEvents, Topics

# Configure logging
logger.remove()
logger.add(sys.stdout, level="INFO", format="{time} - {name} - {level} - {message}")

app = FastAPI(
    title="Payment Service",
    description="Microservice for processing payments",
    version="1.0.0"
)

# Initialize services
kafka_producer = get_kafka_producer()
db_manager = get_database_manager()

# Global consumer instance
consumer = None
# Add a global event loop for background tasks
background_loop = None

class PaymentRequest(BaseModel):
    order_id: str
    amount: float
    payment_method: str = "credit_card"

class PaymentResponse(BaseModel):
    payment_id: str
    order_id: str
    amount: float
    status: str
    transaction_id: str
    created_at: datetime

@app.on_event("startup")
async def startup_event():
    """Initialize connections and start Kafka consumer"""
    global consumer
    global background_loop
    try:
        await db_manager.connect_postgres()
        await db_manager.connect_redis()
        kafka_producer.connect()

        # Set the background event loop to the current running loop
        background_loop = asyncio.get_running_loop()
        if not background_loop:
            raise RuntimeError("No running event loop found. Ensure this is called within an async context.")
        
        # Create and configure Kafka consumer
        consumer = create_consumer(
            topics=[Topics.ORDER_CREATED],
            group_id="payment-service-group"
        )
        # Set up signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, consumer.signal_handler)
        signal.signal(signal.SIGTERM, consumer.signal_handler)

        # Register message handler
        consumer.register_handler(Topics.ORDER_CREATED, handle_order_created)

        consumer_thread = threading.Thread(target=consumer.start_consuming, daemon=True)
        consumer_thread.start()

        logger.info("Payment service started successfully")

    except Exception as e:
        logger.error(f"Failed to start payment service: {e}")
        raise

@app.on_event("shutdown")
async def shutdown_event():
    """Clean up connections on shutdown"""
    global consumer
    
    if consumer:
        consumer.stop_consuming()
    
    await db_manager.close_connections()
    kafka_producer.close()
    logger.info("Payment service shut down")

@app.get("/")
async def root():
    return {"service": "payment-service", "status": "healthy", "version": "1.0.0"}

@app.get("/health")
async def health_check():
    return {
        "service": "payment-service", 
        "status": "healthy",
        "timestamp": datetime.now().isoformat()
    }

@app.post("/payments", response_model=PaymentResponse)
async def create_payment(payment_request: PaymentRequest):
    """
    Manual payment endpoint (for testing)
    """
    payment_id = str(uuid4())
    
    try:
        # Simulate payment processing
        success = await process_payment(
            payment_request.order_id,
            payment_request.amount,
            payment_request.payment_method
        )
        
        status = "successful" if success else "failed"
        transaction_id = str(uuid4()) if success else None
        
        # Store payment in database
        async with db_manager.get_postgres_connection() as conn:
            await conn.execute(
                """
                INSERT INTO payments (id, order_id, amount, status, payment_method, transaction_id)
                VALUES ($1, $2, $3, $4, $5, $6)
                """,
                payment_id, payment_request.order_id, payment_request.amount, 
                status, payment_request.payment_method, transaction_id
            )
        
        # Publish payment result event
        if success:
            event = PaymentEvents.payment_successful(
                payment_request.order_id, payment_id, 
                payment_request.amount, payment_request.payment_method
            )
            kafka_producer.send_message(Topics.PAYMENT_SUCCESSFUL, event, key=payment_request.order_id)
        else:
            event = PaymentEvents.payment_failed(
                payment_request.order_id, payment_request.amount, "Payment processing failed"
            )
            kafka_producer.send_message(Topics.PAYMENT_FAILED, event, key=payment_request.order_id)
        
        return PaymentResponse(
            payment_id=payment_id,
            order_id=payment_request.order_id,
            amount=payment_request.amount,
            status=status,
            transaction_id=transaction_id or "",
            created_at=datetime.now()
        )
        
    except Exception as e:
        logger.error(f"Failed to process payment: {e}")
        raise HTTPException(status_code=500, detail="Payment processing failed")

@app.get("/payments/{payment_id}")
async def get_payment(payment_id: str):
    """Get payment details by ID"""
    try:
        async with db_manager.get_postgres_connection() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM payments WHERE id = $1", payment_id
            )
            
            if not row:
                raise HTTPException(status_code=404, detail="Payment not found")
            
            return {
                "payment_id": row['id'],
                "order_id": row['order_id'],
                "amount": float(row['amount']),
                "status": row['status'],
                "payment_method": row['payment_method'],
                "transaction_id": row['transaction_id'],
                "created_at": row['created_at'].isoformat()
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get payment {payment_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve payment")

def handle_order_created(message):
    """
    Handle order_created events from Kafka
    """
    global background_loop
    try:
        data = message.get('data', {})
        order_id = data.get('order_id')
        amount = data.get('amount')

        if not order_id or not amount:
            logger.warning(f"Invalid order_created message: {message}")
            return

        logger.info(f"Processing payment for order {order_id}, amount: ${amount}")

        asyncio.run_coroutine_threadsafe(process_order_payment(order_id, amount), background_loop)

    except Exception as e:
        logger.error(f"Error handling order_created event: {e}")

async def process_order_payment(order_id: str, amount: float):
    """
    Process payment for an order asynchronously
    """
    try:
        payment_id = str(uuid4())
        
        # Simulate payment processing delay
        await asyncio.sleep(2)
        
        # Simulate payment success/failure (90% success rate)
        success = await process_payment(order_id, amount, "credit_card")
        
        status = "successful" if success else "failed"
        transaction_id = str(uuid4()) if success else None
        
        # Store payment result in database
        async with db_manager.get_postgres_connection() as conn:
            await conn.execute(
                """
                INSERT INTO payments (id, order_id, amount, status, payment_method, transaction_id)
                VALUES ($1, $2, $3, $4, $5, $6)
                """,
                payment_id, order_id, amount, status, "credit_card", transaction_id
            )
        
        # Publish payment result event
        if success:
            event = PaymentEvents.payment_successful(
                order_id, payment_id, amount, "credit_card"
            )
            kafka_producer.send_message(Topics.PAYMENT_SUCCESSFUL, event, key=order_id)
            logger.info(f"Payment successful for order {order_id}")
        else:
            event = PaymentEvents.payment_failed(order_id, amount, "Insufficient funds")
            kafka_producer.send_message(Topics.PAYMENT_FAILED, event, key=order_id)
            logger.warning(f"Payment failed for order {order_id}")
            
    except Exception as e:
        logger.error(f"Error processing payment for order {order_id}: {e}")

async def process_payment(order_id: str, amount: float, payment_method: str) -> bool:
    """
    Simulate payment processing
    
    Args:
        order_id: Order identifier
        amount: Payment amount
        payment_method: Payment method
        
    Returns:
        bool: True if payment successful, False otherwise
    """
    # Simulate different payment scenarios
    if amount > 5000:
        # High-value transactions have higher failure rate
        return random.random() > 0.3
    elif amount > 1000:
        # Medium-value transactions
        return random.random() > 0.15
    else:
        # Low-value transactions have high success rate
        return random.random() > 0.05

def run_service():
    """Run the payment service"""
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,  # Disable reload in production
        log_level="info"
    )

if __name__ == "__main__":
    run_service()
