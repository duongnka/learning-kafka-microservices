"""
Order Service - Handles incoming orders and publishes order_created events
"""
import os
import sys
from datetime import datetime
from typing import List, Optional
from uuid import uuid4

import uvicorn
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from loguru import logger

# Add shared modules to path
sys.path.append('/app/shared')

from kafka_producer import get_kafka_producer
from database import get_database_manager
from events import OrderEvents, Topics

# Configure logging
logger.remove()
logger.add(sys.stdout, level="INFO", format="{time} - {name} - {level} - {message}")

app = FastAPI(
    title="Order Service",
    description="Microservice for handling order creation and management",
    version="1.0.0"
)

# Initialize services
kafka_producer = get_kafka_producer()
db_manager = get_database_manager()

# Pydantic models
class OrderItem(BaseModel):
    product_id: str = Field(..., description="Product identifier")
    product_name: str = Field(..., description="Product name")
    quantity: int = Field(..., gt=0, description="Quantity to order")
    price: float = Field(..., gt=0, description="Price per unit")

class CreateOrderRequest(BaseModel):
    user_id: str = Field(..., description="User identifier")
    items: List[OrderItem] = Field(..., min_items=1, description="Items to order")
    
    @property
    def total_amount(self) -> float:
        return sum(item.quantity * item.price for item in self.items)

class OrderResponse(BaseModel):
    order_id: str
    user_id: str
    items: List[OrderItem]
    total_amount: float
    status: str
    created_at: datetime

@app.on_event("startup")
async def startup_event():
    """Initialize connections on startup"""
    try:
        await db_manager.connect_postgres()
        await db_manager.connect_redis()
        kafka_producer.connect()
        logger.info("Order service started successfully")
    except Exception as e:
        logger.error(f"Failed to start order service: {e}")
        raise

@app.on_event("shutdown")
async def shutdown_event():
    """Clean up connections on shutdown"""
    await db_manager.close_connections()
    kafka_producer.close()
    logger.info("Order service shut down")

@app.get("/")
async def root():
    return {"service": "order-service", "status": "healthy", "version": "1.0.0"}

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "service": "order-service",
        "status": "healthy",
        "timestamp": datetime.now().isoformat()
    }

@app.post("/orders", response_model=OrderResponse)
async def create_order(order_request: CreateOrderRequest, background_tasks: BackgroundTasks):
    """
    Create a new order and publish order_created event
    """
    order_id = str(uuid4())
    
    try:
        # Store order in database
        async with db_manager.get_postgres_connection() as conn:
            await conn.execute(
                """
                INSERT INTO orders (id, user_id, amount, status, created_at)
                VALUES ($1, $2, $3, $4, $5)
                """,
                order_id, order_request.user_id, order_request.total_amount, 
                "pending", datetime.now()
            )
        
        # Cache order details in Redis for quick access
        redis_client = db_manager.get_redis_client()
        order_data = {
            "order_id": order_id,
            "user_id": order_request.user_id,
            "items": [item.dict() for item in order_request.items],
            "total_amount": order_request.total_amount,
            "status": "pending",
            "created_at": datetime.now().isoformat()
        }
        await redis_client.setex(f"order:{order_id}", 3600, str(order_data))
        
        # Publish order_created event to Kafka
        background_tasks.add_task(
            publish_order_created_event,
            order_id, order_request.user_id, order_request.total_amount,
            [item.dict() for item in order_request.items]
        )
        
        logger.info(f"Order {order_id} created for user {order_request.user_id}")
        
        return OrderResponse(
            order_id=order_id,
            user_id=order_request.user_id,
            items=order_request.items,
            total_amount=order_request.total_amount,
            status="pending",
            created_at=datetime.now()
        )
        
    except Exception as e:
        logger.error(f"Failed to create order: {e}")
        raise HTTPException(status_code=500, detail="Failed to create order")

@app.get("/orders/{order_id}", response_model=OrderResponse)
async def get_order(order_id: str):
    """
    Get order details by ID
    """
    try:
        # Try to get from Redis cache first
        redis_client = db_manager.get_redis_client()
        cached_order = await redis_client.get(f"order:{order_id}")
        
        if cached_order:
            order_data = eval(cached_order)  # In production, use proper JSON parsing
            return OrderResponse(**order_data)
        
        # If not in cache, get from database
        async with db_manager.get_postgres_connection() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM orders WHERE id = $1", order_id
            )
            
            if not row:
                raise HTTPException(status_code=404, detail="Order not found")
            
            # For simplicity, return basic order info (in production, you'd join with order_items table)
            return OrderResponse(
                order_id=row['id'],
                user_id=row['user_id'],
                items=[],  # Would need to fetch from order_items table
                total_amount=row['amount'],
                status=row['status'],
                created_at=row['created_at']
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get order {order_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve order")

@app.get("/orders")
async def list_orders(user_id: Optional[str] = None, limit: int = 10, offset: int = 0):
    """
    List orders with optional filtering by user_id
    """
    try:
        async with db_manager.get_postgres_connection() as conn:
            if user_id:
                rows = await conn.fetch(
                    """
                    SELECT * FROM orders 
                    WHERE user_id = $1 
                    ORDER BY created_at DESC 
                    LIMIT $2 OFFSET $3
                    """,
                    user_id, limit, offset
                )
            else:
                rows = await conn.fetch(
                    """
                    SELECT * FROM orders 
                    ORDER BY created_at DESC 
                    LIMIT $1 OFFSET $2
                    """,
                    limit, offset
                )
            
            orders = []
            for row in rows:
                orders.append({
                    "order_id": row['id'],
                    "user_id": row['user_id'],
                    "amount": float(row['amount']),
                    "status": row['status'],
                    "created_at": row['created_at'].isoformat()
                })
            
            return {"orders": orders, "count": len(orders)}
            
    except Exception as e:
        logger.error(f"Failed to list orders: {e}")
        raise HTTPException(status_code=500, detail="Failed to list orders")

async def publish_order_created_event(order_id: str, user_id: str, amount: float, items: list):
    """
    Publish order_created event to Kafka
    """
    try:
        event = OrderEvents.order_created(order_id, user_id, amount, items)
        success = kafka_producer.send_message(Topics.ORDER_CREATED, event, key=order_id)
        
        if success:
            logger.info(f"Published order_created event for order {order_id}")
        else:
            logger.error(f"Failed to publish order_created event for order {order_id}")
            
    except Exception as e:
        logger.error(f"Error publishing order_created event: {e}")

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
