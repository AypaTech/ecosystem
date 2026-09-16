import json
import re
from bs4 import BeautifulSoup


CURRENCY_SYMBOLS = {
    "€": "EUR",
    "$": "USD",
    "US$": "USD",
    "£": "GBP",
}

CURRENCY_WORDS = {
    "eur": "EUR",
    "euro": "EUR",
    "euros": "EUR",
    "usd": "USD",
    "dollar": "USD",
    "dollars": "USD",
    "gbp": "GBP",
    "pound": "GBP",
    "pounds": "GBP",
}

BAD_CONTEXT_WORDS = [
    "shipping", "delivery", "tax", "fee", "coupon", "voucher", "discount",
    "save", "saving", "points", "reward", "installment", "monthly",
    "klarna", "paypal", "afterpay", "zip", "delivery fee",
    "spedizione", "consegna", "iva", "sconto", "coupon", "codice",
    "risparmia", "punti", "premio", "rate", "mensile",
    "livraison", "remise", "expédition",
]

OLD_PRICE_WORDS = [
    "old price", "original price", "list price", "was", "before",
    "prezzo originale", "prezzo precedente", "prima", "era",
    "ancien prix", "prix initial",
]

GOOD_CONTEXT_WORDS = [
    "price", "sale price", "current price", "final price", "now",
    "our price", "special price", "product price",
    "prezzo", "prezzo attuale", "prezzo finale", "ora",
    "prix", "prix actuel", "prix final",
    "saleprice", "currentprice", "finalprice", "priceamount",
    "unitprice", "offerprice",
]

PRICE_KEY_HINTS = [
    "price", "salePrice", "sale_price", "currentPrice", "current_price",
    "finalPrice", "final_price", "priceAmount", "price_amount",
    "unitPrice", "unit_price", "amount", "value",
    "minPrice", "maxPrice", "lowPrice", "highPrice",
]

TITLE_KEY_HINTS = [
    "title", "name", "productName", "product_name",
]


def collect_price_candidates(html, url="", title="", max_candidates=30):
    soup = BeautifulSoup(html or "", "html.parser")

    candidates = []

    candidates.extend(_candidates_from_json_ld(soup))
    candidates.extend(_candidates_from_meta(soup))
    candidates.extend(_candidates_from_scripts(soup))
    candidates.extend(_candidates_from_visible_text(soup))

    candidates = _deduplicate_candidates(candidates)
    candidates = _score_candidates(candidates, title=title, url=url)

    candidates.sort(key=lambda item: item.get("score", 0), reverse=True)

    best = _select_best_candidate(candidates)

    return {
        "best_price": best.get("price") if best else 0.0,
        "currency": best.get("currency") if best else "EUR",
        "confidence": _confidence_from_score(best.get("score", 0) if best else 0),
        "selected_candidate": best or {},
        "candidates": candidates[:max_candidates],
    }


def _clean_price(value):
    if value is None:
        return None

    value = str(value).strip().replace("\xa0", " ")

    if not re.search(r"\d", value):
        return None

    value = re.sub(r"[^\d,\.]", "", value)

    if not value:
        return None

    if "," in value and "." in value:
        if value.rfind(",") > value.rfind("."):
            value = value.replace(".", "").replace(",", ".")
        else:
            value = value.replace(",", "")
    else:
        value = value.replace(",", ".")

    match = re.search(r"\d+(\.\d+)?", value)
    if not match:
        return None

    try:
        price = float(match.group())
    except Exception:
        return None

    if price <= 0:
        return None

    if price > 50000:
        return None

    return price


def _detect_currency(text, default="EUR"):
    text = text or ""
    lowered = text.lower()

    for symbol, code in CURRENCY_SYMBOLS.items():
        if symbol in text:
            return code

    for word, code in CURRENCY_WORDS.items():
        if re.search(r"\b%s\b" % re.escape(word), lowered):
            return code

    return default


def _make_candidate(price, currency="EUR", source="", context="", raw_value="", key="", extra_score=0):
    price = _clean_price(price)
    if price is None:
        return None

    context = _compact_text(context)

    return {
        "price": price,
        "currency": currency or _detect_currency(context),
        "source": source,
        "context": context[:600],
        "raw_value": str(raw_value or "")[:200],
        "key": key or "",
        "score": int(extra_score or 0),
        "is_rejected": False,
        "reject_reason": "",
    }


