import asyncio
import os
import tempfile

from durable_lru_cache import lru_cache


def build_cached_double(counter, cache_dir):
    @lru_cache(capacity=2, dir=cache_dir)
    def double(n):
        counter["calls"] += 1
        return n * 2

    return double


def main():
    passed = 0
    failed = 0

    def check(label, got, expected):
        nonlocal passed, failed
        if got == expected:
            print(f"  PASS  {label}")
            passed += 1
        else:
            print(f"  FAIL  {label}: got {got!r}, expected {expected!r}")
            failed += 1

    os.makedirs("/tmp/cache", exist_ok=True)
    cache_dir = tempfile.mkdtemp(prefix="durable_lru_cache_", dir="/tmp/cache")

    counter1 = {"calls": 0}
    cache1 = build_cached_double(counter1, cache_dir)
    check("first compute is a miss", cache1(3), 6)
    check("first function call count", counter1["calls"], 1)
    asyncio.run(cache1.flush())
    cache1.snapshot()
    cache1.close()

    counter2 = {"calls": 0}
    cache2 = build_cached_double(counter2, cache_dir)
    check("replayed value survives restart", cache2(3), 6)
    check("restart hit avoids recompute", counter2["calls"], 0)
    check("new key still computes", cache2(4), 8)
    check("new key increments calls", counter2["calls"], 1)
    asyncio.run(cache2.flush())
    cache2.close()

    wal_files = [name for name in os.listdir(cache_dir) if name.endswith(".wal")]
    check("wal file created", len(wal_files), 1)
    snapshot_files = [name for name in os.listdir(cache_dir) if name.endswith(".snapshot")]
    check("snapshot file created", len(snapshot_files), 1)

    wal_path = os.path.join(cache_dir, wal_files[0])
    with open(wal_path, "ab") as handle:
        handle.write(b"partial-record")

    counter3 = {"calls": 0}
    cache3 = build_cached_double(counter3, cache_dir)
    check("torn wal tail ignored during replay", cache3(3), 6)
    check("torn wal still replays cached value", counter3["calls"], 0)
    check("second cached key also survives replay", cache3(4), 8)
    cache3.close()

    print(f"\n{passed} passed, {failed} failed")


if __name__ == "__main__":
    main()
