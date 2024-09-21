import os
from typing import ClassVar

from pydantic_settings import BaseSettings


class Settings(BaseSettings):

    image_host: ClassVar[str] = "https://flash-response-cloud.s3.ap-northeast-3.amazonaws.com/"
    s3_bucket_name: ClassVar[str] = "flash-response-cloud"

    # MySQL Configuration (Loaded from .env file)
    MYSQL_USER: str
    MYSQL_PASSWORD: str
    MYSQL_HOST: str
    MYSQL_PORT: int
    MYSQL_DB: str

    # knowledge base
    OPENAI_API_KEY:str =  os.getenv('OPEN_AI_KEY')
    MILVUS_HOST:str = os.getenv('MILVUS_HOST')
    MILVUS_PORT:str = os.getenv('MILVUS_PORT')

    # RabbitMQ Configuration
    RABBITMQ_HOST: str = os.getenv('RABBITMQ_HOST')
    RABBITMQ_USERNAME: str = os.getenv('RABBITMQ_USERNAME')
    RABBITMQ_PASSWORD: str = os.getenv('RABBITMQ_PASSWORD')

    # Redis Configuration
    redis_host: str = os.getenv("REDIS_HOST")
    redis_password: str = os.getenv("REDIS_PASSWORD")

    # embedding model
    embedding_model: str = "text-embedding-3-small"

    @property
    def database_url(self):
        return f"mysql+aiomysql://{self.MYSQL_USER}:{self.MYSQL_PASSWORD}@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DB}"

    class Config:
        env_file = ".env"


# Instantiate the settings object
settings = Settings()