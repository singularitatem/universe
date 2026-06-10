"""Maglev consistent hashing (Google, 2016).

Builds a fixed-size lookup table (prime M) where each slot maps to a node.
add_node / remove_node rebuild the table — O(M * n).
get_node is O(1).
"""

import hashlib
from typing import List, Optional

_TABLE_SIZE = 65537  # prime; ~100x a typical max node count


class MaglevHash:
    def __init__(self, nodes: List[str] = ()):
        self._nodes: list[str] = list(nodes)
        self._table: list[int] = []
        if self._nodes:
            self._build()

    def _h1(self, key: str) -> int:
        return int(hashlib.md5(key.encode()).hexdigest(), 16)

    def _h2(self, key: str) -> int:
        return int(hashlib.sha1(key.encode()).hexdigest(), 16)

    def _build(self) -> None:
        M = _TABLE_SIZE
        n = len(self._nodes)
        offsets = [self._h1(node) % M for node in self._nodes]
        skips   = [self._h2(node) % (M - 1) + 1 for node in self._nodes]

        table = [-1] * M
        nexts = [0] * n
        filled = 0

        while filled < M:
            for i in range(n):
                c = (offsets[i] + nexts[i] * skips[i]) % M
                while table[c] != -1:
                    nexts[i] += 1
                    c = (offsets[i] + nexts[i] * skips[i]) % M
                table[c] = i
                nexts[i] += 1
                filled += 1
                if filled == M:
                    break

        self._table = table

    def add_node(self, node: str) -> None:
        self._nodes.append(node)
        self._build()

    def remove_node(self, node: str) -> None:
        self._nodes.remove(node)
        self._table = []
        if self._nodes:
            self._build()

    def get_node(self, key: str) -> Optional[str]:
        if not self._table:
            return None
        idx = self._h1(key) % _TABLE_SIZE
        return self._nodes[self._table[idx]]