def _compact_text(text):
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _candidates_from_json_ld(soup):
    candidates = []

    for script in soup.find_all("script", type="application/ld+json"):
        raw = script.string or script.get_text() or ""
        data = _safe_json(raw)
        if data is None:
            continue

        products = []
        _find_json_ld_products(data, products)

        for product in products:
            offers = product.get("offers")
            if isinstance(offers, list):
                offer_items = offers
            elif isinstance(offers, dict):
                offer_items = [offers]
            else:
                offer_items = []

            for offer in offer_items:
                if not isinstance(offer, dict):
                    continue

                currency = (
                    offer.get("priceCurrency")
                    or offer.get("currency")
                    or product.get("priceCurrency")
                    or "EUR"
                )

                for key in ["price", "salePrice", "lowPrice", "highPrice"]:
                    if offer.get(key) is None:
                        continue

                    candidate = _make_candidate(
                        price=offer.get(key),
                        currency=currency,
                        source="json_ld",
                        context=json.dumps({
                            "product_name": product.get("name"),
                            "offer": offer,
                        }, ensure_ascii=False)[:1000],
                        raw_value=offer.get(key),
                        key=key,
                        extra_score=90,
                    )
                    if candidate:
                        candidates.append(candidate)

    return candidates


def _find_json_ld_products(data, products):
    if isinstance(data, list):
        for item in data:
            _find_json_ld_products(item, products)
        return

    if not isinstance(data, dict):
        return

    item_type = data.get("@type")
    is_product = item_type == "Product" or (
        isinstance(item_type, list) and "Product" in item_type
    )

    if is_product:
        products.append(data)

    graph = data.get("@graph")
    if isinstance(graph, list):
        for item in graph:
            _find_json_ld_products(item, products)


def _candidates_from_meta(soup):
    candidates = []

    amount_attrs = [
        {"property": "product:price:amount"},
        {"property": "og:price:amount"},
        {"property": "product:sale_price:amount"},
        {"name": "twitter:data1"},
    ]

    currency = _get_meta_currency(soup) or "EUR"

    for attrs in amount_attrs:
        for tag in soup.find_all("meta", attrs=attrs):
            value = tag.get("content")
            if not value:
                continue

            candidate = _make_candidate(
                price=value,
                currency=currency or _detect_currency(value),
                source="meta",
                context=str(tag),
                raw_value=value,
                key=str(attrs),
                extra_score=80,
            )
            if candidate:
                candidates.append(candidate)

    return candidates


def _get_meta_currency(soup):
    for attrs in [
        {"property": "product:price:currency"},
        {"property": "og:price:currency"},
        {"property": "product:sale_price:currency"},
    ]:
        tag = soup.find("meta", attrs=attrs)
        if tag and tag.get("content"):
            return tag["content"].strip().upper()
    return None


def _candidates_from_scripts(soup):
    candidates = []

    for script in soup.find_all("script"):
        raw = script.string or script.get_text() or ""
        if not raw or len(raw) < 20:
            continue

        if len(raw) > 400000:
            raw = raw[:400000]

        script_candidates = []

        json_objects = _extract_json_objects_from_script(raw)
        for obj in json_objects[:20]:
            _walk_json_for_prices(obj, script_candidates)

        script_candidates.extend(_regex_prices_with_context(raw, source="script_text"))

        candidates.extend(script_candidates[:40])

    return candidates


def _extract_json_objects_from_script(raw):
    result = []

    raw = raw.strip()

    direct = _safe_json(raw)
    if direct is not None:
        result.append(direct)

    patterns = [
        r'<script[^>]*id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>',
        r'window\.__INITIAL_STATE__\s*=\s*({.*?});',
        r'window\.__APOLLO_STATE__\s*=\s*({.*?});',
        r'window\.__PRELOADED_STATE__\s*=\s*({.*?});',
        r'__INITIAL_STATE__\s*=\s*({.*?});',
        r'preloadedState\s*=\s*({.*?});',
    ]

    for pattern in patterns:
        for match in re.findall(pattern, raw, flags=re.DOTALL):
            data = _safe_json(match)
            if data is not None:
                result.append(data)

    return result


def _safe_json(text):
    if not text:
        return None

    text = text.strip()

    try:
        return json.loads(text)
    except Exception:
        pass

    return None


def _walk_json_for_prices(data, candidates, path="", parent_context=None):
    if isinstance(data, list):
        for index, item in enumerate(data[:200]):
            _walk_json_for_prices(
                item,
                candidates,
                path="%s[%s]" % (path, index),
                parent_context=parent_context,
            )
        return

    if not isinstance(data, dict):
        return

    compact = {}
    for key in TITLE_KEY_HINTS + PRICE_KEY_HINTS + ["currency", "priceCurrency"]:
        if key in data:
            compact[key] = data.get(key)

    context = json.dumps(compact or data, ensure_ascii=False)[:1000]

    currency = (
        data.get("currency")
        or data.get("priceCurrency")
        or data.get("currencyCode")
        or _detect_currency(context)
    )

    for key, value in data.items():
        key_str = str(key)

        if _key_looks_like_price(key_str):
            candidate = _make_candidate(
                price=value,
                currency=currency,
                source="script_json",
                context=context,
                raw_value=value,
                key="%s.%s" % (path, key_str),
                extra_score=60,
            )
            if candidate:
                candidates.append(candidate)

    for key, value in data.items():
        _walk_json_for_prices(
            value,
            candidates,
            path="%s.%s" % (path, key),
            parent_context=context,
        )


