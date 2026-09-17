import json
import requests


def _get_param(env, key, default=False):
    return env["ir.config_parameter"].sudo().get_str(
        "ai_dropshipping_assistant.%s" % key,
        default,
    )


def _extract_openai_response_text(data):
    if data.get("output_text"):
        return data["output_text"]

    for item in data.get("output", []):
        for content in item.get("content", []):
            if content.get("type") in ("output_text", "text") and content.get("text"):
                return content["text"]

    return None


def _safe_json_loads(text):
    if not text:
        raise Exception("AI returned empty response.")

    text = text.strip()

    if text.startswith("```"):
        text = text.replace("```json", "").replace("```", "").strip()

    try:
        return json.loads(text)
    except Exception:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            return json.loads(text[start:end + 1])

        raise Exception("AI returned invalid JSON: %s" % text[:1000])


def _call_openai_json(env, prompt, schema_name, schema):
    api_key = _get_param(env, "openai_api_key")
    model = _get_param(env, "openai_model", "gpt-4.1-mini")

    if not api_key:
        raise Exception("OpenAI API Key is not configured.")

    payload = {
        "model": model,
        "input": prompt,
        "temperature": 0.1,
        "text": {
            "format": {
                "type": "json_schema",
                "name": schema_name,
                "strict": True,
                "schema": schema,
            }
        },
    }

    response = requests.post(
        "https://api.openai.com/v1/responses",
        headers={
            "Authorization": "Bearer %s" % api_key,
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=60,
    )

    if response.status_code >= 400:
        raise Exception("OpenAI Error %s: %s" % (response.status_code, response.text[:1500]))

    data = response.json()
    text = _extract_openai_response_text(data)

    return _safe_json_loads(text)


def _normalize_gemini_model(model):
    model = (model or "gemini-2.5-flash").strip()

    if model.startswith("models/"):
        model = model.replace("models/", "", 1)

    return model


def _call_gemini_json(env, prompt):
    api_key = _get_param(env, "gemini_api_key")
    model = _normalize_gemini_model(
        _get_param(env, "gemini_model", "gemini-2.5-flash")
    )

    if not api_key:
        raise Exception("Gemini API Key is not configured.")

    url = "https://generativelanguage.googleapis.com/v1beta/models/%s:generateContent?key=%s" % (
        model,
        api_key,
    )

    gemini_prompt = """
Return ONLY valid JSON.
Do not use markdown.
Do not wrap the response in ```json.
Do not add explanations.

%s
""" % prompt

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": gemini_prompt}
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.1
        }
    }

    response = requests.post(
        url,
        headers={"Content-Type": "application/json"},
        json=payload,
        timeout=60,
    )

    if response.status_code >= 400:
        raise Exception("Gemini Error %s: %s" % (response.status_code, response.text[:1500]))

    data = response.json()

    try:
        text = data["candidates"][0]["content"]["parts"][0]["text"]
    except Exception:
        raise Exception("Gemini returned invalid response: %s" % json.dumps(data)[:1500])

    return _safe_json_loads(text)


def _call_ai_json(env, prompt, schema_name, schema):
    provider = _get_param(env, "ai_provider", "openai")

    if provider == "openai":
        return _call_openai_json(env, prompt, schema_name, schema)

    if provider == "gemini":
        return _call_gemini_json(env, prompt)

    raise Exception("Unsupported AI provider: %s" % provider)


def _clean_content_source(description):
    if not description:
        return ""

    if isinstance(description, dict):
        data = description
    else:
        try:
            data = json.loads(description)
        except Exception:
            return str(description)[:12000]

    cleaned = {
        "title": data.get("title", ""),
        "description": data.get("description", ""),
        "image_url": data.get("image_url", ""),
        "availability": data.get("availability", ""),
        "currency": data.get("currency", ""),
    }

    return json.dumps(cleaned, ensure_ascii=False, indent=2)


def validate_price_candidates(env, url="", title="", price_payload=None, page_summary="", admin_note=""):
    price_payload = price_payload or {}
    candidates = price_payload.get("candidates") or []

    safe_candidates = []
    for index, item in enumerate(candidates[:30]):
        safe_candidates.append({
            "index": index,
            "price": item.get("price"),
            "currency": item.get("currency"),
            "source": item.get("source"),
            "score": item.get("score"),
            "is_rejected": item.get("is_rejected"),
            "reject_reason": item.get("reject_reason"),
            "key": item.get("key"),
            "context": item.get("context"),
        })

    prompt = """
You are a strict e-commerce product price validator.

Your task:
Select the correct current selling price for the MAIN product only.

Rules:
- Choose a price ONLY from price_candidates.
- Never invent a price.
- Never estimate a price.
- If no candidate is clearly valid, return price 0.
- Ignore shipping, delivery, tax, coupon, voucher, discount amount, reward points, installment, monthly payment, old crossed-out price, related products, recommended products, bundles, ads, and footer/header prices.
- Prefer final/current/sale price over old/list/original price.
- If a candidate is marked is_rejected=true, use it only if the rejection looks clearly wrong.
- If candidates conflict and evidence is weak, return price 0.
- Currency must come from the selected candidate.
- selected_candidate_index must be the selected candidate index, or -1 if no valid price is selected.
- Confidence:
  - high: price is clearly current main product price
  - medium: likely current main product price
  - low: weak evidence or noisy page
- Return valid JSON only.

Product URL:
%s

Known product title:
%s

Admin instruction:
%s

Rule-based best candidate:
%s

Price candidates:
%s

Page summary:
%s

Return exactly:
{
  "price": 0,
  "currency": "EUR",
  "selected_candidate_index": -1,
  "reason": "string",
  "confidence": "low"
}
""" % (
        url or "",
        title or "",
        admin_note or "",
        json.dumps(price_payload.get("selected_candidate") or {}, ensure_ascii=False)[:2000],
        json.dumps(safe_candidates, ensure_ascii=False)[:12000],
        page_summary or "",
    )

    schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "price": {"type": "number"},
            "currency": {"type": "string"},
            "selected_candidate_index": {"type": "integer"},
            "reason": {"type": "string"},
            "confidence": {
                "type": "string",
                "enum": ["high", "medium", "low"],
            },
        },
        "required": [
            "price",
            "currency",
            "selected_candidate_index",
            "reason",
            "confidence",
        ],
    }

    return _call_ai_json(env, prompt, "price_candidate_validation", schema)


