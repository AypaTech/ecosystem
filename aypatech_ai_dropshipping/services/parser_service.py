from bs4 import BeautifulSoup
import re


def parse_product(html):
    soup = BeautifulSoup(html, "html.parser")

    title = soup.find("h1")
    title = title.text.strip() if title else None

    text = soup.get_text(" ", strip=True)

    price = None
    match = re.search(r"(\d+[.,]?\d*)\s*€", text)
    if match:
        price = float(match.group(1).replace(",", "."))

    return {
        "title": title,
        "description": "",
        "price": price,
        "currency": "EUR",
    }