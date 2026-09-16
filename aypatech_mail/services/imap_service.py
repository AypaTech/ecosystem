# -*- coding: utf-8 -*-
"""
Real IMAP client wrapper (stdlib imaplib) used for every mailbox-content
operation: folder discovery, incremental fetch, flag sync. Never used for
Mailcow administration - that is mailcow_client.py's job (section 19).
"""
import email
import imaplib
import logging
import re

_logger = logging.getLogger(__name__)

_LIST_LINE_RE = re.compile(rb'^\((?P<flags>[^)]*)\)\s+"(?P<delim>[^"]*)"\s+(?P<name>.+)$')


class IMAPServiceError(Exception):
    pass


class IMAPService:
    def __init__(self, host, port, use_ssl, login, password, timeout=15):
        self.host = host
        self.port = port or (993 if use_ssl else 143)
        self.use_ssl = use_ssl
        self.login_name = login
        self.password = password
        self.timeout = timeout
        self._conn = None

    # ------------------------------------------------------------------
    def connect(self):
        if self._conn is not None:
            return self._conn
        if not self.host:
            raise IMAPServiceError("IMAP host is not configured")
        try:
            if self.use_ssl:
                conn = imaplib.IMAP4_SSL(self.host, self.port, timeout=self.timeout)
            else:
                conn = imaplib.IMAP4(self.host, self.port, timeout=self.timeout)
                conn.starttls()
            conn.login(self.login_name, self.password or "")
        except (imaplib.IMAP4.error, OSError) as exc:
            raise IMAPServiceError("IMAP connection failed: %s" % exc) from exc
        self._conn = conn
        return conn

    def close(self):
        if self._conn is None:
            return
        try:
            self._conn.logout()
        except Exception:  # noqa: BLE001
            pass
        finally:
            self._conn = None

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()

    # ------------------------------------------------------------------
    # Folder discovery (spec section 9, step 1)
    # ------------------------------------------------------------------
    def list_folders(self):
        conn = self.connect()
        status, data = conn.list()
        if status != "OK":
            raise IMAPServiceError("IMAP LIST failed: %s" % data)

        folders = []
        for raw_line in data:
            if not raw_line:
                continue
            match = _LIST_LINE_RE.match(raw_line)
            if not match:
                continue
            flags = match.group("flags").decode(errors="replace").split()
            delimiter = match.group("delim").decode(errors="replace")
            name = match.group("name").decode(errors="replace").strip('"')
            folders.append((name, delimiter, flags))
        return folders

    # ------------------------------------------------------------------
    # Sync primitives (spec section 9, steps 2-3)
    # ------------------------------------------------------------------
    def select_folder(self, remote_name, readonly=True):
        conn = self.connect()
        status, data = conn.select(mailbox=self._quote(remote_name), readonly=readonly)
        if status != "OK":
            raise IMAPServiceError("Cannot select folder %s: %s" % (remote_name, data))
        return status

    def get_uidvalidity(self, remote_name):
        conn = self.connect()
        self.select_folder(remote_name)
        status, data = conn.status(self._quote(remote_name), "(UIDVALIDITY UIDNEXT)")
        if status != "OK":
            raise IMAPServiceError("STATUS failed for %s: %s" % (remote_name, data))
        raw = data[0].decode(errors="replace") if data and data[0] else ""
        uidvalidity = self._extract_status_value(raw, "UIDVALIDITY")
        uidnext = self._extract_status_value(raw, "UIDNEXT")
        return uidvalidity, uidnext

    @staticmethod
    def _extract_status_value(raw, key):
        match = re.search(r"%s (\d+)" % key, raw)
        return match.group(1) if match else None

    def fetch_new_uids(self, remote_name, last_uid=0):
        """Return the sorted list of UIDs strictly greater than last_uid
        (spec section 9, step 3: only new/changed messages).
        """
        conn = self.connect()
        self.select_folder(remote_name)
        uid_range = "%s:*" % (last_uid + 1)
        status, data = conn.uid("search", None, "UID", uid_range)
        if status != "OK":
            raise IMAPServiceError("UID SEARCH failed for %s: %s" % (remote_name, data))
        raw = data[0].decode() if data and data[0] else ""
        uids = sorted({int(x) for x in raw.split() if x.isdigit() and int(x) > last_uid})
        return uids

    def fetch_message(self, remote_name, uid):
        """Fetch one full RFC822 message plus its flags, without marking
        it \\Seen (BODY.PEEK), so read/unread stays under our own control
        until the user actually opens it.
        """
        conn = self.connect()
        self.select_folder(remote_name)
        status, data = conn.uid("fetch", str(uid), "(BODY.PEEK[] FLAGS)")
        if status != "OK" or not data or data[0] is None:
            raise IMAPServiceError("UID FETCH failed for uid=%s in %s: %s" % (uid, remote_name, data))

        raw_bytes = None
        flags = []
        for part in data:
            if isinstance(part, tuple) and part[1]:
                raw_bytes = part[1]
            elif isinstance(part, bytes):
                flag_match = re.search(rb"FLAGS \(([^)]*)\)", part)
                if flag_match:
                    flags = flag_match.group(1).decode(errors="replace").split()
        if raw_bytes is None:
            raise IMAPServiceError("Empty body for uid=%s in %s" % (uid, remote_name))

        return raw_bytes, flags

    def set_flag(self, remote_name, uid, flag, set_flag=True):
        conn = self.connect()
        self.select_folder(remote_name, readonly=False)
        command = "+FLAGS" if set_flag else "-FLAGS"
        status, data = conn.uid("store", str(uid), command, "(%s)" % flag)
        if status != "OK":
            raise IMAPServiceError("UID STORE failed for uid=%s: %s" % (uid, data))
        return True

    def append_message(self, remote_name, raw_message, flags=("\\Seen",)):
        """Append an already-sent message into e.g. the Sent folder."""
        conn = self.connect()
        flag_str = "(%s)" % " ".join(flags) if flags else None
        status, data = conn.append(self._quote(remote_name), flag_str, None, raw_message)
        if status != "OK":
            raise IMAPServiceError("APPEND failed for %s: %s" % (remote_name, data))
        return True

    @staticmethod
    def _quote(remote_name):
        if remote_name.startswith('"') and remote_name.endswith('"'):
            return remote_name
        return '"%s"' % remote_name.replace('"', '\\"')


def parse_raw_message(raw_bytes):
    """Thin pass-through kept here for convenience; real parsing lives in
    services/parser.py so it can be unit-tested without a live IMAP server.
    """
    return email.message_from_bytes(raw_bytes)
