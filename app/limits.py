import redis.asyncio as redis
from limits.aio.strategies import MovingWindowRateLimiter, RateLimiter
from limits.storage import storage_from_string

from app.config import settings


def init_limits(host, password, port) -> RateLimiter:
    redis_client = storage_from_string(f"async+{host}://default:{password}@{host}:{port}")
    return MovingWindowRateLimiter(redis_client)


def init_redis(host, password, port):
    return redis.Redis(host=host, port=port, password=password)


rate_limiter = init_limits(settings.redis_host, settings.redis_password.get_secret_value(), settings.redis_port)
redis_client = init_redis(settings.redis_host, settings.redis_password.get_secret_value(), settings.redis_port)
