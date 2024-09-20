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

    @property
    def database_url(self):
        return f"mysql+aiomysql://{self.MYSQL_USER}:{self.MYSQL_PASSWORD}@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DB}"

    class Config:
        env_file = ".env"


# Instantiate the settings object
settings = Settings()