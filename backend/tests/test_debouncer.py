"""
Tests for debounce logic.
Uses a mock Redis to test without a live connection.
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch


class MockRedis:
    """In-memory mock Redis for debouncer tests."""
    def __init__(self):
        self._store = {}
        self._counters = {}

    async def incr(self, key):
        self._counters[key] = self._counters.get(key, 0) + 1
        return self._counters[key]

    async def expire(self, key, ttl):
        pass

    async def set(self, key, value, ex=None):
        self._store[key] = value

    async def get(self, key):
        return self._store.get(key)

    def reset(self):
        self._store.clear()
        self._counters.clear()


mock_redis = MockRedis()


@pytest.mark.asyncio
async def test_first_signal_creates_work_item():
    mock_redis.reset()
    with patch("app.core.debouncer.get_redis", return_value=mock_redis):
        from app.core.debouncer import get_or_create_work_item_id
        should_create, work_item_id = await get_or_create_work_item_id("TEST_COMPONENT")
        assert should_create is True
        assert work_item_id is not None
        assert len(work_item_id) == 36  # UUID format


@pytest.mark.asyncio
async def test_second_signal_links_to_same_work_item():
    mock_redis.reset()
    with patch("app.core.debouncer.get_redis", return_value=mock_redis):
        from app.core.debouncer import get_or_create_work_item_id
        should_create1, wi_id1 = await get_or_create_work_item_id("TEST_COMPONENT_2")
        should_create2, wi_id2 = await get_or_create_work_item_id("TEST_COMPONENT_2")

        assert should_create1 is True
        assert should_create2 is False
        assert wi_id1 == wi_id2  # same Work Item


@pytest.mark.asyncio
async def test_hundred_signals_same_work_item():
    mock_redis.reset()
    with patch("app.core.debouncer.get_redis", return_value=mock_redis):
        from app.core.debouncer import get_or_create_work_item_id
        work_item_ids = set()
        created_count = 0

        for _ in range(100):
            should_create, wi_id = await get_or_create_work_item_id("CACHE_CLUSTER_99")
            work_item_ids.add(wi_id)
            if should_create:
                created_count += 1

        assert created_count == 1           # only 1 Work Item created
        assert len(work_item_ids) == 1      # all signals link to same WI


@pytest.mark.asyncio
async def test_different_components_get_different_work_items():
    mock_redis.reset()
    with patch("app.core.debouncer.get_redis", return_value=mock_redis):
        from app.core.debouncer import get_or_create_work_item_id
        _, wi_id1 = await get_or_create_work_item_id("COMPONENT_A")
        _, wi_id2 = await get_or_create_work_item_id("COMPONENT_B")
        assert wi_id1 != wi_id2