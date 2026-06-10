import argparse
import time
import requests
import threading

from queue import Queue
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from typing import Set
from utils import get_domain, load_robot, extract_urls

class Crawler:
    """ Crawls links given the seed url of the same domain.

    """
    def __init__(self, seed_url: str, max_depth: int, max_concurrency: int, fetch_timeout: int):
        self.seed_url = seed_url
        self.domain = get_domain(seed_url)
        self.max_depth = max_depth
        self.max_concurrency = max_concurrency
        self.fetch_timeout = fetch_timeout
        self.sitemap = defaultdict(list)
        self.visited: Set[str] = set()
        self.robots = {}
        self.lock = threading.Lock()


    def _crawl(self, q: Queue, session: requests.Session):
        while True:
            (url, depth) = q.get()
            if url is None:
                q.task_done()
                break

            with self.lock:
                if url in self.visited or depth > self.max_depth:
                    q.task_done()
                    continue
                self.visited.add(url)
                if self.domain not in self.robots:
                    self.robots[self.domain] = load_robot(url)
                robot_parser = self.robots[self.domain]

            allowed = robot_parser.can_fetch("*", url) if robot_parser else True
            if not allowed:
                print(f"[robot] disallowed {url} (depth {depth})")
                q.task_done()
                continue
            try:
                response = session.get(url, timeout=self.fetch_timeout)
                response.raise_for_status()
                html = response.text
                urls = extract_urls(html, url)
                links = [link for link in urls if get_domain(link) == self.domain]
                with self.lock:
                    self.sitemap[url] = links
                for link in links:
                    with self.lock:
                        already_visited = link in self.visited
                    if not already_visited:
                        q.put((link, depth + 1))
                print(f"[crawl] depth {depth} {url} -> {len(links)} same-host links")
            except Exception as e:
                print(f"[crawl] failed to crawl {url}: {e}")
            finally:
                q.task_done()


    def run(self):
        q = Queue()
        q.put((self.seed_url, 0))
        with requests.Session() as session:
            session.headers["User-Agent"] = "Yi-Web-Crawler/1.0"
            with ThreadPoolExecutor(max_workers=self.max_concurrency) as ex:
                for _ in range(self.max_concurrency):
                    ex.submit(self._crawl, q, session)

                q.join()

                for _ in range(self.max_concurrency):
                    q.put((None, None))
        return dict(self.sitemap)


def main():
    parser = argparse.ArgumentParser(description="Hand curated web crawler using threads + requests.")
    parser.add_argument("--seed-url", type=str, help="seed url to start crawling.")
    parser.add_argument("--max-depth", type=int, default=1, help="max depth to stop crawling.")
    parser.add_argument("--max-concurrency", type=int, default=10, help="max concurrency to do networking requests.")
    parser.add_argument("--fetch-timeout", type=int, default=10, help="timeout to fetch 1 web page.")
    args = parser.parse_args()
    print(f"[main] start seed={args.seed_url!r} max_depth={args.max_depth} concurrency={args.max_concurrency}")
    start = time.perf_counter()
    crawler = Crawler(args.seed_url, args.max_depth, args.max_concurrency, args.fetch_timeout)
    sitemap = crawler.run()
    elapsed = time.perf_counter() - start
    print(f"[main] done in {elapsed:.2f}s ({args.seed_url})")
    print(f"[main] got sitemap with {len(sitemap)} links and {args.max_depth} depth.")


if __name__ == "__main__":
    main()
