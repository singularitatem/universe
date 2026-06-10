import bs4
import requests

from typing import List
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

def get_domain(url: str) -> str:
    parsed = urlparse(url)
    return parsed.hostname


def load_robot(url: str) -> RobotFileParser:
    domain = get_domain(url)
    robot_url = f"https://{domain}/robots.txt"
    try:
        response = requests.get(robot_url)
        response.raise_for_status()
        parser = RobotFileParser()
        parser.parse(response.text.splitlines())
        return parser
    except Exception as e:
        print(f"[robots] loads failed {robot_url}: {e}")
        return None

def extract_urls(html: str, base_url: str) -> List[str]:
    parsed = urlparse(base_url)
    schema = parsed.scheme
    soup = bs4.BeautifulSoup(html, 'html.parser')
    tags = soup.find_all('a', href=True)
    links = []
    for tag in tags:
        raw = tag.get("href", "").strip()
        if not raw or raw.startswith(("#", "mailto:", "javascript:")):
            continue
        absolute = urljoin(base_url, raw)
        if schema in ("http", "https"):
            links.append(urlparse(absolute)._replace(fragment="").geturl())
    return links
        
