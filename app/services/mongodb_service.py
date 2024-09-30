from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timezone, timedelta, date
from typing import List, Dict
from bson import ObjectId

from app.core.config import settings
from app.schemas.ai_reply import AIReply

class MongoDBService:
    def __init__(self):
        self.client = AsyncIOMotorClient(settings.MONGODB_URL)
        self.db = self.client[settings.DATABASE_NAME]

    async def get_tenant_collection(self, tenant_id: str):
        collection_name = f"{tenant_id}_replies"
        return self.db[collection_name]

    async def save_ai_reply(self, ai_reply: AIReply):
        collection = await self.get_tenant_collection(ai_reply.tenant_id)
        result = await collection.insert_one(ai_reply.model_dump())
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
                    "created_at": {
                        "$gte": start_of_today,
                        "$lt": start_of_tomorrow
                    }
                }
            },
            {
                "$project": {
                    "total_tokens": 1,
                    "document_total_price": {
                        "$reduce": {
                            "input": {
                                "$map": {
                                    "input": {"$objectToArray": "$tokens"},
                                    "as": "token",
                                    "in": {
                                        "$multiply": ["$$token.v.count", "$$token.v.price_per_token"]
                                    }
                                }
                            },
                            "initialValue": 0,
                            "in": {"$add": ["$$value", "$$this"]}
                        }
                    }
                }
            },
            {
                "$group": {
                    "_id": None,
                    "total_tokens_used": {"$sum": "$total_tokens"},
                    "total_price": {"$sum": "$document_total_price"}
                }
            }
        ]

        aggregation_result = await collection.aggregate(pipeline).to_list(length=1)

        if not aggregation_result:
            return 0, 0.0

        data = aggregation_result[0]
        return data.get("total_tokens_used", 0), data.get("total_price", 0.0)

    async def aggregate_monthly_data(self, tenant_id: str, year: int, month: int) -> (int, float):
        """
        Aggregates total tokens and total price for the specified month from MongoDB.

        :param tenant_id: The tenant's unique identifier.
        :param year: The billing year.
        :param month: The billing month.
        :return: A tuple containing total_tokens_used and total_price.
        """
        collection = await self.get_tenant_collection(tenant_id)

        # Define start and end of the month in UTC
        start_date = datetime(year, month, 1, tzinfo=timezone.utc)
        if month == 12:
            end_date = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
        else:
            end_date = datetime(year, month + 1, 1, tzinfo=timezone.utc)

        pipeline = [
            {
                "$match": {
                    "created_at": {
                        "$gte": start_date,
                        "$lt": end_date
                    }
                }
            },
            {
                "$project": {
                    "total_tokens": 1,
                    "document_total_price": {
                        "$reduce": {
                            "input": {
                                "$map": {
                                    "input": {"$objectToArray": "$tokens"},
                                    "as": "token",
                                    "in": {
                                        "$multiply": ["$$token.v.count", "$$token.v.price_per_token"]
                                    }
                                }
                            },
                            "initialValue": 0,
                            "in": {"$add": ["$$value", "$$this"]}
                        }
                    }
                }
            },
            {
                "$group": {
                    "_id": None,
                    "total_tokens_used": {"$sum": "$total_tokens"},
                    "total_price": {"$sum": "$document_total_price"}
                }
            }
        ]

        aggregation_result = await collection.aggregate(pipeline).to_list(length=1)

        if not aggregation_result:
            return 0, 0.0

        data = aggregation_result[0]
        return data.get("total_tokens_used", 0), data.get("total_price", 0.0)

    async def aggregate_multiple_dates(self, tenant_id: str, dates: List[date]) -> Dict[date, Dict[str, float]]:
        """
        Aggregates total tokens and total price for multiple specific dates from MongoDB.

        :param tenant_id: The tenant's unique identifier.
        :param dates: List of dates to aggregate.
        :return: A dictionary with date as key and a dict of tokens_used and total_price.
        """
        if not dates:
            return {}

        collection = await self.get_tenant_collection(tenant_id)

        # Build match conditions for each date
        match_conditions = []
        for d in dates:
            start = datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
            end = start + timedelta(days=1)
            match_conditions.append({
                "created_at": {
                    "$gte": start,
                    "$lt": end
                }
            })

        pipeline = [
            {
                "$match": {
                    "$or": match_conditions
                }
            },
            {
                "$project": {
                    "created_at": 1,
                    "total_tokens": 1,
                    "document_total_price": {
                        "$reduce": {
                            "input": {
                                "$map": {
                                    "input": {"$objectToArray": "$tokens"},
                                    "as": "token",
                                    "in": {
                                        "$multiply": ["$$token.v.count", "$$token.v.price_per_token"]
                                    }
                                }
                            },
                            "initialValue": 0,
                            "in": {"$add": ["$$value", "$$this"]}
                        }
                    }
                }
            },
            {
                "$group": {
                    "_id": {
                        "year": {"$year": "$created_at"},
                        "month": {"$month": "$created_at"},
                        "day": {"$dayOfMonth": "$created_at"}
                    },
                    "total_tokens_used": {"$sum": "$total_tokens"},
                    "total_price": {"$sum": "$document_total_price"}
                }
            }
        ]

        aggregation_result = await collection.aggregate(pipeline).to_list(length=None)

        # Transform aggregation result into a dictionary
        mongo_data: Dict[date, Dict[str, float]] = {}
        for record in aggregation_result:
            year = record["_id"]["year"]
            month = record["_id"]["month"]
            day = record["_id"]["day"]
            # Create date object
            d = date(year, month, day)
            mongo_data[d] = {
                "tokens_used": record.get("total_tokens_used", 0),
                "total_price": record.get("total_price", 0.0)
            }

        return mongo_data

    async def get_data_for_date_range(self, tenant_id: str, start_date: datetime, end_date: datetime):
        collection = await self.get_tenant_collection(tenant_id)
        cursor = collection.find({
            "created_at": {
                "$gte": start_date,
                "$lt": end_date
            }
        }, {
            "created_at": 1,
            "total_tokens": 1,
            "tokens": 1  # Include tokens field to access price information
        })
        records = await cursor.to_list(length=None)
        return records

    async def close_connection(self):
        self.client.close()

mongodb_service = MongoDBService()
