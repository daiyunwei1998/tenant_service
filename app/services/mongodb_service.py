# app/services/mongodb_service.py

from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timezone, timedelta
from typing import Optional, List
from bson import ObjectId

from app.core.config import settings
from app.schemas.ai_reply import AIReply
from app.schemas.aggregation import MonthlyAggregation


class MongoDBService:
    def __init__(self):
        self.client = AsyncIOMotorClient(settings.MONGODB_URL)
        self.db = self.client[settings.DATABASE_NAME]

    async def get_tenant_collection(self, tenant_id: str):
        collection_name = f"{tenant_id}_replies"
        return self.db[collection_name]

    async def save_ai_reply(self, ai_reply: AIReply):
        collection = await self.get_tenant_collection(ai_reply.tenant_id)
        result = await collection.insert_one(ai_reply.dict())
        return str(result.inserted_id)

    async def update_feedback(self, reply_id: str, tenant_id: str, feedback: bool):
        collection = await self.get_tenant_collection(tenant_id)
        result = await collection.update_one(
            {"_id": ObjectId(reply_id)},
            {"$set": {"customer_feedback": feedback}}
        )
        return result.modified_count > 0

    async def ensure_indexes(self, tenant_ids: List[str]):
        for tenant_id in tenant_ids:
            collection = await self.get_tenant_collection(tenant_id)
            await collection.create_index("created_at")

    async def ensure_index(self, tenant_id: str):
        collection = await self.get_tenant_collection(tenant_id)
        await collection.create_index("created_at")

    async def aggregate_todays_data(self, tenant_id: str) -> (int, float):
        """
        Aggregates today's total tokens and total price from MongoDB.

        :param tenant_id: The tenant's unique identifier.
        :return: A tuple containing total_tokens_used and total_price.
        """
        collection = await self.get_tenant_collection(tenant_id)

        # Define start and end of today in UTC
        now = datetime.now(timezone.utc)
        start_of_today = datetime(year=now.year, month=now.month, day=now.day, tzinfo=timezone.utc)
        start_of_tomorrow = start_of_today + timedelta(days=1)

        pipeline = [
            {
                "$match": {
                    "tenant_id": tenant_id,
                    "created_at": {
                        "$gte": start_of_today,
                        "$lt": start_of_tomorrow
                    }
                }
            },
            {
                "$group": {
                    "_id": None,
                    "total_tokens_used": {"$sum": "$total_tokens"},
                    "total_price": {"$sum": {"$multiply": ["$total_tokens", "$per_token_price"]}}
                }
            }
        ]

        aggregation_result = await collection.aggregate(pipeline).to_list(length=1)

        if not aggregation_result:
            return 0, 0.0

        data = aggregation_result[0]
        return data.get("total_tokens_used", 0), data.get("total_price", 0.0)

    async def close_connection(self):
        self.client.close()


# Instantiate a global MongoDBService
mongodb_service = MongoDBService()
