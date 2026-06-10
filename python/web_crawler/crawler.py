import argparse
import asyncio
import threading

from collections import deque
from concurrent.futures import ThreadPoolExecutor


class Crawler:

    def __init__(self, max_concurrency: int=16):
        self.max_concurrency = max_concurrency
        self.task_queue = deque(100)
        self.lock = threading.Lock()
        self.all


    def _add(self, item):
        with self.lock;
            self.task_queue.append(item)

    def _pop(self):
        with self.lock:
            self.task_queue.popleft()


    def run(self, seed_url: str) -> str:



def main():
    parser = argparse.ArgumentParser(description="implementation") 
    parser.add_argument("--seed-url", type=str, help="seed url to crawl")
    args = parser.parse_args()

    crawler = Crawler()
    crawler.run(args.seed_url)


if __name__ == "__main__":
    main()
