import uuid
from app.db.redis import get_redis
from app.config import get_settings

settings = get_settings()


async def get_or_create_work_item_id(component_id: str) -> tuple[bool, str]:
    """
    Redis-backed debouncer.

    Logic:
    - First signal for a component_id in a 10s window -> create new Work Item
    - Signals 2-N in the same window -> link to existing Work Item
    - After window expires -> next signal starts a fresh Work Item

    Returns:
        (should_create: bool, work_item_id: str)
        should_create=True  means caller must INSERT a new Work Item in Postgres
        should_create=False means caller just links signal to existing Work Item
    """
    redis = get_redis()

    debounce_key  = f"debounce:{component_id}"
    ref_key       = f"work_item_ref:{component_id}"
    window        = settings.DEBOUNCE_WINDOW_SECONDS

    # Atomically increment the counter for this component in this window
    count = await redis.incr(debounce_key)

    if count == 1:
        # First signal in this window — start the TTL clock
        await redis.expire(debounce_key, window)

        # Generate a new Work Item ID and store the reference
        work_item_id = str(uuid.uuid4())
        # Store ref slightly longer than window so late signals still link correctly
        await redis.set(ref_key, work_item_id, ex=window + 10)

        return True, work_item_id
    else:
        # Subsequent signal — fetch the existing Work Item ID
        work_item_id = await redis.get(ref_key)

        if work_item_id is None:
            # Edge case: ref expired before debounce key — create fresh
            work_item_id = str(uuid.uuid4())
            await redis.set(ref_key, work_item_id, ex=window + 10)
            await redis.expire(debounce_key, window)
            return True, work_item_id

        return False, work_item_id


async def increment_signal_count(component_id: str) -> int:
    """Returns current signal count for a component in the active window."""
    redis = get_redis()
    count = await redis.get(f"debounce:{component_id}")
    return int(count) if count else 0