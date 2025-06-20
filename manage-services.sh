#!/bin/bash

# Script to manage Docker Compose services for Kafka Microservices

# Set colors for pretty output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Function to display help
show_help() {
  echo -e "${YELLOW}Kafka Microservices Management Script${NC}"
  echo -e "Usage: $0 [command]"
  echo
  echo "Commands:"
  echo "  start        Start all services"
  echo "  start-infra  Start only infrastructure (Kafka, PostgreSQL, Redis)"
  echo "  start-kafka  Start only Kafka-related services"
  echo "  start-service [service_name]  Start a specific service (order-service, payment-service, etc.)"
  echo "  stop         Stop all services"
  echo "  restart      Restart all services"
  echo "  logs [service]  Show logs for all or specific service"
  echo "  clean        Stop and remove all containers, volumes, and networks"
  echo "  status       Show status of services"
  echo "  help         Show this help message"
}

# Function to start all services
start_all() {
  echo -e "${GREEN}Starting all services...${NC}"
  docker-compose up -d
  echo -e "${GREEN}All services started. Use './manage-services.sh status' to check status.${NC}"
}

# Function to start only infrastructure services
start_infra() {
  echo -e "${GREEN}Starting infrastructure services (Kafka, PostgreSQL, Redis)...${NC}"
  docker-compose up -d kafka kafka-init kafka-ui postgres redis
  echo -e "${GREEN}Infrastructure services started.${NC}"
}

# Function to start only Kafka services
start_kafka() {
  echo -e "${GREEN}Starting Kafka services...${NC}"
  docker-compose up -d kafka kafka-init kafka-ui
  echo -e "${GREEN}Kafka services started.${NC}"
}

# Function to start a specific service
start_service() {
  if [ -z "$1" ]; then
    echo -e "${RED}Error: Service name is required.${NC}"
    echo "Available services: order-service, payment-service, inventory-service, notification-service"
    exit 1
  fi
  
  echo -e "${GREEN}Starting $1 service...${NC}"
  docker-compose up -d $1
  echo -e "${GREEN}Service $1 started.${NC}"
}

# Function to stop all services
stop_all() {
  echo -e "${YELLOW}Stopping all services...${NC}"
  docker-compose down
  echo -e "${GREEN}All services stopped.${NC}"
}

# Function to restart all services
restart_all() {
  echo -e "${YELLOW}Restarting all services...${NC}"
  docker-compose down
  docker-compose up -d
  echo -e "${GREEN}All services restarted.${NC}"
}

# Function to show logs
show_logs() {
  if [ -z "$1" ]; then
    echo -e "${GREEN}Showing logs for all services (press Ctrl+C to exit)...${NC}"
    docker-compose logs -f
  else
    echo -e "${GREEN}Showing logs for $1 (press Ctrl+C to exit)...${NC}"
    docker-compose logs -f $1
  fi
}

# Function to clean everything
clean_all() {
  echo -e "${RED}Stopping all services and removing containers, networks, and volumes...${NC}"
  docker-compose down -v
  echo -e "${GREEN}Cleanup complete.${NC}"
}

# Function to show status
show_status() {
  echo -e "${GREEN}Services status:${NC}"
  docker-compose ps
}

# Main script logic
case "$1" in
  start)
    start_all
    ;;
  start-infra)
    start_infra
    ;;
  start-kafka)
    start_kafka
    ;;
  start-service)
    start_service "$2"
    ;;
  stop)
    stop_all
    ;;
  restart)
    restart_all
    ;;
  logs)
    show_logs "$2"
    ;;
  clean)
    clean_all
    ;;
  status)
    show_status
    ;;
  help|--help|-h)
    show_help
    ;;
  *)
    show_help
    exit 1
    ;;
esac

exit 0
