"""
Inventory Service - Manages product inventory and handles payment_successful events
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
from events import InventoryEvents, Topics

# Configure logging
logger.remove()
logger.add(sys.stdout, level="INFO", format="{time} - {name} - {level} - {message}")

# Initialize services
kafka_producer = get_kafka_producer()
db_manager = get_database_manager()

# Global consumer instance
consumer = None
background_loop = None

class InventoryItem(BaseModel):
    product_id: str
    product_name: str
    quantity: int
    reserved_quantity: int
    price: float

class UpdateInventoryRequest(BaseModel):
    product_id: str
    quantity_change: int  # Positive to add, negative to remove

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
            topics=[Topics.PAYMENT_SUCCESSFUL, Topics.PAYMENT_FAILED],
            group_id="inventory-service-group"
        )

        background_loop = asyncio.get_event_loop()
        if not background_loop.is_running():
            raise RuntimeError("Event loop is not running. Ensure the service is started correctly.")
        
        signal.signal(signal.SIGINT, consumer.signal_handler)
        signal.signal(signal.SIGTERM, consumer.signal_handler)
        
        # Register message handlers
        consumer.register_handler(Topics.PAYMENT_SUCCESSFUL, handle_payment_successful)
        consumer.register_handler(Topics.PAYMENT_FAILED, handle_payment_failed)
        
        # Start consumer in background thread
        consumer_thread = threading.Thread(target=consumer.start_consuming, daemon=True)
        consumer_thread.start()
        
        logger.info("Inventory service started successfully")
        
    except Exception as e:
        logger.error(f"Failed to start inventory service: {e}")
        raise

async def shutdown_event():
    """Clean up connections on shutdown"""
    global consumer
    
    if consumer:
        consumer.stop_consuming()
    
    await db_manager.close_connections()
    kafka_producer.close()
    logger.info("Inventory service shut down")

async def lifespan(app: FastAPI):
    """Lifespan event to manage startup and shutdown"""
    await startup_event()
    yield
    await shutdown_event()

app = FastAPI(
    title="Inventory Service",
    description="Microservice for managing product inventory",
    version="1.0.0",
    lifespan=lifespan
)

@app.get("/")
async def root():
    return {"service": "inventory-service", "status": "healthy", "version": "1.0.0"}

@app.get("/health")
async def health_check():
    return {
        "service": "inventory-service",
        "status": "healthy",
        "timestamp": datetime.now().isoformat()
    }

@app.get("/inventory")
async def list_inventory():
    """Get all inventory items"""
    try:
        async with db_manager.get_postgres_connection() as conn:
            rows = await conn.fetch("SELECT * FROM inventory ORDER BY product_name")
            
            inventory = []
            for row in rows:
                inventory.append({
                    "product_id": row['product_id'],
                    "product_name": row['product_name'],
                    "quantity": row['quantity'],
                    "reserved_quantity": row['reserved_quantity'],
                    "available_quantity": row['quantity'] - row['reserved_quantity'],
                    "price": float(row['price']),
                    "updated_at": row['updated_at'].isoformat()
                })
            
            return {"inventory": inventory}
            
    except Exception as e:
        logger.error(f"Failed to list inventory: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve inventory")

@app.get("/inventory/{product_id}")
async def get_inventory_item(product_id: str):
    """Get inventory details for a specific product"""
    try:
        async with db_manager.get_postgres_connection() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM inventory WHERE product_id = $1", product_id
            )
            
            if not row:
                raise HTTPException(status_code=404, detail="Product not found")
            
            return {
                "product_id": row['product_id'],
                "product_name": row['product_name'],
                "quantity": row['quantity'],
                "reserved_quantity": row['reserved_quantity'],
                "available_quantity": row['quantity'] - row['reserved_quantity'],
                "price": float(row['price']),
                "updated_at": row['updated_at'].isoformat()
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get inventory for {product_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve inventory")

@app.post("/inventory/{product_id}/update")
async def update_inventory(product_id: str, request: UpdateInventoryRequest):
    """Manually update inventory quantity"""
    try:
        async with db_manager.get_postgres_connection() as conn:
            # Check if product exists
            row = await conn.fetchrow(
                "SELECT * FROM inventory WHERE product_id = $1", product_id
            )
            
            if not row:
                raise HTTPException(status_code=404, detail="Product not found")
            
            new_quantity = row['quantity'] + request.quantity_change
            
            if new_quantity < 0:
                raise HTTPException(status_code=400, detail="Insufficient inventory")
            
            # Update inventory
            await conn.execute(
                """
                UPDATE inventory 
                SET quantity = $1, updated_at = CURRENT_TIMESTAMP 
                WHERE product_id = $2
                """,
                new_quantity, product_id
            )
            
            logger.info(f"Updated inventory for {product_id}: {row['quantity']} -> {new_quantity}")
            
            return {
                "product_id": product_id,
                "old_quantity": row['quantity'],
                "new_quantity": new_quantity,
                "change": request.quantity_change
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update inventory for {product_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update inventory")

def handle_payment_successful(message):
    """Handle payment_successful events from Kafka"""
    try:
        data = message.get('data', {})
        order_id = data.get('order_id')
        
        if not order_id:
            logger.warning(f"Invalid payment_successful message: {message}")
            return
        
        logger.info(f"Processing inventory update for successful payment, order: {order_id}")
        
        asyncio.run_coroutine_threadsafe(
            process_inventory_update(order_id), 
            background_loop
        )
        
    except Exception as e:
        logger.error(f"Error handling payment_successful event: {e}")

def handle_payment_failed(message):
    """Handle payment_failed events from Kafka"""
    try:
        data = message.get('data', {})
        order_id = data.get('order_id')
        
        if not order_id:
            logger.warning(f"Invalid payment_failed message: {message}")
            return
        
        logger.info(f"Releasing reserved inventory for failed payment, order: {order_id}")
        
        asyncio.run_coroutine_threadsafe(
            release_reserved_inventory(order_id), 
            background_loop
        )
        
    except Exception as e:
        logger.error(f"Error handling payment_failed event: {e}")

async def process_inventory_update(order_id: str):
    """Process inventory update for successful payment"""
    try:
        # Get order details (in real implementation, this would come from order service or cache)
        # For simplicity, we'll simulate updating inventory for a sample product
        
        # Simulate inventory update for a sample order
        sample_items = [
            {"product_id": "LAPTOP001", "quantity": 1},
            {"product_id": "MOUSE001", "quantity": 2}
        ]
        
        updated_items = []
        
        async with db_manager.get_postgres_connection() as conn:
            for item in sample_items:
                product_id = item['product_id']
                quantity = item['quantity']
                
                # Check current inventory
                row = await conn.fetchrow(
                    "SELECT * FROM inventory WHERE product_id = $1", product_id
                )
                
                if row and row['quantity'] >= quantity:
                    # Update inventory
                    new_quantity = row['quantity'] - quantity
                    
                    await conn.execute(
                        """
                        UPDATE inventory 
                        SET quantity = $1, updated_at = CURRENT_TIMESTAMP 
                        WHERE product_id = $2
                        """,
                        new_quantity, product_id
                    )
                    
                    # Record inventory transaction
                    await conn.execute(
                        """
                        INSERT INTO inventory_transactions 
                        (order_id, product_id, quantity, transaction_type)
                        VALUES ($1, $2, $3, $4)
                        """,
                        order_id, product_id, quantity, "fulfill"
                    )
                    
                    updated_items.append({
                        "product_id": product_id,
                        "quantity_updated": quantity,
                        "new_quantity": new_quantity
                    })
                    
                    logger.info(f"Updated inventory for {product_id}: -{quantity} (new total: {new_quantity})")
        
        if updated_items:
            # Publish inventory_updated event
            event = InventoryEvents.inventory_updated(order_id, updated_items)
            kafka_producer.send_message(Topics.INVENTORY_UPDATED, event, key=order_id)
            logger.info(f"Published inventory_updated event for order {order_id}")
        
    except Exception as e:
        logger.error(f"Error processing inventory update for order {order_id}: {e}")

async def release_reserved_inventory(order_id: str):
    """Release reserved inventory for failed payment"""
    try:
        # In a real implementation, you would release previously reserved inventory
        # For this demo, we'll just log the action
        logger.info(f"Released reserved inventory for order {order_id}")
        
        # You could implement inventory reservation logic here
        # This would involve maintaining reserved_quantity in the inventory table
        
    except Exception as e:
        logger.error(f"Error releasing reserved inventory for order {order_id}: {e}")

def run_service():
    """Run the inventory service"""
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info"
    )

if __name__ == "__main__":
    run_service()
