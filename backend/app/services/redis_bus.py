import json
import asyncio
from typing import Optional, Callable, Dict, Any
import redis
import redis.asyncio as aioredis

from backend.app.schemas.alert import Alert
from backend.app.core.config import settings
from backend.app.core.logging import logger


class RedisEventBus:
    """
    Redis Pub/Sub transport for broadcasting real-time security alerts.
    Supports both async and synchronous publishing with graceful offline fallback.
    """

    def __init__(
        self,
        redis_url: Optional[str] = None,
        channel: Optional[str] = None
    ):
        self.redis_url = redis_url or settings.REDIS_URL
        self.channel = channel or settings.REDIS_ALERT_CHANNEL
        self._async_client: Optional[aioredis.Redis] = None
        self._sync_client: Optional[redis.Redis] = None
        self._last_sync_fail: float = 0.0
        self._last_async_fail: float = 0.0

    def _get_sync_client(self) -> Optional[redis.Redis]:
        import time
        if (time.time() - self._last_sync_fail) < 10.0:
            return None

        if self._sync_client is None:
            try:
                self._sync_client = redis.from_url(
                    self.redis_url,
                    socket_connect_timeout=0.5,
                    decode_responses=True
                )
            except Exception as e:
                self._last_sync_fail = time.time()
                logger.warning("Redis sync client connection failed (%s): %s", self.redis_url, e)
                return None
        return self._sync_client

    async def _get_async_client(self) -> Optional[aioredis.Redis]:
        import time
        if (time.time() - self._last_async_fail) < 10.0:
            return None

        if self._async_client is None:
            try:
                self._async_client = aioredis.from_url(
                    self.redis_url,
                    socket_connect_timeout=0.5,
                    decode_responses=True
                )
            except Exception as e:
                self._last_async_fail = time.time()
                logger.warning("Redis async client connection failed (%s): %s", self.redis_url, e)
                return None
        return self._async_client

    def publish_alert_sync(self, alert: Alert) -> bool:
        """
        Synchronously publishes an alert as a JSON message to Redis Pub/Sub.
        Fails gracefully without raising if Redis is offline.
        """
        try:
            client = self._get_sync_client()
            if client is None:
                return False
            payload = json.dumps(alert.to_dict())
            client.publish(self.channel, payload)
            return True
        except Exception as e:
            logger.debug("Redis sync publish unavailable (running in local mode): %s", e)
            return False

    async def publish_alert_async(self, alert: Alert) -> bool:
        """
        Asynchronously publishes an alert as a JSON message to Redis Pub/Sub.
        Fails gracefully without raising if Redis is offline.
        """
        try:
            client = await self._get_async_client()
            if client is None:
                return False
            payload = json.dumps(alert.to_dict())
            await client.publish(self.channel, payload)
            return True
        except Exception as e:
            logger.debug("Redis async publish unavailable (running in local mode): %s", e)
            return False

    async def subscribe_alerts(
        self,
        callback: Callable[[Alert], Any],
        stop_event: Optional[asyncio.Event] = None
    ) -> None:
        """
        Subscribes to the alert channel and yields deserialized Alert objects to callback.
        """
        try:
            client = await self._get_async_client()
            if client is None:
                logger.warning("Cannot start Redis alert subscriber: Redis unavailable.")
                return

            pubsub = client.pubsub()
            await pubsub.subscribe(self.channel)
            logger.info("Subscribed to Redis alert channel: '%s'", self.channel)

            while stop_event is None or not stop_event.is_set():
                try:
                    message = await pubsub.get_message(
                        ignore_subscribe_messages=True,
                        timeout=1.0
                    )
                    if message and message.get("type") == "message":
                        data_str = message.get("data")
                        if isinstance(data_str, str):
                            data_dict = json.loads(data_str)
                            alert = Alert.from_dict(data_dict)
                            if asyncio.iscoroutinefunction(callback):
                                await callback(alert)
                            else:
                                callback(alert)
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.warning("Error in Redis subscription message handler: %s", e)
                    await asyncio.sleep(1.0)

            await pubsub.unsubscribe(self.channel)
            await pubsub.close()
        except Exception as e:
            logger.warning("Redis subscription loop terminated: %s", e)

    async def close(self) -> None:
        """Closes async connections."""
        if self._async_client is not None:
            await self._async_client.close()
            self._async_client = None
        if self._sync_client is not None:
            self._sync_client.close()
            self._sync_client = None


# Global singleton instance
redis_event_bus = RedisEventBus()
