from functools import wraps
from threading import RLock


def lru_cache(func=None, capacity=128):
    def decorator(func):
        data = {}
        lock = RLock()
        missing = object()

        class Node():
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

            def append(self, node):
                node.prev = self
                node.next = self.next
                if self.next:
                    self.next.prev = node
                self.next = node

        head = Node(None, None)
        tail = Node(None, None)
        head.append(tail)

        def recent_accessed(n):
            n.remove()
            head.append(n)

        def get(key):
            if key not in data:
                return missing

            n = data[key]
            recent_accessed(n)
            return n.v

        def put(key, value):
            if key in data:
                n = data[key]
                recent_accessed(n)
                n.v = value
                return
            n = Node(key, value)
            recent_accessed(n)
            data[key] = n
            if len(data) > capacity:
                last = tail.prev
                last.remove()
                del data[last.k]

        def freeze(x):
            if isinstance(x, list):
                return tuple(freeze(item) for item in x)
            elif isinstance(x, dict):
                return tuple(sorted((k, freeze(v)) for k, v in x.items()))
            elif isinstance(x, set):
                return frozenset(freeze(item) for item in x)
            return x

        def to_key(args, kwargs):
            return (
                tuple(freeze(x) for x in args),
                tuple(sorted((k, freeze(v)) for k, v in kwargs.items()))
            )

        @wraps(func)
        def wrapper(*args, **kwargs):
            key = to_key(args, kwargs)
            with lock:
                value = get(key)
                if value is not missing:
                    wrapper.cache_hit += 1
                    return value

            result = func(*args, **kwargs)

            with lock:
                put(key, result)
                wrapper.cache_miss += 1
                return result

        def cache_info():
            return {
                "hits": wrapper.cache_hit,
                "misses": wrapper.cache_miss,
                "size": len(data),
            }

        wrapper.cache_hit = 0
        wrapper.cache_miss = 0
        wrapper.cache_info = cache_info

        return wrapper

    if func is None:
        return decorator
    return decorator(func)

@lru_cache(capacity=10)
def fib(n):
    if n <= 1:
        return n
    return fib(n-1) + fib(n-2)


@lru_cache
def letters(pref):
    if len(pref) < 1:
        return ""
    return letters(pref[1:])

def main():
    for i in range(20, 30):
        print(f"{i}'s fib number is {fib(i)}: {fib.cache_info()}")
    print(letters([1,2,[3, 4], {"r": "t"}]))
    print(letters.cache_info())

if __name__ == "__main__":
    main()
