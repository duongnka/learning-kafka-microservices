# 🚀 Kafka Microservices - Order Processing System

A comprehensive microservices architecture demonstrating event-driven communication using Apache Kafka for order processing.

## 🎯 Project Overview

This project implements a complete order processing system with four microservices that communicate asynchronously through Kafka:

- **Order Service**: Handles incoming orders and publishes `order_created` events
- **Payment Service**: Processes payments and publishes `payment_successful/failed` events  
- **Inventory Service**: Manages stock levels and publishes `inventory_updated` events
- **Notification Service**: Sends order confirmations and status updates

## 🏗️ Architecture

```
[Client API Call]
     ↓
[order-service] → emits → [order_created]
     ↓
[Kafka Topic: order_created]
     ↓
[payment-service] → emits → [payment_successful]
     ↓
[Kafka Topic: payment_successful]  
     ↓
[inventory-service] → emits → [inventory_updated]
     ↓
[notification-service] → sends email/SMS
```

## 🔧 Tech Stack

- **Apache Kafka with Zookeeper**: Event streaming platform with proven metadata management (Zookeeper required)
- **Python FastAPI**: Lightweight web framework for microservices
- **PostgreSQL**: Primary database for persistent data
- **Redis**: Caching layer for improved performance
- **Docker + Docker Compose**: Containerized deployment
- **Kafka UI**: Web interface for monitoring Kafka topics

## 📁 Project Structure

```
kafka-microservices/
│
├── docker-compose.yml          # Main orchestration file
├── init-db.sql                 # Database initialization
├── start-system.sh            # System startup script
├── test-system.sh             # End-to-end testing script
│
├── services/
│   ├── order-service/         # Order management service
│   ├── payment-service/       # Payment processing service  
│   ├── inventory-service/     # Stock management service
│   └── notification-service/  # Notification delivery service
│
└── shared/                    # Common utilities
    ├── kafka_producer.py      # Kafka message publisher
    ├── kafka_consumer.py      # Kafka message consumer
    ├── database.py            # Database connections
    └── events.py              # Event schemas
```

## ✨ Zookeeper Benefits

This system uses **Zookeeper** for Kafka metadata management:

- **🔒 Proven Reliability**: Zookeeper is a mature, production-grade coordination service
- **🗂️ Distributed Coordination**: Ensures consistent metadata and leader election
- **🛠️ Compatibility**: Supported by all major Kafka distributions
- **🏗️ Standard Operations**: Well-documented and widely adopted in the Kafka ecosystem

## 🚀 Quick Start

### Prerequisites
- Docker and Docker Compose installed
- `curl` and `jq` for testing (optional)

### 1. Start the System
```bash
# Make scripts executable
chmod +x start-system.sh test-system.sh

# Start all services
./start-system.sh
```

### 2. Verify Services
The system exposes the following endpoints:
- **Kafka UI**: http://localhost:8080
- **Order Service**: http://localhost:8001
- **Payment Service**: http://localhost:8002  
- **Inventory Service**: http://localhost:8003
- **Notification Service**: http://localhost:8004

### 3. Test the Flow
```bash
# Run end-to-end tests
./test-system.sh
```

## 📊 API Examples

### Create an Order
```bash
curl -X POST http://localhost:8001/orders \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user_123",
    "items": [
      {
        "product_id": "LAPTOP001",
        "product_name": "Gaming Laptop", 
        "quantity": 1,
        "price": 1299.99
      }
    ]
  }'
```

### Check Inventory
```bash
curl http://localhost:8003/inventory
```

### View Notifications
```bash
curl "http://localhost:8004/notifications?user_id=user_123"
```

## 🔄 Event Flow

1. **Order Created**: Client creates order → `order_created` event published
2. **Payment Processing**: Payment service consumes event → processes payment → publishes `payment_successful/failed`
3. **Inventory Update**: Inventory service consumes payment success → updates stock → publishes `inventory_updated`
4. **Notifications**: Notification service sends confirmations at each step

## 📈 Monitoring & Debugging

### View Kafka Topics
Access Kafka UI at http://localhost:8080 to:
- Monitor topic messages
- View consumer group status
- Inspect message schemas

### Check Service Logs
```bash
# View all logs
docker-compose logs -f

# View specific service logs
docker-compose logs -f order-service
docker-compose logs -f payment-service
```

### Database Access
```bash
# Connect to PostgreSQL
docker exec -it postgres psql -U admin -d microservices_db

# Common queries
SELECT * FROM orders ORDER BY created_at DESC LIMIT 10;
SELECT * FROM payments ORDER BY created_at DESC LIMIT 10;
SELECT * FROM inventory;
SELECT * FROM notifications ORDER BY created_at DESC LIMIT 10;
```

## 🛠️ Development

### Running Individual Services
```bash
# Start dependencies (Kafka, PostgreSQL, Redis)
docker-compose up kafka postgres redis -d

# Run service locally
cd services/order-service
pip install -r requirements.txt
python main.py
```

### Adding New Events
1. Define event schema in `shared/events.py`
2. Add topic constant in `Topics` class
3. Update producer/consumer services
4. Add database migrations if needed

## 🎯 Key Features Demonstrated

- **Event-Driven Architecture**: Loose coupling between services
- **Async Communication**: Non-blocking message processing
- **Event Sourcing**: Complete audit trail of order processing
- **Fault Tolerance**: Graceful handling of service failures
- **Scalability**: Horizontal scaling through Kafka partitioning
- **Monitoring**: Comprehensive logging and health checks

## 🔧 Configuration

### Environment Variables
Each service supports these environment variables:
- `KAFKA_BOOTSTRAP_SERVERS`: Kafka broker connection
- `DATABASE_URL`: PostgreSQL connection string
- `REDIS_URL`: Redis connection string

### Kafka Topics
- `order_created`: New order events
- `payment_successful`: Successful payment events
- `payment_failed`: Failed payment events  
- `inventory_updated`: Stock update events
- `notification_sent`: Notification delivery events

## 🚨 Error Handling

The system implements several error handling patterns:
- **Retry Logic**: Automatic retries for transient failures
- **Dead Letter Queues**: Failed messages for manual review
- **Circuit Breakers**: Prevent cascade failures
- **Graceful Degradation**: Fallback mechanisms

## 📚 Learning Outcomes

This project demonstrates:
- Microservices architecture design
- Kafka producer/consumer patterns
- Event-driven system design
- Docker containerization
- Database integration
- API design with FastAPI
- Monitoring and observability

## 🛑 Stopping the System

```bash
# Stop all services
docker-compose down

# Remove volumes (reset data)
docker-compose down -v
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Submit a pull request with clear description

## 📜 License

This project is for educational purposes and demonstrates best practices in microservices architecture.
