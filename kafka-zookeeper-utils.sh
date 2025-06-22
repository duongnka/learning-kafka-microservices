#!/bin/bash

# Load environment variables from .env if it exists
if [ -f .env ]; then
    set -a
    source .env
    set +a
fi

# Zookeeper-based Kafka Management Utilities

# Load service ports from environment or use defaults
ORDER_SERVICE_PORT=${ORDER_SERVICE_PORT:-8001}
PAYMENT_SERVICE_PORT=${PAYMENT_SERVICE_PORT:-8002}
INVENTORY_SERVICE_PORT=${INVENTORY_SERVICE_PORT:-8003}
NOTIFICATION_SERVICE_PORT=${NOTIFICATION_SERVICE_PORT:-8004}
KAFKA_PORT=${KAFKA_PORT:-9092}
ZOOKEEPER_PORT=${ZOOKEEPER_PORT:-2181}

echo "🚀 Kafka Zookeeper Management Utilities"
echo "===================================="

case "$1" in
    "cluster-info")
        echo "📊 Kafka Cluster Information:"
        docker exec kafka kafka-cluster cluster-id --bootstrap-server localhost:$KAFKA_PORT
        echo ""
        docker exec kafka kafka-broker-api-versions --bootstrap-server localhost:$KAFKA_PORT
        ;;
        
    "zk-info")
        echo "🔍 Zookeeper Information:"
        docker exec zookeeper zookeeper-shell localhost:$ZOOKEEPER_PORT ls /brokers/ids
        ;;
        
    "zk-reset")
        echo "⚠️  WARNING: This will destroy all Kafka data!"
        read -p "Are you sure you want to reset Zookeeper data? (yes/no): " confirm
        if [ "$confirm" = "yes" ]; then
            echo "🔄 Resetting Zookeeper data..."
            docker-compose stop kafka zookeeper
            docker volume rm kafka-micro-services_kafka_data kafka-micro-services_zookeeper_data kafka-micro-services_zookeeper_log
            docker-compose up -d zookeeper kafka
            echo "✅ Zookeeper data reset complete"
        else
            echo "❌ Reset cancelled"
        fi
        ;;
        
    "topic-list")
        echo "📋 Kafka Topics:"
        docker exec kafka kafka-topics --bootstrap-server localhost:$KAFKA_PORT --list
        ;;
        
    "topic-create")
        if [ -z "$2" ]; then
            echo "❌ Error: Please provide a topic name"
            echo "Usage: $0 topic-create TOPIC_NAME [PARTITIONS] [REPLICATION_FACTOR]"
            exit 1
        fi
        
        TOPIC_NAME=$2
        PARTITIONS=${3:-1}
        REPLICATION=${4:-1}
        
        echo "🔧 Creating topic: $TOPIC_NAME (Partitions: $PARTITIONS, Replication: $REPLICATION)"
        docker exec kafka kafka-topics --create --bootstrap-server localhost:$KAFKA_PORT --topic "$TOPIC_NAME" --partitions "$PARTITIONS" --replication-factor "$REPLICATION"
        ;;
        
    "topic-delete")
        if [ -z "$2" ]; then
            echo "❌ Error: Please provide a topic name"
            echo "Usage: $0 topic-delete TOPIC_NAME"
            exit 1
        fi
        
        TOPIC_NAME=$2
        
        echo "🗑️  Deleting topic: $TOPIC_NAME"
        docker exec kafka kafka-topics --delete --bootstrap-server localhost:$KAFKA_PORT --topic "$TOPIC_NAME"
        ;;
        
    "topic-describe")
        if [ -z "$2" ]; then
            echo "❌ Error: Please provide a topic name"
            echo "Usage: $0 topic-describe TOPIC_NAME"
            exit 1
        fi
        
        TOPIC_NAME=$2
        
        echo "🔍 Describing topic: $TOPIC_NAME"
        docker exec kafka kafka-topics --describe --bootstrap-server localhost:$KAFKA_PORT --topic "$TOPIC_NAME"
        ;;
        
    "consumer-groups")
        echo "👥 Consumer Groups:"
        docker exec kafka kafka-consumer-groups --bootstrap-server localhost:$KAFKA_PORT --list
        ;;
        
    "consumer-group-describe")
        if [ -z "$2" ]; then
            echo "❌ Error: Please provide a consumer group"
            echo "Usage: $0 consumer-group-describe GROUP_ID"
            exit 1
        fi
        
        GROUP_ID=$2
        
        echo "🔍 Describing Consumer Group: $GROUP_ID"
        docker exec kafka kafka-consumer-groups --bootstrap-server localhost:$KAFKA_PORT --describe --group "$GROUP_ID"
        ;;
        
    "produce")
        if [ -z "$2" ]; then
            echo "❌ Error: Please provide a topic name"
            echo "Usage: $0 produce TOPIC_NAME"
            exit 1
        fi
        
        TOPIC_NAME=$2
        
        echo "📤 Starting producer for topic: $TOPIC_NAME"
        echo "Type messages and press Enter. Press Ctrl+C to exit."
        docker exec -it kafka kafka-console-producer --bootstrap-server localhost:$KAFKA_PORT --topic "$TOPIC_NAME"
        ;;
        
    "consume")
        if [ -z "$2" ]; then
            echo "❌ Error: Please provide a topic name"
            echo "Usage: $0 consume TOPIC_NAME [--from-beginning]"
            exit 1
        fi
        
        TOPIC_NAME=$2
        FROM_BEGINNING=""
        
        if [ "$3" = "--from-beginning" ]; then
            FROM_BEGINNING="--from-beginning"
        fi
        
        echo "📥 Starting consumer for topic: $TOPIC_NAME $FROM_BEGINNING"
        echo "Press Ctrl+C to exit."
        docker exec -it kafka kafka-console-consumer --bootstrap-server localhost:$KAFKA_PORT --topic "$TOPIC_NAME" $FROM_BEGINNING
        ;;
        
    *)
        echo "📚 Available Commands:"
        echo "  cluster-info           - Show cluster information"
        echo "  zk-info                - Show Zookeeper information"
        echo "  zk-reset               - Reset Zookeeper data (warning: destroys all data)"
        echo "  topic-list             - List all topics"
        echo "  topic-create           - Create a new topic"
        echo "  topic-delete           - Delete a topic"
        echo "  topic-describe         - Describe a topic"
        echo "  consumer-groups        - List all consumer groups"
        echo "  consumer-group-describe - Describe a consumer group"
        echo "  produce                - Produce messages to a topic"
        echo "  consume                - Consume messages from a topic"
        ;;
esac
