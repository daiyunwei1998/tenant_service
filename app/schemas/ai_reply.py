# app/schemas/ai_reply.py

from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel

class AIReply(BaseModel):
    receiver: str
    user_query: str
    ai_reply: str
    total_tokens: int  # Ensure this field exists
    customer_feedback: Optional[bool] = None
    tenant_id: str
    created_at: datetime = datetime.now(timezone.utc)

    class Config:
        orm_mode = True
