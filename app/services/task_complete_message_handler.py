import asyncio
import json
import logging

from aio_pika import IncomingMessage, connect_robust
from fastapi import HTTPException

from app.core.config import settings
from app.dependencies import get_db
from app.routers.tenant_doc import create_tenant_doc
from app.schemas.tenant_doc_schema import TenantDocCreateSchema
from app.services.tenant_doc_service import TenantDocService

# config
rabbitmq_username = settings.RABBITMQ_USERNAME
rabbitmq_host = settings.RABBITMQ_HOST
rabbitmq_password = settings.RABBITMQ_PASSWORD


async def process_message(message: IncomingMessage):
    async with message.process():
        try:
            # Decode the message body
            message_body = message.body.decode()
            message_data = json.loads(message_body)

            # Log the received message
            logging.info(f"Received message: {message_data}")

            # Extract data from the message
            tenant_id = message_data.get("tenantId")
            file_name = message_data.get("file")
            status = message_data.get("status")
            number_of_entries = message_data.get("number_of_entries")
            error = message_data.get("error")  # May not exist if status is success

            if status == "success":
                # Obtain an AsyncSession using an async context manager
                async with get_db() as db:
                    tenant_doc_data = TenantDocCreateSchema(
                        tenant_id=tenant_id,
                        doc_name=file_name,
                        num_entries=number_of_entries
                    )
                    try:
                        # Call create_tenant_doc with the session
                        await TenantDocService.create_tenant_doc(tenant_doc_data, db)
                        logging.info(f"Tenant document created in database for tenant '{tenant_id}' and doc '{file_name}'.")
                    except HTTPException as he:
                        if he.status_code == 400:
                            logging.warning(f"TenantDoc with tenant_id '{tenant_id}' and doc_name '{file_name}' already exists.")
                        else:
                            logging.error(f"Failed to create TenantDoc: {he.detail}")
            else:
                logging.error(f"Message indicates failure: {error}")

        except Exception as e:
            logging.error(f"Failed to process message: {e}")
            # Optionally, reject or requeue the message
            # await message.reject(requeue=True)


async def start_message_handler():
    # Create a connection
    connection = await connect_robust(
        f"amqp://{rabbitmq_username}:{rabbitmq_password}@{rabbitmq_host}/",
        loop=asyncio.get_event_loop(),
    )

    # Creating a channel
    channel = await connection.channel()

    # Declare the queue
    queue_name = 'chunking_complete_notification_queue'
    queue = await channel.declare_queue(queue_name, durable=True)

    # Start consuming messages
    await queue.consume(process_message)

