from collections import deque, namedtuple
from typing import Deque, Iterable, List, Sequence, Tuple

Sample = namedtuple("Sample", ["ts", "stack"])
Event = namedtuple("Event", ["kind", "ts", "name"])


def _longest_common_stack(former: Sequence[str], latter: Sequence[str]) -> Tuple[int, int, int]:
    """
    Find the longest common contiguous segment under head-truncation.

    Returns `(a, b, l)` where:
    - `former[a : a + l] == latter[b : b + l]`
    - either `a == 0` or `b == 0`

    This models sampling where one stack may be missing some outer frames.
    """
    n, m = len(former), len(latter)
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n - 1, -1, -1):
        for j in range(m - 1, -1, -1):
            if former[i] == latter[j]:
                dp[i][j] = 1 + dp[i+1][j+1]
            else:
                dp[i][j] = 0
    longest, a, b = 0, 0, 0
    for i in range(n):
        if dp[i][0] > longest:
            longest = dp[i][0]
            a = i
            b = 0
    for j in range(m):
        if dp[0][j] > longest:
            longest = dp[0][j]
            a = 0
            b = j
    return (a, b, longest)


def _enqueue_event(pending_events: Deque[Event], pending_counts: Deque[int], event: Event) -> None:
    """Coalesce adjacent identical events to keep output compact."""
    if pending_events and pending_events[-1] == event:
        pending_counts[-1] += 1
        return
    pending_events.append(event)
    pending_counts.append(1)


def _dequeue_event(pending_events: Deque[Event], pending_counts: Deque[int], event: Event) -> None:
    if pending_events and pending_events[-1].name == event.name and pending_counts[-1] > 1:
        pending_counts[-1] -= 1
        return
    pending_events.pop()
    pending_counts.pop()


def stackTrace(samples: Iterable[Sample], delta: float = 0) -> List[Tuple[Event, int]]:
    """
    Convert stack samples into trace events.

    Each sample is sorted (timestamp, stack), where stack = [root, ..., leaf].

    Output is a list of `(Event, count)` where `Event = (kind, ts, name)`.
    Adjacent identical events are coalesced into one entry with `count > 1`.

    Rules:
    - Compare consecutive stacks via `lcStack`, allowing one side to be
      truncated at the head (outermost frames missing).
    - Functions not in the new stack → emit "end" events (inner → outer).
    - New functions in the new stack → emit "start" events (outer → inner).
    - If stacks are identical → emit nothing.
    - Recursive calls are distinct by position (stack index).
    - `delta` delays emission: events are flushed only when
      `current_ts - pending_event_ts > delta`.
    - Any events still pending after the last sample are intentionally dropped
      (preserves legacy behavior).

    Returns:
        List of events in chronological order.
    """
    events: List[Tuple[Event, int]] = []
    pending_events: Deque[Event] = deque()
    pending_counts: Deque[int] = deque()

    last_sample = Sample(-1, [])
    last_start_idx = 0
    for sample in samples:
        ts, stack = sample.ts, sample.stack
        old_stack = last_sample.stack
        old_start, new_start, common_len = _longest_common_stack(old_stack, stack)
        # End events: only frames deeper than the aligned common segment.
        # Head-truncated frames are ambiguous and intentionally ignored.
        old_tail_start = old_start + common_len
        for name in reversed(old_stack[old_tail_start:]):
            if ts - pending_events[last_start_idx].ts > delta:
                _enqueue_event(pending_events, pending_counts, Event("end", ts, name))
            else:
                _dequeue_event(pending_events, pending_counts, Event("end", ts, name))
                for i, e in enumerate(reversed(pending_events)):
                    if e.kind == "start":
                        last_start_idx = i
                        break

        # Start events: only frames deeper than the aligned common segment.
        new_tail_start = new_start + common_len
        for name in stack[new_tail_start:]:
            _enqueue_event(pending_events, pending_counts, Event("start", ts, name))
            last_start_idx = len(pending_events) - 1

        last_sample = sample
    
    while pending_events:
        events.append((pending_events.popleft(), pending_counts.popleft()))

    # Preserve original behavior: do not flush pending events after the final sample.
    return events

def main():
    test_cases = [
        {
            "name": "basic_start_end",
            "delta": 0.0,
            "samples": [
                Sample(1.0, ["main"]),
                Sample(2.0, ["main", "f1"]),
                Sample(3.0, ["main"]),
            ],
            "expected": [
                (Event("start", 1.0, "main"), 1),
                (Event("start", 2.0, "f1"), 1),
                (Event("end", 3.0, "f1"), 1),
            ],
        },
        {
            "name": "recursive_frames",
            "delta": 0.0,
            "samples": [
                Sample(1.0, ["main"]),
                Sample(2.0, ["main", "f1", "f1", "f1"]),
                Sample(3.0, ["main", "f1", "f2"]),
            ],
            "expected": [
                (Event("start", 1.0, "main"), 1),
                (Event("start", 2.0, "f1"), 3),
                (Event("end", 3.0, "f1"), 2),
                (Event("start", 3.0, "f2"), 1),
            ],
        },
        {
            "name": "head_truncation_alignment",
            "delta": 0.0,
            "samples": [
                Sample(1.0, ["root", "a", "b", "c"]),
                Sample(2.0, ["a", "b", "d"]),
            ],
            "expected": [
                (Event("start", 1.0, "root"), 1),
                (Event("start", 1.0, "a"), 1),
                (Event("start", 1.0, "b"), 1),
                (Event("start", 1.0, "c"), 1),
                (Event("end", 2.0, "c"), 1), 
                (Event("start", 2.0, "d"), 1),
            ],
        },
        {
            "name": "delta_truncates_unflushed_tail",
            "delta": 1.5,
            "samples": [
                Sample(1.0, ["main"]),
                Sample(2.0, ["main", "f1", "f2"]),
                Sample(3.0, ["main", "f1"]),
                Sample(4.0, ["main"]),
            ],
            "expected": [
                # start(main) flushes at ts=3.0 because 3.0 - 1.0 > 1.5
                (Event("start", 1.0, "main"), 1),
                (Event("start", 2.0, "f1"), 1),
                (Event("end", 4.0, "f1"), 1),
            ],
        },
    ]

    print(f"Running {len(test_cases)} tests")
    for case in test_cases:
        got = stackTrace(case["samples"], delta=case["delta"])
        if got != case["expected"]:
            print(f"[FAIL] {case['name']} (delta={case['delta']})")
            print("  expected:")
            for event, count in case["expected"]:
                print(f"    {event} x{count}")
            print("  got:")
            for event, count in got:
                print(f"    {event} x{count}")
            raise AssertionError(f"test failed: {case['name']}")
        print(f"[PASS] {case['name']}")

    print("All tests passed.")

if __name__ == "__main__":
    main()

