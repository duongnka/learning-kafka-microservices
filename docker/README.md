# Docker Compose Structure

This directory contains Docker Compose files organized in a modular structure for better maintainability.

## Directory Structure

```
docker/
├── docker-compose.base.yml       # Base configuration with networks and volumes
├── kafka/
│   └── docker-compose.kafka.yml  # Kafka and Kafka UI services
├── database/
│   └── docker-compose.database.yml # PostgreSQL and Redis
└── services/
    ├── docker-compose.order-service.yml
    ├── docker-compose.payment-service.yml
    ├── docker-compose.inventory-service.yml
    └── docker-compose.notification-service.yml
```

## Usage

The main `docker-compose.yml` in the root directory includes all the compose files using the `include` directive (requires Docker Compose v2).

### Start all services:
```bash
docker-compose up -d
```

### Start only infrastructure (Kafka and databases):
```bash
docker-compose up -d kafka kafka-init kafka-ui postgres redis
```

### Start a specific service:
```bash
docker-compose up -d order-service
```
Note: This will automatically start its dependencies (Kafka, databases).

### Stop all services:
```bash
docker-compose down
```

### Clean volumes:
```bash
docker-compose down -v
```

## Service Dependencies

- All services depend on Kafka, PostgreSQL, and Redis
- Kafka depends on kafka-init to set up correct volume permissions

## Troubleshooting

### Permission issues with Kafka logs
If you encounter permission issues with Kafka logs, the kafka-init service should handle it by setting proper permissions. If issues persist, you may need to:

1. Stop the services:
   ```bash
   docker-compose down -v
   ```

2. Restart all services:
   ```bash
   docker-compose up -d
   ```
