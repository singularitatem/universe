"""Ketama consistent hashing.

Places each node at `replicas` virtual points on a hash ring using MD5.
Lookup finds the nearest point clockwise — O(log n) via bisect.
"""

import bisect
import hashlib
from typing import List, Optional


class KetamaHash:
    def __init__(self, nodes: List[str] = (), replicas: int = 150):
        self._replicas = replicas
        self._ring: dict[int, str] = {}
        self._keys: list[int] = []
        for node in nodes:
            self.add_node(node)

    def _hash(self, key: str) -> int:
        return int(hashlib.md5(key.encode()).hexdigest(), 16)

    def add_node(self, node: str) -> None:
        for i in range(self._replicas):
            h = self._hash(f"{node}:{i}")
            self._ring[h] = node
            bisect.insort(self._keys, h)

    def remove_node(self, node: str) -> None:
        for i in range(self._replicas):
            h = self._hash(f"{node}:{i}")
            self._ring.pop(h, None)
            idx = bisect.bisect_left(self._keys, h)
            if idx < len(self._keys) and self._keys[idx] == h:
                self._keys.pop(idx)

    def get_node(self, key: str) -> Optional[str]:
        if not self._ring:
            return None
        h = self._hash(key)
        idx = bisect.bisect(self._keys, h) % len(self._keys)
        return self._ring[self._keys[idx]]
