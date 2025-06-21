"""
Database connection utilities for microservices
"""
import os
import logging
from typing import Optional
import asyncpg
import redis.asyncio as redis
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

class DatabaseManager:
    """Manages database connections for microservices"""
    
    def __init__(self):
        self.pg_pool = None
        self.redis_client = None
        self.database_url = os.getenv('DATABASE_URL', 'postgresql://admin:password123@localhost:5432/microservices_db')
        self.redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
    
    async def connect_postgres(self):
        """Initialize PostgreSQL connection pool"""
        try:
            self.pg_pool = await asyncpg.create_pool(
                self.database_url,
                min_size=1,
                max_size=10,
                command_timeout=60
            )
            logger.info("Connected to PostgreSQL database")
        except Exception as e:
            logger.error(f"Failed to connect to PostgreSQL: {e}")
            raise
    
    async def connect_redis(self):
        """Initialize Redis connection"""
        try:
            self.redis_client = redis.Redis.from_url(self.redis_url)
            await self.redis_client.ping()
            logger.info("Connected to Redis")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise
    
    async def close_connections(self):
        """Close all database connections"""
        if self.pg_pool:
            await self.pg_pool.close()
            logger.info("PostgreSQL connection pool closed")
        
        if self.redis_client:
            await self.redis_client.close()
            logger.info("Redis connection closed")
    
    @asynccontextmanager
    async def get_postgres_connection(self):
        """Get a PostgreSQL connection from the pool"""
        if not self.pg_pool:
            await self.connect_postgres()
        
        conn = await self.pg_pool.acquire()
        try:
            yield conn
        finally:
            await self.pg_pool.release(conn)
    
    def get_redis_client(self):
        """Get Redis client"""
        if not self.redis_client:
            raise Exception("Redis client not initialized. Call connect_redis() first.")
        return self.redis_client

# Singleton instance
_db_manager = None

def get_database_manager() -> DatabaseManager:
    """Get or create a singleton database manager instance"""
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager()
    return _db_manager
