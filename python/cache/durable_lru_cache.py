import asyncio
import os
import pickle
import struct
import threading
import zlib
from functools import wraps


class Node:
    def __init__(self, k, v):
        self.k = k
        self.v = v
        self.prev = None
        self.next = None

    def remove(self):
        if self.prev:
            self.prev.next = self.next
        if self.next:
            self.next.prev = self.prev
        self.prev = None
        self.next = None

    def append(self, node):
        node.prev = self
        node.next = self.next
        if self.next:
            self.next.prev = node
        self.next = node


class DurableStore:
    _HEADER = struct.Struct("!II")

    def __init__(self, capacity, dir_path, name, snapshot_threshold=32):
        self.capacity = capacity
        self.dir_path = dir_path
        self.name = name
        self.snapshot_threshold = snapshot_threshold

        self.data = {}
        self.head = Node(None, None)
        self.tail = Node(None, None)
        self.head.append(self.tail)

        self.lock = threading.RLock()
        self.cv = threading.Condition(self.lock)
        self.pending = []
        self.next_seq = 1
        self.flushed_seq = 0
        self.closed = False

        self.snapshot_path = None
        self.wal_path = None
        self._wal = None
        self._writer = None

        if self.dir_path:
            os.makedirs(self.dir_path, exist_ok=True)
            self.snapshot_path = os.path.join(self.dir_path, f"{self.name}.snapshot")
            self.wal_path = os.path.join(self.dir_path, f"{self.name}.wal")
            self._load_from_disk()
            self._wal = open(self.wal_path, "ab")
            self._writer = threading.Thread(target=self._writer_loop, daemon=True)
            self._writer.start()

    def close(self):
        if not self.dir_path:
            return
        with self.cv:
            self.closed = True
            self.cv.notify_all()
        if self._writer:
            self._writer.join()
        if self._wal:
            self._wal.close()

    def get(self, key):
        with self.lock:
            node = self.data.get(key)
            if node is None:
                return None, False
            self._recent_accessed(node)
            return node.v, True

    def put(self, key, value):
        with self.lock:
            self._set_node(key, value)
            if self.dir_path:
                seq = self.next_seq
                self.next_seq += 1
                self.pending.append((seq, {"op": "put", "key": key, "value": value}))
                self.cv.notify_all()

    def cache_size(self):
        with self.lock:
            return len(self.data)

    def ordered_items(self):
        items = []
        curr = self.head.next
        while curr is not self.tail:
            items.append((curr.k, curr.v))
            curr = curr.next
        return items

    def snapshot(self):
        if not self.dir_path:
            return
        self.flush()
        with self.lock:
            payload = {
                "version": 1,
                "capacity": self.capacity,
                "items": self.ordered_items(),
                "flushed_seq": self.flushed_seq,
            }
        temp_path = f"{self.snapshot_path}.tmp"
        with open(temp_path, "wb") as handle:
            pickle.dump(payload, handle, protocol=pickle.HIGHEST_PROTOCOL)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, self.snapshot_path)

    def replay(self):
        if not self.dir_path:
            return
        self.flush()
        with self.lock:
            self._reset_state_locked()
            self._load_from_disk_locked()

    def flush(self):
        if not self.dir_path:
            return
        with self.cv:
            target = self.next_seq - 1
            while self.flushed_seq < target:
                self.cv.notify_all()
                self.cv.wait()

    async def async_flush(self):
        await asyncio.to_thread(self.flush)

    def _load_from_disk(self):
        with self.lock:
            self._load_from_disk_locked()

    def _load_from_disk_locked(self):
        snapshot_seq = 0
        if self.snapshot_path and os.path.exists(self.snapshot_path):
            with open(self.snapshot_path, "rb") as handle:
                payload = pickle.load(handle)
            self.capacity = payload["capacity"]
            for key, value in reversed(payload["items"]):
                self._set_node(key, value)
            snapshot_seq = payload.get("flushed_seq", 0)
            self.flushed_seq = snapshot_seq
            self.next_seq = snapshot_seq + 1

        if self.wal_path and os.path.exists(self.wal_path):
            for seq, record in self._read_wal(self.wal_path):
                if seq <= snapshot_seq:
                    continue
                self._apply_record(record)
                self.flushed_seq = max(self.flushed_seq, seq)
                self.next_seq = max(self.next_seq, seq + 1)

    def _reset_state_locked(self):
        self.data = {}
        self.head = Node(None, None)
        self.tail = Node(None, None)
        self.head.append(self.tail)
        self.flushed_seq = 0
        self.next_seq = 1

    def _set_node(self, key, value):
        if self.capacity <= 0:
            return
        if key in self.data:
            node = self.data[key]
            node.v = value
            self._recent_accessed(node)
            return

        node = Node(key, value)
        self._recent_accessed(node)
        self.data[key] = node
        if len(self.data) > self.capacity:
            last = self.tail.prev
            last.remove()
            del self.data[last.k]

    def _recent_accessed(self, node):
        node.remove()
        self.head.append(node)

    def _apply_record(self, record):
        if record["op"] == "put":
            self._set_node(record["key"], record["value"])
        else:
            raise ValueError(f"unknown WAL op: {record['op']}")

    def _writer_loop(self):
        while True:
            with self.cv:
                while not self.pending and not self.closed:
                    self.cv.wait()
                if not self.pending and self.closed:
                    return
                batch = self.pending
                self.pending = []

            max_seq = self._append_batch(batch)

            with self.cv:
                self.flushed_seq = max(self.flushed_seq, max_seq)
                self.cv.notify_all()

    def _append_batch(self, batch):
        max_seq = 0
        for seq, record in batch:
            payload = pickle.dumps((seq, record), protocol=pickle.HIGHEST_PROTOCOL)
            checksum = zlib.crc32(payload)
            self._wal.write(self._HEADER.pack(len(payload), checksum))
            self._wal.write(payload)
            max_seq = seq
        self._wal.flush()
        os.fsync(self._wal.fileno())
        return max_seq

    @classmethod
    def _read_wal(cls, wal_path):
        with open(wal_path, "rb") as handle:
            while True:
                header = handle.read(cls._HEADER.size)
                if not header:
                    return
                if len(header) != cls._HEADER.size:
                    return
                length, checksum = cls._HEADER.unpack(header)
                payload = handle.read(length)
                if len(payload) != length:
                    return
                if zlib.crc32(payload) != checksum:
                    return
                yield pickle.loads(payload)


