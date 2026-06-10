from lru_cache import LRUCache


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

    # basic set and get
    c = LRUCache(2)
    c.set(1, 10)
    c.set(2, 20)
    check("get existing key 1", c.get(1), 10)
    check("get existing key 2", c.get(2), 20)
    check("get missing key", c.get(99), -1)

    # eviction: key 2 is LRU after get(1) promotes key 1
    c.reset(2)
    c.set(1, 10)
    c.set(2, 20)
    c.get(1)        # key 1 becomes MRU, key 2 is LRU
    c.set(3, 30)    # evicts key 2
    check("evicted LRU key", c.get(2), -1)
    check("kept MRU key 1", c.get(1), 10)
    check("new key 3 present", c.get(3), 30)

    # update existing key updates value and moves to front
    c.reset(2)
    c.set(1, 10)
    c.set(2, 20)
    c.set(1, 99)    # update key 1 — should become MRU
    c.set(3, 30)    # evicts key 2 (LRU), not key 1
    check("updated value reflected", c.get(1), 99)
    check("evicted LRU after update", c.get(2), -1)
    check("new key after update", c.get(3), 30)

    # capacity 1
    c.reset(1)
    c.set(1, 10)
    check("capacity 1 get", c.get(1), 10)
    c.set(2, 20)    # evicts key 1
    check("capacity 1 eviction", c.get(1), -1)
    check("capacity 1 new key", c.get(2), 20)

    # capacity 0
    c.reset(0)
    c.set(1, 10)
    check("capacity 0 stores nothing", c.get(1), -1)

    # set is idempotent for same key/value
    c.reset(2)
    c.set(1, 10)
    c.set(1, 10)
    check("idempotent set", c.get(1), 10)
    check("size stays within capacity", len(c.data), 1)

    print(f"\n{passed} passed, {failed} failed")


if __name__ == "__main__":
    main()
