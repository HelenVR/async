import asyncio
import aiohttp
import aiofiles
from bs4 import BeautifulSoup
import os
import time

BASE_URL = "https://news.ycombinator.com/"
TOP_N = 5
CRAWL_INTERVAL = 300
NEWS_DIR = 'data'


async def fetch(session: aiohttp.ClientSession, url: str, headers=None) -> str | None:
    try:
        async with session.get(url, headers=headers) as resp:
            resp.raise_for_status()
            return await resp.text()
    except Exception as e:
        print(f"Error while getting page {url}: {e}")
        return None


def parse_top_news(html) -> list:
    soup = BeautifulSoup(html, 'html.parser')
    links = []
    rows = soup.select("tr.athing")
    for row in rows[:TOP_N]:
        title_span = row.find('span', class_='titleline')
        if title_span and title_span.find('a'):
            full_url = title_span.find('a')['href']
            news_id = row.get('id')
            links.append((news_id, full_url))
    return links


async def save_html(folder_path: str, filename: str, html) -> None:
    os.makedirs(folder_path, exist_ok=True)
    path = os.path.join(folder_path, filename)
    async with aiofiles.open(path, 'w', encoding='utf-8') as f:
        await f.write(html)


async def download_news_and_comments(session: aiohttp.ClientSession,
                                     news_id: str,
                                     news_url: str,
                                     news_links: set) -> None:
    folder = os.path.join(NEWS_DIR, news_id)
    news_html = await fetch(session, news_url)
    if not news_html:
        print(f"Failed to get news {news_url}")
        return
    await save_html(folder, "news.html", news_html)
    if not news_links:
        print(f"No links found in comments for news {news_id}")
        return

    print(f"For {news_id} news {len(news_links)} links found in comments. Downloading...")
    tasks = []
    for i, link in enumerate(news_links):
        filename = f"comment_{i + 1}.html"
        tasks.append(download_and_save(session, link, folder, filename))
    await asyncio.gather(*tasks)


async def get_comments_links(session: aiohttp.ClientSession, news_id: str) -> set | None:
    url = f'{BASE_URL}item?id={news_id}'
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/114.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Cache-Control": "max-age=0",
    }
    page = await fetch(session, url, headers)
    links = set()
    if not page:
        print(f'Failed to get page for new {news_id}')
    soup = BeautifulSoup(page, 'html.parser')
    for link in soup.find_all('a', href=True):
        href = link.get('href')
        if href.startswith("http://") or href.startswith("https://"):
            links.add(href)
    return links


async def download_and_save(session: aiohttp.ClientSession,
                            url: str,
                            folder: str,
                            filename: str) -> None:
    html = await fetch(session, url)
    if html:
        await save_html(folder, filename, html)
    else:
        print(f"Failed to download {url}")


async def main() -> None:
    async with aiohttp.ClientSession() as session:
        seen_news = set()
        while True:
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] ---Main page parsing---")
            main_page_html = await fetch(session, BASE_URL)
            if not main_page_html:
                print("Main page parsing error, scip")
                await asyncio.sleep(CRAWL_INTERVAL)
                continue
            top_news = parse_top_news(main_page_html)
            new_news = [(nid, url) for nid, url in top_news if nid not in seen_news]
            if new_news:
                print(f"{len(new_news)} news found")
                for nid, url in new_news:
                    print(f"Downloading news {nid} - {url}")
                    news_links = await get_comments_links(session, nid)
                    await download_news_and_comments(session, nid, url, news_links)
                    seen_news.add(nid)
            else:
                print("No unprocessed news found")

            await asyncio.sleep(CRAWL_INTERVAL)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("News tracker stopped")