def _freeze(x):
    if isinstance(x, list):
        return tuple(_freeze(item) for item in x)
    if isinstance(x, dict):
        return tuple(sorted((k, _freeze(v)) for k, v in x.items()))
    if isinstance(x, set):
        return frozenset(_freeze(item) for item in x)
    return x


def _cache_name(func):
    return f"{func.__module__}.{func.__qualname__}".replace(os.sep, "_").replace(" ", "_")


def lru_cache(func=None, capacity=128, dir=None, snapshot_threshold=32):
    def decorator(func):
        store = DurableStore(
            capacity=capacity,
            dir_path=dir,
            name=_cache_name(func),
            snapshot_threshold=snapshot_threshold,
        )

        @wraps(func)
        def wrapper(*args, **kwargs):
            key = (
                tuple(_freeze(x) for x in args),
                tuple(sorted((k, _freeze(v)) for k, v in kwargs.items())),
            )
            value, found = store.get(key)
            if found:
                wrapper.cache_hit += 1
                return value

            result = func(*args, **kwargs)
            store.put(key, result)
            wrapper.cache_miss += 1
            return result

        def cache_info():
            return {
                "hits": wrapper.cache_hit,
                "misses": wrapper.cache_miss,
                "size": store.cache_size(),
            }

        def replay():
            store.replay()

        def snapshot():
            store.snapshot()

        def close():
            store.close()

        async def flush():
            await store.async_flush()

        wrapper.cache_hit = 0
        wrapper.cache_miss = 0
        wrapper.cache_info = cache_info
        wrapper.flush = flush
        wrapper.replay = replay
        wrapper.snapshot = snapshot
        wrapper.close = close

        return wrapper

    if func is None:
        return decorator
    return decorator(func)


@lru_cache(capacity=10, dir="./.cache")
def fib(n):
    if n <= 1:
        return n
    return fib(n - 1) + fib(n - 2)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Durable LRU cache demo for Fibonacci.")
    parser.add_argument("--start", type=int, default=20, help="Start n (inclusive).")
    parser.add_argument("--end", type=int, default=24, help="End n (exclusive).")
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="Remove durable cache files before running.",
    )
    parser.add_argument(
        "--cleanup-only",
        action="store_true",
        help="Remove durable cache files and exit.",
    )
    args = parser.parse_args()

    if args.end <= args.start:
        raise ValueError("--end must be greater than --start")

    cache_dir = "./.cache"
    cache_name = _cache_name(fib.__wrapped__)
    snapshot_path = os.path.join(cache_dir, f"{cache_name}.snapshot")
    wal_path = os.path.join(cache_dir, f"{cache_name}.wal")

    if args.cleanup or args.cleanup_only:
        # Store is created at import time by the decorator, so close it first.
        fib.close()
        for path in (snapshot_path, wal_path):
            if os.path.exists(path):
                os.remove(path)
                print(f"removed {path}")
        if args.cleanup_only:
            return
        print("cache files removed; re-run command to start with a clean store")
        return

    # On first run this fills the durable cache.
    # On subsequent runs, values are auto-loaded from disk at import/decorator init.
    try:
        print("before:", fib.cache_info())
        for i in range(args.start, args.end):
            print(f"{i}'s fib number is {fib(i)}")
        print("after:", fib.cache_info())

        # Optional: compact WAL into snapshot. (snapshot() already flushes.)
        fib.snapshot()
    finally:
        # Important for short-lived programs: stop writer thread and close WAL.
        fib.close()


if __name__ == "__main__":
    main()
