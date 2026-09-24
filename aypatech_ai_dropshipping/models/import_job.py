import base64
import json
import re
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from odoo import fields, models


class DropshippingImportJob(models.Model):
    _name = "dropshipping.import.job"
    _description = "Dropshipping Import Job"

    name = fields.Char(default="New Import Job")
    url = fields.Char(string="Product URL")

    raw_price = fields.Float(string="Detected Price")
    estimated_price = fields.Float(string="Estimated Price")
    confirmed_price = fields.Float(string="Confirmed Supplier Price")
    raw_currency = fields.Char(string="Currency")

    margin_percent = fields.Float(string="Margin %", default=20.0)
    selling_price = fields.Float(string="Selling Price")

    image_url = fields.Char(string="Detected Image URL")
    manual_image_url = fields.Char(string="Manual Image URL")
    image_preview = fields.Image(string="Image Preview", max_width=512, max_height=512)

    image_ids = fields.One2many(
        "dropshipping.import.job.image",
        "job_id",
        string="Product Images",
    )

    ai_used = fields.Boolean(string="AI Used", readonly=True)

    ai_confidence = fields.Selection([
        ("high", "High"),
        ("medium", "Medium"),
        ("low", "Low"),
    ], string="AI Confidence", readonly=True)

    ai_raw_response = fields.Text(string="AI Raw Response", readonly=True)
    ai_admin_note = fields.Text(string="AI Instruction / Admin Note")

    ai_generated_title = fields.Char(string="AI Generated Title")
    ai_generated_short_description = fields.Text(string="AI Short Description")
    ai_generated_description = fields.Html(string="AI Website Description")
    ai_generated_seo_title = fields.Char(string="AI SEO Title")
    ai_generated_seo_description = fields.Text(string="AI SEO Description")
    ai_content_confirmed = fields.Boolean(string="AI Content Confirmed")

    product_tmpl_id = fields.Many2one("product.template", string="Created Product", readonly=True)
    product_created = fields.Boolean(string="Product Created", readonly=True)

    price_confidence = fields.Selection([
        ("high", "High"),
        ("medium", "Medium"),
        ("low", "Low"),
        ("failed", "Failed"),
    ], string="Price Confidence")

    price_status = fields.Selection([
        ("green", "🟢 Green"),
        ("yellow", "🟡 Yellow"),
        ("red", "🔴 Red"),
    ], string="Price Status")

    is_price_confirmed = fields.Boolean(string="Price Confirmed")
    error_message = fields.Text(string="Error Message")

    state = fields.Selection([
        ("draft", "Draft"),
        ("done", "Done"),
        ("failed", "Failed"),
    ], default="draft")

    def action_fetch_product(self):
        for rec in self:
            rec.error_message = False
            rec.is_price_confirmed = False
            rec.confirmed_price = 0.0
            rec.selling_price = 0.0
            rec.image_url = False
            rec.image_preview = False
            rec.ai_used = False
            rec.ai_raw_response = False
            rec.image_ids.unlink()

            if not rec.url:
                rec._set_failed("Product URL is empty.")
                continue

            try:
                rec.url = rec._normalize_product_url(rec.url)

                html = rec._fetch_page_html(use_browser_fallback=True)
                soup = BeautifulSoup(html, "html.parser")

                title = rec._get_title(soup) or rec._get_title_from_url(rec.url)
                rec.name = title or rec.name

                if rec.manual_image_url:
                    image_urls = [rec._normalize_image_url(rec.manual_image_url, rec.url)]
                else:
                    image_urls = rec._get_image_urls(soup, rec.url)

                rec._save_image_urls(image_urls)

                from odoo.addons.ai_dropshipping_assistant.services.price_candidate_service import (
                    collect_price_candidates,
                )

                price_payload = collect_price_candidates(
                    html=html,
                    url=rec.url,
                    title=title,
                )

                if not price_payload.get("candidates"):
                    rendered_html = rec._fetch_rendered_html_safely()
                    if rendered_html:
                        html = rendered_html
                        soup = BeautifulSoup(html, "html.parser")

                        better_title = rec._get_title(soup)
                        if better_title:
                            title = better_title
                            rec.name = better_title

                        price_payload = collect_price_candidates(
                            html=html,
                            url=rec.url,
                            title=title,
                        )

                        if not rec.image_ids:
                            if rec.manual_image_url:
                                image_urls = [rec._normalize_image_url(rec.manual_image_url, rec.url)]
                            else:
                                image_urls = rec._get_image_urls(soup, rec.url)
                            rec._save_image_urls(image_urls)

                price_data = rec._price_data_from_payload(price_payload)
                estimated_price = price_payload.get("best_price") or 0.0

                if not price_data:
                    rec.raw_price = 0.0
                    rec.estimated_price = estimated_price or 0.0
                    rec.raw_currency = price_payload.get("currency") if estimated_price else False
                    rec.ai_raw_response = json.dumps({
                        "price_debug": price_payload,
                    }, ensure_ascii=False, indent=2)
                    rec._set_failed("Reliable price not found. You can use AI Extract or enter manually.")
                    continue

                rec.raw_price = price_data["price"]
                rec.estimated_price = estimated_price or price_data["price"]
                rec.raw_currency = price_data["currency"]
                rec.price_confidence = price_data["confidence"]
                rec.price_status = rec._get_price_status(price_data["confidence"])
                rec.ai_raw_response = json.dumps({
                    "price_debug": price_payload,
                }, ensure_ascii=False, indent=2)
                rec.error_message = False
                rec.state = "done"

            except Exception as error:
                rec.name = rec.name if rec.name != "New Import Job" else rec._get_title_from_url(rec.url)
                rec._set_failed(str(error))

    def action_ai_extract(self):
        for rec in self:
            if not rec.url:
                rec.error_message = "Product URL is empty."
                continue

            try:
                rec.url = rec._normalize_product_url(rec.url)

                ai_enabled = self.env["ir.config_parameter"].sudo().get_param(
                    "ai_dropshipping_assistant.ai_enabled"
                )

                if ai_enabled not in ("True", "true", "1"):
                    rec.error_message = "AI API is disabled. Enable it from Settings > AI Dropshipping."
                    continue

                html_full = rec._fetch_page_html(use_browser_fallback=True)
                soup = BeautifulSoup(html_full, "html.parser")

                page_title = rec._get_title(soup) or rec.name or rec._get_title_from_url(rec.url)
                page_text = soup.get_text(" ", strip=True)

                from odoo.addons.ai_dropshipping_assistant.services.price_candidate_service import (
                    collect_price_candidates,
                )
                from odoo.addons.ai_dropshipping_assistant.services.ai_service import (
                    extract_product_data,
                    validate_price_candidates,
                )

                price_payload = collect_price_candidates(
                    html=html_full,
                    url=rec.url,
                    title=page_title,
                )

                if not price_payload.get("candidates"):
                    rendered_html = rec._fetch_rendered_html_safely()
                    if rendered_html:
                        html_full = rendered_html
                        soup = BeautifulSoup(html_full, "html.parser")
                        page_text = soup.get_text(" ", strip=True)

                        better_title = rec._get_title(soup)
                        if better_title:
                            page_title = better_title
                            rec.name = better_title

                        price_payload = collect_price_candidates(
                            html=html_full,
                            url=rec.url,
                            title=page_title,
                        )

                        if not rec.image_ids:
                            if rec.manual_image_url:
                                image_urls = [rec._normalize_image_url(rec.manual_image_url, rec.url)]
                            else:
                                image_urls = rec._get_image_urls(soup, rec.url)
                            rec._save_image_urls(image_urls)

                ai_price_result = validate_price_candidates(
                    env=self.env,
                    url=rec.url,
                    title=page_title,
                    price_payload=price_payload,
                    page_summary=page_text[:4000],
                    admin_note=rec.ai_admin_note,
                )

                if ai_price_result.get("price") and float(ai_price_result.get("price")) > 0:
                    price_payload["best_price"] = float(ai_price_result.get("price"))
                    price_payload["currency"] = (
                        ai_price_result.get("currency")
                        or price_payload.get("currency")
                        or "EUR"
                    )
                    price_payload["confidence"] = ai_price_result.get("confidence") or "medium"

                price_payload["ai_validation"] = ai_price_result

                ai_input = """
PRODUCT URL:
%s

KNOWN PRODUCT TITLE:
%s

VISIBLE PAGE TEXT:
%s

RAW HTML:
%s
""" % (
                    rec.url or "",
                    page_title or "",
                    page_text[:12000],
                    html_full[:18000],
                )

                ai_result = extract_product_data(
                    env=self.env,
                    html=ai_input,
                    url=rec.url,
                    admin_note=rec.ai_admin_note,
                    price_payload=price_payload,
                )

                if price_payload.get("best_price") and float(price_payload.get("best_price")) > 0:
                    ai_result["price"] = float(price_payload.get("best_price"))
                    ai_result["currency"] = (
                        price_payload.get("currency")
                        or ai_result.get("currency")
                        or "EUR"
                    )
                    ai_result["confidence"] = (
                        price_payload.get("confidence")
                        or ai_result.get("confidence")
                        or "medium"
                    )

                ai_result["price_debug"] = {
                    "rule_based": price_payload,
                    "ai_validation": ai_price_result,
                }

                rec.ai_raw_response = json.dumps(ai_result, ensure_ascii=False, indent=2)
                rec._apply_ai_result(ai_result)
                rec.ai_used = True
                rec.state = "done"

            except Exception as error:
                rec._set_failed("AI Extract Error: %s" % str(error))

    def action_generate_ai_content(self):
        for rec in self:
            try:
                ai_enabled = self.env["ir.config_parameter"].sudo().get_param(
                    "ai_dropshipping_assistant.ai_enabled"
                )

                if ai_enabled not in ("True", "true", "1"):
                    rec.error_message = "AI API is disabled. Enable it from Settings > AI Dropshipping."
                    continue

                from odoo.addons.ai_dropshipping_assistant.services.ai_service import (
                    generate_product_content,
                )

                result = generate_product_content(
                    env=self.env,
                    title=rec.name,
                    description=rec.ai_raw_response or "",
                    url=rec.url,
                    admin_note=rec.ai_admin_note,
                )

                rec.ai_generated_title = result.get("title")
                rec.ai_generated_short_description = result.get("short_description")
                rec.ai_generated_description = result.get("description")
                rec.ai_generated_seo_title = result.get("seo_title")
                rec.ai_generated_seo_description = result.get("seo_description")
                rec.ai_content_confirmed = False
                rec.error_message = False

            except Exception as error:
                rec.error_message = "AI Content Error: %s" % str(error)

    def action_confirm_ai_content(self):
        for rec in self:
            if not rec.ai_generated_title and not rec.ai_generated_description:
                rec.error_message = "No AI content available to confirm."
                continue

            rec.ai_content_confirmed = True
            rec.error_message = False

    def action_reset_ai_content_confirmation(self):
        for rec in self:
            rec.ai_content_confirmed = False

    def _generate_ai_content_if_missing(self):
        self.ensure_one()

        if self.ai_generated_description:
            return

        ai_enabled = self.env["ir.config_parameter"].sudo().get_param(
            "ai_dropshipping_assistant.ai_enabled"
        )

        if ai_enabled not in ("True", "true", "1"):
            return

        try:
            from odoo.addons.ai_dropshipping_assistant.services.ai_service import (
                generate_product_content,
            )

            result = generate_product_content(
                env=self.env,
                title=self.name,
                description=self.ai_raw_response or "",
                url=self.url,
                admin_note=self.ai_admin_note,
            )

            self.ai_generated_title = result.get("title")
            self.ai_generated_short_description = result.get("short_description")
            self.ai_generated_description = result.get("description")
            self.ai_generated_seo_title = result.get("seo_title")
            self.ai_generated_seo_description = result.get("seo_description")

        except Exception as error:
            self.error_message = "AI Content Auto Generate Error: %s" % str(error)

    def _apply_ai_result(self, data):
        self.ensure_one()

        title = data.get("title")
        price = data.get("price")
        currency = data.get("currency") or "EUR"
        image_url = data.get("image_url")
        confidence = data.get("confidence") or "medium"

        if title:
            self.name = title

        if price and float(price) > 0:
            self.raw_price = float(price)
            self.estimated_price = float(price)
            self.raw_currency = currency
            self.price_confidence = confidence if confidence in ("high", "medium", "low") else "medium"
            self.price_status = self._get_price_status(self.price_confidence)
            self.error_message = False
        else:
            if not self.raw_price and not self.estimated_price:
                self.raw_price = 0.0
                self.estimated_price = 0.0
                self.price_confidence = "failed"
                self.price_status = "red"
                self.error_message = (
                    "AI extracted product data, but price was not found. "
                    "Please enter or confirm price manually."
                )

        if image_url:
            normalized_image_url = self._normalize_image_url(image_url, self.url)
            self.image_url = normalized_image_url

            image_data = self._download_image_as_base64(normalized_image_url)
            if image_data:
                self.image_preview = image_data
                self._save_image_urls([normalized_image_url])
            elif not self.error_message:
                self.error_message = "AI found image URL, but Odoo could not download the image."

        self.ai_confidence = confidence if confidence in ("high", "medium", "low") else "medium"

    def action_download_manual_image(self):
        for rec in self:
            image_url = rec.manual_image_url or rec.image_url
            if not image_url:
                rec.error_message = "Please enter a Manual Image URL first."
                continue

            image_url = rec._normalize_image_url(image_url, rec.url)
            image_data = rec._download_image_as_base64(image_url)

            if image_data:
                rec.image_url = image_url
                rec.image_preview = image_data
                rec._save_image_urls([image_url])
                rec.error_message = False
            else:
                rec.error_message = "Could not download image from the provided URL."

    def action_confirm_price(self):
        for rec in self:
            price = rec.confirmed_price or rec.raw_price or rec.estimated_price
            if price:
                rec.confirmed_price = price
                rec.is_price_confirmed = True
                rec.selling_price = rec._compute_selling_price(price)
                rec.error_message = False
            else:
                rec.is_price_confirmed = False
                rec.error_message = "No price available to confirm."

    def action_reset_confirmation(self):
        for rec in self:
            rec.is_price_confirmed = False
            rec.confirmed_price = 0.0
            rec.selling_price = 0.0

    def action_compute_selling_price(self):
        for rec in self:
            base_price = rec.confirmed_price or rec.raw_price or rec.estimated_price
            if not base_price:
                rec.error_message = "No base price available to compute selling price."
                continue

            rec.selling_price = rec._compute_selling_price(base_price)
            rec.error_message = False

    def action_create_product(self):
        for rec in self:
            if rec.product_tmpl_id:
                rec.error_message = "Product already created."
                continue

            if not rec.is_price_confirmed:
                rec.error_message = "Please confirm the supplier price before creating the product."
                continue

            supplier_price = rec.confirmed_price or rec.raw_price or rec.estimated_price
            if not supplier_price:
                rec.error_message = "No valid supplier price found for product creation."
                continue

            rec._generate_ai_content_if_missing()

            publish_after_create = self.env["ir.config_parameter"].sudo().get_param(
                "ai_dropshipping_assistant.publish_after_create"
            )

            vals = {
                "name": rec.name or rec._get_title_from_url(rec.url) or "Imported Product",
                "type": "consu",
                "list_price": rec.selling_price or rec._compute_selling_price(supplier_price),
                "standard_price": supplier_price,
                "is_published": publish_after_create in ("True", "true", "1"),
                "is_dropshipping_product": True,
                "dropshipping_source_url": rec.url,
                "dropshipping_source_price": supplier_price,
                "dropshipping_source_currency": rec.raw_currency or "EUR",
                "dropshipping_import_job_id": rec.id,
            }

            if rec.ai_generated_title and rec.ai_content_confirmed:
                vals["name"] = rec.ai_generated_title

            if rec.ai_generated_short_description:
                vals["description_sale"] = rec.ai_generated_short_description

            if rec.ai_generated_description:
                vals["website_description"] = rec.ai_generated_description

            if rec.ai_generated_seo_title:
                vals["website_meta_title"] = rec.ai_generated_seo_title

            if rec.ai_generated_seo_description:
                vals["website_meta_description"] = rec.ai_generated_seo_description

            main_image = rec.image_ids.filtered(lambda img: img.is_main and img.image)[:1]
            if main_image:
                vals["image_1920"] = main_image.image
            elif rec.image_preview:
                vals["image_1920"] = rec.image_preview

            product = self.env["product.template"].create(vals)

            rec._create_product_gallery_images(product)

            rec.product_tmpl_id = product.id
            rec.product_created = True
            rec.state = "done"
            rec.error_message = False

    def _create_product_gallery_images(self, product):
        self.ensure_one()

        if not product:
            return

        images = self.image_ids.filtered(lambda img: img.image)
        if not images:
            return

        main_image = images.filtered(lambda img: img.is_main)[:1]

        for img in images:
            if main_image and img.id == main_image.id:
                continue

            self.env["product.image"].create({
                "name": img.name or product.name,
                "product_tmpl_id": product.id,
                "image_1920": img.image,
            })

    def _fetch_page_html(self, use_browser_fallback=True):
        self.ensure_one()

        self.url = self._normalize_product_url(self.url)

        if not self.url:
            raise Exception("Product URL is empty.")

        response = requests.get(
            self.url,
            timeout=25,
            headers=self._get_request_headers(),
            allow_redirects=True,
        )

        if response.status_code < 400 and response.text:
            return response.text

        if use_browser_fallback:
            try:
                html = self._fetch_rendered_html_safely()
                if html:
                    return html
            except Exception as browser_error:
                raise Exception(
                    "Could not download product page. Supplier returned HTTP %s. "
                    "Browser fallback also failed: %s"
                    % (response.status_code, str(browser_error))
                )

        raise Exception(
            "Could not download product page. Supplier returned HTTP %s. "
            "This website may block scraping or require JavaScript/browser rendering."
            % response.status_code
        )

    def _fetch_rendered_html_safely(self):
        self.ensure_one()

        try:
            from odoo.addons.ai_dropshipping_assistant.services.browser_service import (
                fetch_rendered_html,
            )

            html = fetch_rendered_html(self.url)
            return html or False

        except Exception:
            return False

    def _save_image_urls(self, image_urls):
        self.ensure_one()

        if not image_urls:
            return

        existing_urls = set(self.image_ids.mapped("image_url"))
        sequence = len(self.image_ids) * 10

        for image_url in image_urls[:10]:
            if not image_url or image_url in existing_urls:
                continue

            image_data = self._download_image_as_base64(image_url)
            if not image_data:
                continue

            sequence += 10
            is_main = not bool(self.image_ids)

            self.env["dropshipping.import.job.image"].create({
                "job_id": self.id,
                "sequence": sequence,
                "name": "Product Image",
                "image_url": image_url,
                "image": image_data,
                "is_main": is_main,
            })

            if is_main:
                self.image_url = image_url
                self.image_preview = image_data

            existing_urls.add(image_url)

    def _set_failed(self, message):
        self.state = "failed"
        self.price_confidence = "failed"
        self.price_status = "red"
        self.error_message = message

    def _price_data_from_payload(self, price_payload):
        price_payload = price_payload or {}

        price = price_payload.get("best_price")
        if not price or float(price) <= 0:
            return None

        confidence = price_payload.get("confidence") or "low"

        if confidence == "failed":
            return None

        return {
            "price": float(price),
            "currency": price_payload.get("currency") or "EUR",
            "confidence": confidence if confidence in ("high", "medium", "low") else "low",
        }

    def _normalize_product_url(self, url):
        url = (url or "").strip()

        if not url:
            return url

        if not url.startswith(("http://", "https://")):
            url = "https://" + url

        return url

    def _get_request_headers(self):
        parsed_url = urlparse(self.url or "")
        base_url = "%s://%s" % (
            parsed_url.scheme or "https",
            parsed_url.netloc
        ) if parsed_url.netloc else "https://www.google.com/"

        return {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": (
                "text/html,application/xhtml+xml,application/xml;q=0.9,"
                "image/avif,image/webp,image/apng,*/*;q=0.8"
            ),
            "Accept-Language": "it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Referer": base_url,
        }

    def _get_image_request_headers(self, image_url):
        parsed_page = urlparse(self.url or "")
        page_base_url = "%s://%s" % (
            parsed_page.scheme or "https",
            parsed_page.netloc
        ) if parsed_page.netloc else "https://www.google.com/"

        parsed_image = urlparse(image_url or "")
        image_base_url = "%s://%s" % (
            parsed_image.scheme or "https",
            parsed_image.netloc
        ) if parsed_image.netloc else page_base_url

        return {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
            "Accept-Language": "it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7",
            "Referer": page_base_url,
            "Origin": image_base_url,
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Connection": "keep-alive",
        }

    def _compute_selling_price(self, base_price):
        return base_price * (1 + (self.margin_percent or 0.0) / 100)

    def _get_price_status(self, confidence):
        if confidence in ("high", "medium"):
            return "green"
        if confidence == "low":
            return "yellow"
        return "red"

    def _get_title_from_url(self, url):
        try:
            slug = urlparse(url).path.strip("/").split("/")[-1].split(".")[0]
            slug = re.sub(r"[-_]+", " ", slug)
            return slug.title() if slug else "Imported Product"
        except Exception:
            return "Imported Product"

    def _get_title(self, soup):
        product_data = self._get_product_json_ld(soup)
        if product_data and product_data.get("name"):
            return product_data["name"].strip()

        h1 = soup.find("h1")
        if h1:
            return h1.get_text(strip=True)

        meta = soup.find("meta", attrs={"property": "og:title"})
        if meta and meta.get("content"):
            return meta["content"].strip()

        title = soup.find("title")
        return title.get_text(strip=True) if title else None

    def _get_image_urls(self, soup, page_url):
        urls = []

        urls.extend(self._get_images_from_json_ld(soup))
        urls.extend(self._get_images_from_meta(soup))
        urls.extend(self._get_images_from_img_tags(soup))

        normalized = []
        seen = set()

        for image_url in urls:
            image_url = self._normalize_image_url(image_url, page_url)
            if not image_url or image_url in seen:
                continue

            if not self._looks_like_product_image(image_url):
                continue

            normalized.append(image_url)
            seen.add(image_url)

        return normalized[:10]

    def _get_image_url(self, soup, page_url):
        urls = self._get_image_urls(soup, page_url)
        return urls[0] if urls else None

    def _get_images_from_json_ld(self, soup):
        product_data = self._get_product_json_ld(soup)
        if not product_data:
            return []

        image = product_data.get("image")
        images = []

        if isinstance(image, list):
            for item in image:
                if isinstance(item, str):
                    images.append(item)
                elif isinstance(item, dict):
                    url = item.get("url") or item.get("contentUrl")
                    if url:
                        images.append(url)

        elif isinstance(image, dict):
            url = image.get("url") or image.get("contentUrl")
            if url:
                images.append(url)

        elif isinstance(image, str):
            images.append(image)

        return images

    def _get_images_from_meta(self, soup):
        images = []

        for attrs in [
            {"property": "og:image"},
            {"property": "og:image:secure_url"},
            {"name": "twitter:image"},
            {"name": "twitter:image:src"},
        ]:
            for tag in soup.find_all("meta", attrs=attrs):
                if tag and tag.get("content"):
                    images.append(tag["content"])

        return images

    def _get_images_from_img_tags(self, soup):
        candidates = []

        bad_words = [
            "logo", "icon", "sprite", "favicon", "avatar",
            "banner", "marketing", "campaign", "promo", "hero",
            "footer", "header", "brand",
        ]

        good_words = [
            "product", "sku", "pdp", "zoom", "large", "main",
            "images.footlocker", "fl_product", "media", "catalog",
        ]

        for img in soup.find_all("img"):
            src_values = []

            for attr in ["src", "data-src", "data-original", "data-zoom-image"]:
                value = img.get(attr)
                if value:
                    src_values.append(value)

            srcset = img.get("srcset")
            if srcset:
                for part in srcset.split(","):
                    src_values.append(part.strip().split(" ")[0])

            for src in src_values:
                if not src:
                    continue

                lowered = src.lower()

                if any(word in lowered for word in bad_words):
                    continue

                if not self._looks_like_product_image(src):
                    continue

                score = 0

                if any(word in lowered for word in good_words):
                    score += 10

                alt = (img.get("alt") or "").lower()
                if alt:
                    score += 2
                    if self.name and self.name.lower() in alt:
                        score += 20

                width = img.get("width")
                height = img.get("height")

                try:
                    if width and int(width) >= 300:
                        score += 3
                    if height and int(height) >= 300:
                        score += 3
                except Exception:
                    pass

                candidates.append((score, src))

        candidates.sort(key=lambda item: item[0], reverse=True)

        result = []
        seen = set()

        for score, src in candidates:
            if src in seen:
                continue

            result.append(src)
            seen.add(src)

        return result[:10]

    def _looks_like_product_image(self, url):
        lowered = (url or "").lower()

        if any(x in lowered for x in [
            "logo", "icon", "sprite", "favicon", "avatar",
            "banner", "marketing", "campaign", "promo", "hero",
            "footer", "header",
        ]):
            return False

        return any(x in lowered for x in [
            ".jpg", ".jpeg", ".png", ".webp",
            "cdn", "product", "media", "image", "sku", "pdp", "catalog",
        ])

    def _normalize_image_url(self, image_url, page_url):
        if not image_url:
            return None

        image_url = image_url.strip()

        if image_url.startswith("//"):
            return "https:" + image_url

        if image_url.startswith("/"):
            return urljoin(page_url, image_url)

        return image_url

    def _download_image_as_base64(self, image_url):
        if not image_url:
            return False

        try:
            response = requests.get(
                image_url,
                timeout=25,
                headers=self._get_image_request_headers(image_url),
                allow_redirects=True,
            )

            if response.status_code >= 400:
                return False

            content_type = response.headers.get("Content-Type", "").lower()
            clean_url = image_url.lower().split("?")[0]

            if "image" not in content_type and not clean_url.endswith(
                (".jpg", ".jpeg", ".png", ".webp", ".gif")
            ):
                return False

            return base64.b64encode(response.content)

        except Exception:
            return False

    def _get_product_json_ld(self, soup):
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string or script.get_text())
            except Exception:
                continue

            items = data if isinstance(data, list) else [data]

            for item in items:
                product = self._find_product_in_json_ld(item)
                if product:
                    return product

        return None

    def _find_product_in_json_ld(self, item):
        if not isinstance(item, dict):
            return None

        item_type = item.get("@type")
        if item_type == "Product" or (isinstance(item_type, list) and "Product" in item_type):
            return item

        graph = item.get("@graph")
        if isinstance(graph, list):
            for graph_item in graph:
                product = self._find_product_in_json_ld(graph_item)
                if product:
                    return product

        return None