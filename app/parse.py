import asyncio
import csv
import logging
import sys
from dataclasses import astuple, dataclass, fields
from urllib.parse import urljoin

import aiohttp
from bs4 import BeautifulSoup, Tag

BASE_URL = "https://quotes.toscrape.com/"
MAX_CONCURRENT_REQUESTS = 3


@dataclass
class Quote:
    text: str
    author: str
    tags: list[str]


QUOTE_FIELDS = [field.name for field in fields(Quote)]


logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)8s]: %(message)s",
    handlers=[
        logging.FileHandler("parser.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)


def parse_single_quote(quote_div: Tag) -> Quote:
    """Parse a single quote from the quote div element."""
    return Quote(
        text=quote_div.select_one(".text").text,
        author=quote_div.select_one(".author").text,
        tags=[tag.text for tag in quote_div.select(".tag")],
    )


def get_single_page_quotes(page_soup: Tag) -> list[Quote]:
    """Extract all quotes from a single page."""
    quotes_divs = page_soup.select(".quote")
    return [parse_single_quote(quote_div) for quote_div in quotes_divs]


def get_next_page_url(page_soup: Tag) -> str | None:
    """Get URL of the next page if it exists."""
    next_button = page_soup.select_one("li.next a")

    if next_button:
        return urljoin(BASE_URL, next_button["href"])

    return None


async def get_page_content(session: aiohttp.ClientSession, url: str) -> str:
    """Get HTML content of the page."""
    async with session.get(url) as response:
        response.raise_for_status()
        return await response.text()


async def process_single_page(
    session: aiohttp.ClientSession,
    url: str,
    page_number: int,
    semaphore: asyncio.Semaphore,
) -> tuple[list[Quote], str | None]:
    """Process a single page and return quotes with next page URL."""
    async with semaphore:
        logging.info(f"Parsing page #{page_number}")
        page_content = await get_page_content(session, url)
        page_soup = BeautifulSoup(page_content, "html.parser")

        quotes = get_single_page_quotes(page_soup)

        next_url = get_next_page_url(page_soup)
        return quotes, next_url


async def get_all_quotes() -> list[Quote]:
    """Collect all quotes from all pages asynchronously."""
    all_quotes = []
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)

    async with aiohttp.ClientSession() as session:
        first_page = await process_single_page(
            session, BASE_URL, 1, semaphore
        )
        all_quotes.extend(first_page[0])
        next_url = first_page[1]

        page_urls = []
        page_number = 2
        current_url = next_url

        while current_url:
            page_urls.append(current_url)
            page_content = await get_page_content(session, current_url)
            page_soup = BeautifulSoup(page_content, "html.parser")
            current_url = get_next_page_url(page_soup)
            page_number += 1

        if page_urls:
            tasks = [
                process_single_page(session, url, i + 2, semaphore)
                for i, url in enumerate(page_urls)
            ]
            results = await asyncio.gather(*tasks)

            for quotes, _ in results:
                all_quotes.extend(quotes)

    logging.info(f"Total quotes collected: {len(all_quotes)}")
    return all_quotes


def write_quotes_to_csv(quotes: list[Quote], output_path: str) -> None:
    """Write quotes to a CSV file."""
    with open(output_path, "w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(QUOTE_FIELDS)
        writer.writerows([astuple(quote) for quote in quotes])

    logging.info(f"Quotes have been saved to {output_path}")


async def async_main(output_csv_path: str) -> None:
    """Scrape all quotes and save them to a CSV file."""
    logging.info("Starting quotes scraping...")
    quotes = await get_all_quotes()
    write_quotes_to_csv(quotes, output_csv_path)
    logging.info("Scraping complete!")


def main(output_csv_path: str) -> None:
    """Entry point for synchronous execution."""
    asyncio.run(async_main(output_csv_path))


if __name__ == "__main__":
    main("quotes.csv")
