import csv
import logging
import sys
from dataclasses import astuple, dataclass, fields
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup, Tag


BASE_URL = "https://quotes.toscrape.com/"


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


def get_all_quotes() -> list[Quote]:
    """Collect all quotes from all pages."""
    current_url = BASE_URL
    all_quotes = []
    page_number = 1

    while current_url:
        logging.info(f"Parsing page #{page_number}")
        page_content = requests.get(current_url).content
        page_soup = BeautifulSoup(page_content, "html.parser")

        page_quotes = get_single_page_quotes(page_soup)
        all_quotes.extend(page_quotes)
        logging.info(f"Found {len(page_quotes)} quotes on page #{page_number}")

        current_url = get_next_page_url(page_soup)
        page_number += 1

    logging.info(f"Total quotes collected: {len(all_quotes)}")
    return all_quotes


def write_quotes_to_csv(quotes: list[Quote], output_path: str) -> None:
    """Write quotes to a CSV file."""
    with open(output_path, "w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(QUOTE_FIELDS)
        writer.writerows([astuple(quote) for quote in quotes])

    logging.info(f"Quotes have been saved to {output_path}")


def main(output_csv_path: str) -> None:
    """Scrape all quotes and save them to a CSV file."""
    logging.info("Starting quotes scraping...")
    quotes = get_all_quotes()
    write_quotes_to_csv(quotes, output_csv_path)
    logging.info("Scraping complete!")


if __name__ == "__main__":
    main("quotes.csv")
