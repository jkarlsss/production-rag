import pytest
from unittest.mock import patch
from app.cache import ResponseCache  # Adjust this import to match your file structure


class TestResponseCache:
    """Test suite for the ResponseCache utility."""

    @pytest.fixture
    def cache(self) -> ResponseCache:
        """Provides a fresh cache instance with a default 300-second TTL."""
        return ResponseCache(ttl_seconds=300)

    def test_key_normalization(self, cache: ResponseCache):
        """Verify that case differences and leading/trailing whitespace produce identical keys."""
        key_upper = cache._make_key("What is Python?")
        key_lower = cache._make_key("  what is python?  ")
        
        assert key_upper == key_lower

    def test_cache_set_and_get_hit(self, cache: ResponseCache):
        """Ensure a set value can be retrieved, counting as a cache hit."""
        query = "How old is the universe?"
        response = "About 13.8 billion years old."

        cache.set(query, response)
        cached_response = cache.get(query)

        assert cached_response == response
        assert cache._hits == 1
        assert cache._misses == 0

    def test_cache_miss(self, cache: ResponseCache):
        """Verify fetching an un-cached key returns None and increments misses."""
        response = cache.get("Unknown query")

        assert response is None
        assert cache._hits == 0
        assert cache._misses == 1

    def test_cache_ttl_expiration(self):
        """Verify that items expire exactly when they pass the designated TTL."""
        # Setup a short TTL for testing
        short_cache = ResponseCache(ttl_seconds=10)
        query = "Dynamic data"
        response = "Fresh answer"

        with patch("time.time") as mock_time:
            # Set initial time anchor
            mock_time.return_value = 1000.0
            short_cache.set(query, response)

            # Move forward just under the TTL (9 seconds)
            mock_time.return_value = 1009.0
            assert short_cache.get(query) == response

            # Move forward past the TTL (11 seconds from original placement)
            mock_time.return_value = 1011.0
            assert short_cache.get(query) is None

            # Verify the expired entry was evicted from the internal dictionary
            key = short_cache._make_key(query)
            assert key not in short_cache._cache

    def test_cache_stats_calculation(self, cache: ResponseCache):
        """Ensure performance tracking statistics calculate accurately."""
        # Initial empty stats
        initial_stats = cache.stats()
        assert initial_stats["hit_rate"] == "0.0%"
        assert initial_stats["cached_entries"] == 0

        # Prime the cache
        cache.set("q1", "a1")
        cache.set("q2", "a2")

        # Simulate 1 hit and 3 misses (1/4 = 25% hit rate)
        cache.get("q1")          # Hit
        cache.get("q2-expired")  # Miss
        cache.get("q3-missing")  # Miss
        cache.get("q4-missing")  # Miss

        stats = cache.stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 3
        assert stats["hit_rate"] == "25.0%"
        assert stats["cached_entries"] == 2