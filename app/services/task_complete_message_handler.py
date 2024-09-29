import asyncio
import json
import logging

from aio_pika import IncomingMessage, connect_robust

from app.core.config import settings
from app.dependencies import get_db
from app.routers.tenant_doc import create_tenant_doc
from app.schemas.tenant_doc_schema import TenantDocCreateSchema

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
            msg_text = message_data.get("message")
            error = message_data.get("error")  # May not exist if status is success

            if status == "success":
                # Obtain an AsyncSession
                async for db in get_db():
                    tenant_doc_data = TenantDocCreateSchema(
                        tenant_id=tenant_id,
                        doc_name=file_name,
                        num_entries=number_of_entries
                    )
                    # Call create_tenant_doc with the session
                    await create_tenant_doc(tenant_doc=tenant_doc_data, db=db)
                logging.info(f"Tenant document created in database for tenant '{tenant_id}'.")
            else:
                logging.error(error)

            # Acknowledge the message manually if not using `message.process()`
            # await message.ack()

        except Exception as e:
            logging.error(f"Failed to process message: {e}")
            # Optionally reject or requeue the message
            # await message.reject()


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

