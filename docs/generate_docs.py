"""
System Architecture Visualization Generator
Creates a simple diagram of the microservices architecture
"""

import json
from datetime import datetime

def generate_architecture_diagram():
    """Generate a text-based architecture diagram"""
    
    diagram = """
🏗️  KAFKA MICROSERVICES ARCHITECTURE
=========================================

┌─────────────────┐    HTTP POST     ┌─────────────────┐
│     CLIENT      │ ────────────────▶│  ORDER SERVICE  │
│   (Web/Mobile)  │                  │   Port: 8001    │
└─────────────────┘                  └─────────┬───────┘
                                               │
                                               │ Publishes
                                               ▼
                              ┌─────────────────────────────┐
                              │    KAFKA - order_created    │
                              └─────────────┬───────────────┘
                                            │
                                            │ Consumes
                                            ▼
┌─────────────────┐                  ┌─────────────────┐
│ NOTIFICATION    │◀─────────────────│ PAYMENT SERVICE │
│    SERVICE      │  Publishes       │   Port: 8002    │
│   Port: 8004    │  Events          └─────────┬───────┘
└─────────────────┘                            │
         ▲                                     │ Publishes
         │                                     ▼
         │               ┌─────────────────────────────────┐
         │               │  KAFKA - payment_successful     │
         │               └─────────────┬───────────────────┘
         │                             │
         │                             │ Consumes  
         │                             ▼
         │                  ┌─────────────────┐
         └──────────────────│ INVENTORY       │
           Publishes        │   SERVICE       │
           Events           │   Port: 8003    │
                            └─────────────────┘

SUPPORTING INFRASTRUCTURE:
==========================

┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  ┌────────────────────┐
│   POSTGRESQL    │  │      REDIS      │  │   KAFKA UI      │  │    ZOOKEEPER       │
│   Port: 5432    │  │   Port: 6379    │  │   Port: 8080    │  │   Port: 2181       │
│  (Persistence)  │  │   (Caching)     │  │  (Monitoring)   │  │ (Kafka Metadata)   │
└─────────────────┘  └─────────────────┘  └─────────────────┘  └────────────────────┘

┌─────────────────────────────────────────┐
│          KAFKA WITH ZOOKEEPER           │
│      (Zookeeper Required)               │
│        Port: 9092, 29092                │
│    • Reliable event streaming           │
│    • Distributed coordination           │
│    • Proven architecture                │
└─────────────────────────────────────────┘

EVENT FLOW:
===========
1. order_created     → Payment Service
2. payment_successful → Inventory Service  
3. payment_failed    → Notification Service
4. inventory_updated → Notification Service
5. notification_sent → System Complete

KAFKA TOPICS:
=============
• order_created
• payment_successful  
• payment_failed
• inventory_updated
• notification_sent
"""
    
    return diagram

def generate_system_stats():
    """Generate system statistics template"""
    
    stats = {
        "system_info": {
            "name": "Kafka Microservices Order Processing",
            "version": "1.0.0",
            "created": datetime.now().isoformat(),
            "architecture": "Event-Driven Microservices"
        },
        "services": {
            "order_service": {
                "port": 8001,
                "purpose": "Order creation and management",
                "events_published": ["order_created", "order_cancelled"],
                "events_consumed": []
            },
            "payment_service": {
                "port": 8002, 
                "purpose": "Payment processing",
                "events_published": ["payment_successful", "payment_failed"],
                "events_consumed": ["order_created"]
            },
            "inventory_service": {
                "port": 8003,
                "purpose": "Stock management", 
                "events_published": ["inventory_updated", "inventory_insufficient"],
                "events_consumed": ["payment_successful", "payment_failed"]
            },
            "notification_service": {
                "port": 8004,
                "purpose": "Customer notifications",
                "events_published": ["notification_sent"],
                "events_consumed": ["order_created", "payment_successful", "payment_failed", "inventory_updated"]
            }
        },
        "infrastructure": {
            "kafka": {
                "purpose": "Event streaming platform",
                "port": 9092,
                "ui_port": 8080
            },
            "zookeeper": {
                "purpose": "Kafka metadata management",
                "port": 2181
            },
            "postgresql": {
                "purpose": "Primary database",
                "port": 5432,
                "database": "microservices_db"
            },
            "redis": {
                "purpose": "Caching layer", 
                "port": 6379
            }
        },
        "event_flow": [
            "Client creates order",
            "Order service publishes order_created",
            "Payment service processes payment",
            "Payment service publishes payment_successful/failed",
            "Inventory service updates stock (if payment successful)",
            "Inventory service publishes inventory_updated", 
            "Notification service sends confirmations at each step"
        ]
    }
    
    return stats

if __name__ == "__main__":
    print("Generating system documentation...")
    
    # Generate architecture diagram
    diagram = generate_architecture_diagram()
    with open("architecture_diagram.txt", "w") as f:
        f.write(diagram)
    
    # Generate system stats
    stats = generate_system_stats()
    with open("system_stats.json", "w") as f:
        json.dump(stats, f, indent=2)
    
    print("✅ Documentation generated:")
    print("   - architecture_diagram.txt")
    print("   - system_stats.json")
    
    print("\n" + diagram)
