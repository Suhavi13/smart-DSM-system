"""Clear GBTAC Redis cache keys without flushing unrelated Redis data."""

from backend.app.cache_service import cache


def main() -> None:
    deleted = cache.clear_namespace()
    print(f"Deleted {deleted} GBTAC cache key(s).")


if __name__ == "__main__":
    main()
