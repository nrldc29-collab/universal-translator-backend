# SQLite to PostgreSQL Migration Guide

## Overview

This document outlines the migration path from SQLite to PostgreSQL for NAIA's data storage requirements.

## Current SQLite Usage

NAIA currently uses SQLite for:
- `memory/naia_memory.sqlite3` - Memory storage
- `runtime/events.sqlite3` - Event logging
- `governance/*.sqlite3` - Governance data (approvals, decisions)

## Migration Benefits

1. **Better Concurrency**: PostgreSQL handles concurrent access much better than SQLite
2. **Horizontal Scaling**: Required for multi-instance deployments
3. **Advanced Features**: Full-text search, JSON indexing, advanced constraints
4. **Better Performance**: For large datasets and complex queries
5. **Replication**: Built-in support for high availability

## Prerequisites

- PostgreSQL 15 or later
- Python `psycopg2-binary` package
- Database access credentials

## Migration Steps

### 1. Add PostgreSQL Dependencies

Update `requirements.txt`:

```txt
psycopg2-binary==2.9.9
```

### 2. Create PostgreSQL Database

```sql
CREATE DATABASE naia;
CREATE USER naia_user WITH PASSWORD 'secure_password';
GRANT ALL PRIVILEGES ON DATABASE naia TO naia_user;
```

### 3. Update Database Connection Code

Create a new database abstraction layer that supports both SQLite and PostgreSQL:

```python
# runtime/database.py
import os
from typing import Any
import sqlite3
import psycopg2
from psycopg2 import pool

class DatabaseConnection:
    def __init__(self, db_type: str = "sqlite"):
        self.db_type = db_type
        self.connection_pool = None
        
        if db_type == "postgres":
            self.connection_pool = psycopg2.pool.SimpleConnectionPool(
                minconn=1,
                maxconn=10,
                host=os.getenv("POSTGRES_HOST", "localhost"),
                database=os.getenv("POSTGRES_DB", "naia"),
                user=os.getenv("POSTGRES_USER", "naia_user"),
                password=os.getenv("POSTGRES_PASSWORD"),
            )
    
    def get_connection(self):
        if self.db_type == "postgres":
            return self.connection_pool.getconn()
        else:
            return sqlite3.connect("memory/naia_memory.sqlite3")
    
    def release_connection(self, conn):
        if self.db_type == "postgres":
            self.connection_pool.putconn(conn)
        else:
            conn.close()
```

### 4. Schema Migration

#### Memory Store Schema

```sql
-- PostgreSQL schema for memory store
CREATE TABLE memory_records (
    memory_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id VARCHAR(255) NOT NULL,
    user_id VARCHAR(255),
    content TEXT NOT NULL,
    memory_type VARCHAR(50) NOT NULL,
    confidence FLOAT,
    importance FLOAT,
    status VARCHAR(50) DEFAULT 'active',
    vector VECTOR(768),  -- Requires pgvector extension
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_accessed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    metadata JSONB
);

CREATE INDEX idx_tenant_id ON memory_records(tenant_id);
CREATE INDEX idx_memory_type ON memory_records(memory_type);
CREATE INDEX idx_created_at ON memory_records(created_at);
```

#### Event Log Schema

```sql
CREATE TABLE events (
    event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type VARCHAR(100) NOT NULL,
    module VARCHAR(255),
    session_id VARCHAR(255),
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    state_snapshot JSONB,
    details JSONB
);

CREATE INDEX idx_session_id ON events(session_id);
CREATE INDEX idx_event_type ON events(event_type);
CREATE INDEX idx_timestamp ON events(timestamp);
```

### 5. Data Migration Script

```python
# scripts/migrate_to_postgres.py
import sqlite3
import psycopg2
from datetime import datetime
import json

def migrate_sqlite_to_postgres(sqlite_path, postgres_conn_params):
    """Migrate data from SQLite to PostgreSQL."""
    
    # Connect to SQLite
    sqlite_conn = sqlite3.connect(sqlite_path)
    sqlite_cursor = sqlite_conn.cursor()
    
    # Connect to PostgreSQL
    postgres_conn = psycopg2.connect(**postgres_conn_params)
    postgres_cursor = postgres_conn.cursor()
    
    # Migrate memory records
    sqlite_cursor.execute("SELECT * FROM memory_records")
    for row in sqlite_cursor.fetchall():
        postgres_cursor.execute(
            """INSERT INTO memory_records 
               (memory_id, content, memory_type, confidence, importance, status, created_at, metadata)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
            (row[0], row[3], row[4], row[5], row[6], row[7], row[9], row[11])
        )
    
    postgres_conn.commit()
    postgres_conn.close()
    sqlite_conn.close()
```

### 6. Update Configuration

Add environment variables:

```bash
POSTGRES_HOST=localhost
POSTGRES_DB=naia
POSTGRES_USER=naia_user
POSTGRES_PASSWORD=secure_password
DB_TYPE=postgres
```

### 7. Update Docker Compose

```yaml
services:
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: naia
      POSTGRES_USER: naia_user
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U naia_user"]
      interval: 10s
      timeout: 5s
      retries: 5

  naia:
    depends_on:
      postgres:
        condition: service_healthy
    environment:
      - DB_TYPE=postgres
      - POSTGRES_HOST=postgres
      - POSTGRES_DB=naia
      - POSTGRES_USER=naia_user
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
```

## Rollback Plan

If migration fails:

1. Keep SQLite databases as backup
2. Switch back to SQLite by setting `DB_TYPE=sqlite`
3. Verify data integrity in SQLite backup

## Performance Considerations

- Use connection pooling for PostgreSQL
- Enable query caching
- Add appropriate indexes based on query patterns
- Consider read replicas for read-heavy workloads

## Testing

1. Run integration tests with PostgreSQL
2. Verify all CRUD operations work correctly
3. Test concurrent access patterns
4. Validate data integrity after migration

## Current Status

- [ ] Add PostgreSQL dependencies to requirements.txt
- [ ] Create database abstraction layer
- [ ] Define PostgreSQL schemas
- [ ] Implement migration script
- [ ] Update configuration
- [ ] Update Docker Compose
- [ ] Test migration
- [ ] Update documentation

## Notes

- Migration should be done during maintenance window
- Back up SQLite databases before migration
- Test migration in staging environment first
- Monitor performance after migration
