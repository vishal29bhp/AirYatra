"""
Database Optimization - MongoDB Indexes
Performance indexes for high-traffic scenarios
"""

import asyncio
import logging

logger = logging.getLogger(__name__)

# Index definitions for all collections
INDEXES = {
    "users": [
        {"keys": [("email", 1)], "unique": True, "name": "email_unique"},
        {"keys": [("roles", 1)], "name": "roles_idx"},
        {"keys": [("is_active", 1)], "name": "active_idx"},
        {"keys": [("created_at", -1)], "name": "created_at_idx"},
    ],
    "bookings": [
        {"keys": [("booking_number", 1)], "unique": True, "name": "booking_number_unique"},
        {"keys": [("customer_id", 1)], "name": "customer_idx"},
        {"keys": [("operator_id", 1)], "name": "operator_idx"},
        {"keys": [("status", 1)], "name": "status_idx"},
        {"keys": [("travel_date", 1)], "name": "travel_date_idx"},
        {"keys": [("created_at", -1)], "name": "created_at_idx"},
        {"keys": [("status", 1), ("created_at", -1)], "name": "status_created_compound"},
    ],
    "inquiries": [
        {"keys": [("inquiry_number", 1)], "unique": True, "name": "inquiry_number_unique"},
        {"keys": [("customer_id", 1)], "name": "customer_idx"},
        {"keys": [("status", 1)], "name": "status_idx"},
        {"keys": [("created_at", -1)], "name": "created_at_idx"},
        {"keys": [("status", 1), ("created_at", -1)], "name": "status_created_compound"},
    ],
    "quotes": [
        {"keys": [("inquiry_id", 1)], "name": "inquiry_idx"},
        {"keys": [("operator_id", 1)], "name": "operator_idx"},
        {"keys": [("status", 1)], "name": "status_idx"},
        {"keys": [("created_at", -1)], "name": "created_at_idx"},
    ],
    "operators": [
        {"keys": [("user_id", 1)], "unique": True, "name": "user_id_unique"},
        {"keys": [("status", 1)], "name": "status_idx"},
        {"keys": [("base_city", 1)], "name": "base_city_idx"},
        {"keys": [("rating", -1)], "name": "rating_idx"},
    ],
    "notifications": [
        {"keys": [("user_id", 1)], "name": "user_idx"},
        {"keys": [("is_read", 1)], "name": "read_idx"},
        {"keys": [("created_at", -1)], "name": "created_at_idx"},
        {"keys": [("user_id", 1), ("is_read", 1), ("created_at", -1)], "name": "user_unread_compound"},
    ],
    "crm_leads": [
        {"keys": [("status", 1)], "name": "status_idx"},
        {"keys": [("source", 1)], "name": "source_idx"},
        {"keys": [("assigned_to", 1)], "name": "assigned_idx"},
        {"keys": [("created_at", -1)], "name": "created_at_idx"},
        {"keys": [("priority", 1), ("created_at", -1)], "name": "priority_created_compound"},
    ],
    "call_logs": [
        {"keys": [("call_sid", 1)], "unique": True, "name": "call_sid_unique"},
        {"keys": [("customer_id", 1)], "name": "customer_idx"},
        {"keys": [("created_at", -1)], "name": "created_at_idx"},
    ],
    "support_tickets": [
        {"keys": [("ticket_number", 1)], "unique": True, "name": "ticket_number_unique"},
        {"keys": [("customer_id", 1)], "name": "customer_idx"},
        {"keys": [("status", 1)], "name": "status_idx"},
        {"keys": [("priority", 1)], "name": "priority_idx"},
        {"keys": [("assigned_to", 1)], "name": "assigned_idx"},
        {"keys": [("created_at", -1)], "name": "created_at_idx"},
    ],
    "audit_logs": [
        {"keys": [("user_id", 1)], "name": "user_idx"},
        {"keys": [("action", 1)], "name": "action_idx"},
        {"keys": [("created_at", -1)], "name": "created_at_idx"},
    ],
    "sessions": [
        {"keys": [("user_id", 1)], "name": "user_idx"},
        {"keys": [("expires_at", 1)], "expireAfterSeconds": 0, "name": "ttl_idx"},
    ],
    "landing_points": [
        {"keys": [("city", 1)], "name": "city_idx"},
        {"keys": [("state", 1)], "name": "state_idx"},
        {"keys": [("is_active", 1)], "name": "active_idx"},
        {"keys": [("location", "2dsphere")], "name": "geo_idx"},
    ],
    "fleet": [
        {"keys": [("operator_id", 1)], "name": "operator_idx"},
        {"keys": [("aircraft_type", 1)], "name": "type_idx"},
        {"keys": [("is_available", 1)], "name": "available_idx"},
    ],
    "payments": [
        {"keys": [("booking_id", 1)], "name": "booking_idx"},
        {"keys": [("status", 1)], "name": "status_idx"},
        {"keys": [("created_at", -1)], "name": "created_at_idx"},
    ],
}


def needs_review(index_def) -> str:
    """Why an index must not be created automatically, or '' if it is safe.

    Creating an index must never change data or make a write fail that works today:
    TTL indexes delete documents, unique indexes reject inserts (including several documents
    without the field), and geo/text indexes reject documents whose field is malformed.
    """
    if "expireAfterSeconds" in index_def:
        return "TTL index deletes documents"
    if index_def.get("unique"):
        return "unique index can reject inserts"
    if any(not isinstance(direction, int) for _, direction in index_def["keys"]):
        return "special index type can reject documents"
    return ""


async def create_indexes(db):
    """Create the plain performance indexes; skip (and report) the ones that need review."""
    created_count = 0
    
    for collection_name, indexes in INDEXES.items():
        collection = db[collection_name]
        
        for index_def in indexes:
            reason = needs_review(index_def)
            if reason:
                logger.info(f"Index {index_def['name']} on {collection_name} skipped: {reason} (needs review)")
                continue
            try:
                keys = index_def["keys"]
                options = {k: v for k, v in index_def.items() if k != "keys"}
                await collection.create_index(keys, **options)
                created_count += 1
                logger.info(f"Created index {index_def.get('name', 'unnamed')} on {collection_name}")
            except Exception as e:
                # Same name with other options already exists, or similar: report it, don't stop.
                logger.warning(f"Index {index_def.get('name', 'unnamed')} on {collection_name} not created: {e}")
    
    return created_count


async def optimize_database(db=None):
    """Run all database optimizations on the application database (DB_NAME).

    Indexes used to be created on a hard-coded ``airyatra`` database, so the database the app
    actually uses (DB_NAME, default ``airyatra_db``) never received them.
    """
    if db is None:
        from database import get_database
        db = get_database()
    
    logger.info("Starting database optimization...")
    
    # Create indexes
    index_count = await create_indexes(db)
    logger.info(f"Index optimization complete. Processed {index_count} indexes.")
    
    # Compact collections (optional, can be run periodically)
    # This helps reclaim space and improve performance
    
    return {"indexes_processed": index_count}


# Run optimization on startup
async def _main():
    from database import close_mongo_connection, connect_to_mongo
    await connect_to_mongo()
    try:
        print(await optimize_database())
    finally:
        await close_mongo_connection()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(_main())
