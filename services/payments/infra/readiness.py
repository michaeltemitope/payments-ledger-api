from redis import Redis
from redis.exceptions import RedisError
from sqlalchemy import Engine, text
from sqlalchemy.exc import SQLAlchemyError


def dependencies_reachable(engine: Engine, redis_client: Redis) -> bool:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        redis_client.ping()
    except (SQLAlchemyError, RedisError):
        return False
    return True
