# -*- coding: utf-8 -*-
"""
Thin wrapper around the Mailcow REST API (https://mailcow.docs.apiary.io).

Golden rule: Aypatech Mail NEVER talks to
Mailcow's own PostgreSQL/MySQL database directly. Every administrative
operation (domain/mailbox/alias/quota) goes through this one class, and
every mailbox-content operation (read/send) goes through imap_service.py
/ smtp_service.py instead. Nothing else in the codebase should build a
Mailcow API request by hand - always go through MailcowClient so the
wrapper stays the single place that knows the endpoint shapes, and so a
future non-Mailcow provider can implement the same surface.
"""
import logging

import requests

_logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 15


class MailcowAPIError(Exception):
    """Raised when Mailcow's API answers but reports a failure."""


class MailcowClient:
    def __init__(self, base_url, api_key, timeout=DEFAULT_TIMEOUT):
        if not base_url:
            raise ValueError("Mailcow base_url is required")
        self.base_url = base_url.rstrip("/")
        self._api_key = api_key
        self.timeout = timeout or DEFAULT_TIMEOUT

    # ------------------------------------------------------------------
    # Low-level transport - the only place headers/URLs are built, so a
    # secret can never leak through some other ad-hoc request elsewhere.
    # ------------------------------------------------------------------
    def _headers(self):
        return {
            "X-API-Key": self._api_key or "",
            "Content-Type": "application/json",
        }

    def _request(self, method, path, json_body=None):
        url = "%s/api/v1/%s" % (self.base_url, path.lstrip("/"))
        try:
            response = requests.request(
                method, url, json=json_body, headers=self._headers(), timeout=self.timeout,
            )
        except requests.RequestException as exc:
            # Never include api key/password in the log line.
            _logger.warning("Mailcow API request failed (%s %s): %s", method, path, exc)
            return {"ok": False, "error": "connection_error", "detail": str(exc)}

        if response.status_code >= 500:
            return {"ok": False, "error": "server_error", "status_code": response.status_code}
        if response.status_code >= 400:
            return {"ok": False, "error": "client_error", "status_code": response.status_code, "body": self._safe_json(response)}

        payload = self._safe_json(response)
        # Mailcow's "add"/"edit"/"delete" endpoints answer with a list of
        # {"type": "success"|"error", "msg": ...} objects.
        if isinstance(payload, list):
            has_error = any(isinstance(item, dict) and item.get("type") == "error" for item in payload)
            return {"ok": not has_error, "data": payload}
        return {"ok": True, "data": payload}

    @staticmethod
    def _safe_json(response):
        try:
            return response.json()
        except ValueError:
            return None

    def _get(self, path):
        return self._request("GET", path)

    def _post(self, path, json_body):
        return self._request("POST", path, json_body)

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------
    def health_check(self):
        result = self._get("get/status/containers")
        return {"ok": result.get("ok", False), "error": None if result.get("ok") else result.get("error")}

    # ------------------------------------------------------------------
    # Domain
    # ------------------------------------------------------------------
    def create_domain(self, domain, **options):
        body = {
            "domain": domain,
            "description": options.get("description", ""),
            "aliases": str(options.get("aliases", 400)),
            "mailboxes": str(options.get("mailboxes", 10)),
            "defquota": str(options.get("defquota", 3072)),
            "maxquota": str(options.get("maxquota", 10240)),
            "quota": str(options.get("quota", 10240)),
            "active": "1" if options.get("active", True) else "0",
        }
        return self._post("add/domain", body)

    def update_domain(self, domain, **options):
        attr = {k: v for k, v in options.items() if v is not None}
        return self._post("edit/domain", {"items": [domain], "attr": attr})

    def delete_domain(self, domain):
        return self._post("delete/domain", [domain])

    def get_domain(self, domain):
        result = self._get("get/domain/%s" % domain)
        data = result.get("data")
        return data if isinstance(data, dict) else None

    # ------------------------------------------------------------------
    # Mailbox
    # ------------------------------------------------------------------
    def create_mailbox(self, local_part, domain, password, name="", quota_mb=3072, active=True):
        body = {
            "local_part": local_part,
            "domain": domain,
            "name": name or local_part,
            "password": password,
            "password2": password,
            "quota": str(quota_mb),
            "active": "1" if active else "0",
        }
        return self._post("add/mailbox", body)

    def update_mailbox(self, email, **options):
        attr = {k: v for k, v in options.items() if v is not None}
        return self._post("edit/mailbox", {"items": [email], "attr": attr})

    def delete_mailbox(self, email):
        return self._post("delete/mailbox", [email])

    def get_mailbox(self, email):
        result = self._get("get/mailbox/%s" % email)
        data = result.get("data")
        return data if isinstance(data, dict) else None

    # ------------------------------------------------------------------
    # Alias
    # ------------------------------------------------------------------
    def create_alias(self, address, goto, active=True):
        body = {"address": address, "goto": goto, "active": "1" if active else "0"}
        return self._post("add/alias", body)

    def update_alias(self, alias_id, **options):
        attr = {k: v for k, v in options.items() if v is not None}
        return self._post("edit/alias", {"items": [alias_id], "attr": attr})

    def delete_alias(self, alias_id_or_address):
        return self._post("delete/alias", [alias_id_or_address])