def _key_looks_like_price(key):
    lowered = key.lower()

    if "price" in lowered:
        return True

    return lowered in [
        "amount", "value", "sale", "retail", "subtotal",
    ]


def _candidates_from_visible_text(soup):
    text = soup.get_text(" ", strip=True)
    return _regex_prices_with_context(text, source="visible_text")


def _regex_prices_with_context(text, source="visible_text"):
    candidates = []

    if not text:
        return candidates

    text = _compact_text(text)

    patterns = [
        r"(?P<currency>€|£|\$|US\$)\s*(?P<amount>\d{1,5}(?:[.,]\d{2})?)",
        r"(?P<amount>\d{1,5}(?:[.,]\d{2})?)\s*(?P<currency>€|£|\$|US\$)",
        r"(?P<currency>EUR|USD|GBP)\s*(?P<amount>\d{1,5}(?:[.,]\d{2})?)",
        r"(?P<amount>\d{1,5}(?:[.,]\d{2})?)\s*(?P<currency>EUR|USD|GBP)",
    ]

    for pattern in patterns:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            amount = match.group("amount")
            currency_raw = match.group("currency")
            start = max(0, match.start() - 160)
            end = min(len(text), match.end() + 160)
            context = text[start:end]

            candidate = _make_candidate(
                price=amount,
                currency=_detect_currency(currency_raw),
                source=source,
                context=context,
                raw_value=match.group(0),
                key="regex",
                extra_score=35,
            )
            if candidate:
                candidates.append(candidate)

    return candidates


def _deduplicate_candidates(candidates):
    seen = set()
    result = []

    for item in candidates:
        if not item:
            continue

        price = round(float(item.get("price") or 0), 2)
        currency = item.get("currency") or "EUR"
        context_key = _compact_text(item.get("context", ""))[:80].lower()

        key = (price, currency, item.get("source"), context_key)
        if key in seen:
            continue

        seen.add(key)
        result.append(item)

    return result


def _score_candidates(candidates, title="", url=""):
    title_tokens = _important_tokens(title)
    url_lower = (url or "").lower()

    for item in candidates:
        score = int(item.get("score") or 0)
        context = (item.get("context") or "").lower()
        key = (item.get("key") or "").lower()
        source = item.get("source") or ""
        price = float(item.get("price") or 0)

        if price < 1:
            item["is_rejected"] = True
            item["reject_reason"] = "price_too_low"
            item["score"] = 0
            continue

        if source in ("json_ld", "meta"):
            score += 25

        if source == "script_json":
            score += 10

        if any(word in context for word in GOOD_CONTEXT_WORDS):
            score += 20

        if any(word in key for word in ["saleprice", "finalprice", "currentprice"]):
            score += 25

        if any(word in key for word in ["oldprice", "listprice", "originalprice"]):
            score -= 35

        if any(word in context for word in OLD_PRICE_WORDS):
            score -= 25

        bad_hits = [word for word in BAD_CONTEXT_WORDS if word in context]
        if bad_hits:
            score -= 45
            item["is_rejected"] = True
            item["reject_reason"] = "bad_context:%s" % ",".join(bad_hits[:3])

        title_hit_count = 0
        for token in title_tokens:
            if token in context:
                title_hit_count += 1

        if title_hit_count:
            score += min(30, title_hit_count * 6)

        if "temu" in url_lower or "shein" in url_lower:
            if source == "script_json":
                score += 15

        if price > 10000:
            score -= 30

        item["score"] = max(0, int(score))

    return candidates


def _important_tokens(title):
    title = (title or "").lower()
    words = re.findall(r"[a-zA-Z0-9À-ÿ]{4,}", title)
    stop = {
        "with", "from", "this", "that", "and", "the", "for",
        "con", "per", "del", "della", "dello", "alla",
    }
    return [word for word in words if word not in stop][:12]


def _select_best_candidate(candidates):
    valid = [
        item for item in candidates
        if not item.get("is_rejected") and item.get("score", 0) >= 55
    ]

    if not valid:
        return None

    return valid[0]


def _confidence_from_score(score):
    if score >= 90:
        return "high"
    if score >= 65:
        return "medium"
    if score >= 55:
        return "low"
    return "failed"