def extract_product_data(env, html, url="", admin_note="", price_payload=None):
    default_note = """
Extract only real product data from the page.
Do not invent missing data.
If price is unknown, return 0.
If image is unknown, return empty string.
"""

    instruction = admin_note or default_note
    price_payload = price_payload or {}

    prompt = """
You are an expert e-commerce product data extractor.

Extract product data from the provided page content.

Rules:
- Extract the main product only.
- Ignore recommended products, related products, ads, footer, header, navigation, bundles, and sponsored items.
- Do not invent missing data.
- image_url must be the main product image if available.
- If image is unknown, return an empty string.
- description should extract real product details if available.
- If no clear description exists, return an empty string.
- Do not create marketing copy here. This step is extraction only.
- availability must be one of: in_stock, out_of_stock, unknown.
- confidence must be one of: high, medium, low.

Price rules:
- Prefer the provided validated/rule-based price payload.
- If price candidates exist, choose only a price supported by those candidates.
- Never guess or estimate a price without evidence.
- Ignore shipping fees, delivery fees, tax notes, discount percentages, installment prices, coupon amounts, points, rewards, crossed-out old prices, recommended products, and related products.
- Prefer current sale/final price over old/original/list price.
- If price is unknown, hidden, missing, or unsupported by evidence, return 0.
- Currency must be ISO code like EUR, USD, GBP.

Product URL:
%s

Admin instruction:
%s

Price payload:
%s

Page content:
%s

Return JSON exactly like this:
{
  "title": "string",
  "price": 0,
  "currency": "EUR",
  "image_url": "string",
  "description": "string",
  "availability": "unknown",
  "confidence": "medium"
}
""" % (
        url or "",
        instruction,
        json.dumps(price_payload, ensure_ascii=False)[:10000],
        html or "",
    )

    schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "title": {"type": "string"},
            "price": {"type": "number"},
            "currency": {"type": "string"},
            "image_url": {"type": "string"},
            "description": {"type": "string"},
            "availability": {
                "type": "string",
                "enum": ["in_stock", "out_of_stock", "unknown"],
            },
            "confidence": {
                "type": "string",
                "enum": ["high", "medium", "low"],
            },
        },
        "required": [
            "title",
            "price",
            "currency",
            "image_url",
            "description",
            "availability",
            "confidence",
        ],
    }

    return _call_ai_json(env, prompt, "product_extract", schema)


def generate_product_content(env, title, description="", url="", admin_note=""):
    default_note = """
Write clean e-commerce product content.
Keep the original product language.
Keep the title close to the original.
Do not invent technical details.
Do not exaggerate.
Make the content suitable for a professional online store.
"""

    instruction = admin_note or default_note
    clean_description = _clean_content_source(description)

    prompt = """
You are a professional e-commerce product content writer.

Your task:
Create ready-to-publish product content for an online store.

Rules for title:
- Keep the product title close to the original title.
- You may clean grammar and remove marketplace noise.
- Do not rewrite the title completely.
- Do not make the title too short.
- Keep it descriptive and suitable for ecommerce.

Rules for description:
- Write in the same language as the product title or available product text.
- If real product details are available, use them.
- If product details are missing, create a safe generic product description based only on the title and visible clues.
- Write a richer ecommerce description.
- Description should be around 120 to 220 words when enough information is available.
- Include 4 to 7 useful bullet points.
- Do not invent exact technical specifications, dimensions, materials, certifications, warranty, model numbers, compatibility, or performance claims unless clearly provided.
- Do not mention supplier, marketplace, AliExpress, Temu, Shein, Amazon, scraping, AI, or the source URL.
- Do not mention price.
- Do not use exaggerated claims.
- Make the content suitable for an Odoo website product page.
- Use clean HTML only for the description field.
- short_description must be 1 or 2 short sentences.
- SEO title must be concise.
- SEO description must be attractive but realistic.
- Return only valid JSON.

Product URL:
%s

Product title:
%s

Available product data:
%s

Admin instruction:
%s

Return JSON exactly like this:
{
  "title": "string",
  "short_description": "string",
  "description": "HTML string",
  "seo_title": "string",
  "seo_description": "string"
}
""" % (url or "", title or "", clean_description or "", instruction)

    schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "title": {"type": "string"},
            "short_description": {"type": "string"},
            "description": {"type": "string"},
            "seo_title": {"type": "string"},
            "seo_description": {"type": "string"},
        },
        "required": [
            "title",
            "short_description",
            "description",
            "seo_title",
            "seo_description",
        ],
    }

    return _call_ai_json(env, prompt, "product_content", schema)


def rewrite_product_text(env, title, description, target_language=False):
    admin_note = ""

    if target_language:
        admin_note = "Rewrite and translate the product content into %s." % target_language

    return generate_product_content(
        env=env,
        title=title,
        description=description,
        admin_note=admin_note,
    )