import argparse
import asyncio
import httpx
import time

from bs4 import BeautifulSoup
from collections import defaultdict
from typing import Dict, List, Optional, Set
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

from utils import get_domain, load_robot, extract_urls

class Crawler:
    """Crawl same domain urls starting from seed url with BFS.

    Respects `robots.txt` for the domain.
    Stops when max depth is reached from seed url.
    Limits concurrency to avoid occupying networking I/O extensively.
    """

    def __init__(self, seed_url: str, max_depth: int, max_concurrency: int, fetch_timeout: int):
        self.seed_url = seed_url
        self.max_depth = max_depth
        self.fetch_timeout = fetch_timeout

        self.domain = get_domain(seed_url)
        self.semaphore = asyncio.Semaphore(max_concurrency)
        self.visited: Set[str] = set()
        self.sitemap: Dict[str, List[str]] = defaultdict(list)
        self.robots: Dict[str, RobotFileParser] = {}

    def _http_headers(self):
        return {
            "User-Agent": "Yi-Web-Crawler/1.0"
        }

    def _load_robots(self, url: str) -> Optional[RobotFileParser]:
        domain = get_domain(url)
        if domain in self.robots:
            return self.robots[domain]
        parser = load_robot(url)
        self.robots[domain] = parser
        return parser

    async def _fetch(self, client: httpx.AsyncClient, url: str) -> Optional[str]:
        async with self.semaphore:
            try:
                response = await client.get(url)
                response.raise_for_status()
                return response.text
            except httpx.TimeoutException as e:
                print(f"[fetch] timeout {url} ({e!s})")
                return None
            except httpx.HTTPStatusError as e:
                print(f"[fetch] HTTP {e.response.status_code} {url}")
                return None
            except httpx.RequestError as e:
                print(f"[fetch] transport {url} ({type(e).__name__}: {e})")
                return None
            except Exception as e:
                print(f"[fetch] unexpected {url} ({type(e).__name__}: {e})")
                return None
    
    async def _crawl(self, client: httpx.AsyncClient, url: str, depth: int):
        if depth > self.max_depth or url in self.visited:
            return
        self.visited.add(url)
        
        robot_parser = self._load_robots(url)
        allowed = robot_parser.can_fetch("*", url) if robot_parser else True
        if not allowed:
            print(f"[robots] disallowed {url} (depth {depth})")
            return

        html = await self._fetch(client, url)
        if not html:
            print(f"[crawl] skip {url} (depth {depth}): empty or failed body")
            return

        links = [
            link
            for link in extract_urls(html, url)
            if get_domain(link) == self.domain
        ]
        self.sitemap[url] = links
        print(f"[crawl] depth {depth} {url} -> {len(links)} same-host links")

        tasks = [
            self._crawl(client, link, depth + 1)
            for link in links
            if link not in self.visited and depth < self.max_depth
        ]
        if not tasks:
            return
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for r in results:
            if isinstance(r, BaseException):
                print(f"[crawl] subcrawl raised {type(r).__name__}: {r}")


    async def run(self):
        async with httpx.AsyncClient(
            headers=self._http_headers(),
            follow_redirects=True,
            timeout=self.fetch_timeout,
        ) as client:
            await self._crawl(client, self.seed_url, 0)
        return dict(self.sitemap)


async def main():
    parser = argparse.ArgumentParser(description="Hand curated web crawler using asyncio + httpx.")
    parser.add_argument("--seed-url", type=str, help="seed url to start crawling.")
    parser.add_argument("--max-depth", type=int, default=1, help="max depth to stop crawling.")
    parser.add_argument("--max-concurrency", type=int, default=10, help="max concurrency to do networking requests.")
    parser.add_argument("--fetch-timeout", type=int, default=10, help="timeout to fetch 1 web page.")
    args = parser.parse_args()
    print(f"[main] start seed={args.seed_url!r} max_depth={args.max_depth} concurrency={args.max_concurrency}")
    start = time.perf_counter()
    crawler = Crawler(args.seed_url, args.max_depth, args.max_concurrency, args.fetch_timeout)
    sitemap = await crawler.run()
    elapsed = time.perf_counter() - start
    print(f"[main] done in {elapsed:.2f}s ({args.seed_url})")
    print(f"[main] got sitemap with {len(sitemap)} links and {args.max_depth} depth.")


if __name__ == "__main__":
    asyncio.run(main())
