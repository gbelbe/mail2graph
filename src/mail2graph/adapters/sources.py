"""Adaptateurs de sources de courriel : IMAP (imap-tools), mbox (bibliothèque standard), mémoire (tests)."""
from __future__ import annotations

import mailbox
import subprocess
from datetime import datetime, timezone
from email import policy
from email.utils import parsedate_to_datetime
from typing import Iterable, Sequence

from ..config import SourceCfg
from ..domain import Message


class MemorySource:
    def __init__(self, messages: Sequence[Message]):
        self._m = list(messages)

    def fetch(self, since: datetime | None = None) -> Iterable[Message]:
        return list(self._m)


class MboxSource:
    def __init__(self, path: str):
        self.path = path

    def fetch(self, since: datetime | None = None) -> Iterable[Message]:
        for i, m in enumerate(mailbox.mbox(self.path, factory=lambda f: _parse(f))):
            yield _from_email(m, fallback_id=f"mbox-{i}")


def _parse(fp):
    import email
    return email.message_from_binary_file(fp, policy=policy.default)


def _from_email(m, fallback_id: str) -> Message:
    body = m.get_body(preferencelist=("plain", "html"))
    text = body.get_content() if body is not None else ""
    try:
        date = parsedate_to_datetime(m["date"]) if m["date"] else datetime.now(timezone.utc)
    except (TypeError, ValueError):
        date = datetime.now(timezone.utc)
    atts = tuple(a.get_filename() or "" for a in m.iter_attachments())
    return Message(id=(m["message-id"] or fallback_id).strip(), subject=str(m["subject"] or ""),
                   sender=str(m["from"] or ""), date=date, body=text, attachments=atts)


class ImapSource:
    """Lit une boîte IMAP en lecture seule (aucun message n'est marqué lu ni déplacé)."""

    def __init__(self, cfg: SourceCfg):
        self.cfg = cfg

    def _password(self) -> str:
        if not self.cfg.password_cmd:
            raise RuntimeError("source.password_cmd est requis (commande affichant le mot de passe d'application).")
        return subprocess.run(self.cfg.password_cmd, shell=True, check=True, capture_output=True, text=True).stdout.strip()

    def fetch(self, since: datetime | None = None) -> Iterable[Message]:
        try:
            from imap_tools import AND, MailBox
        except ImportError as e:  # pragma: no cover
            raise RuntimeError("Installer l'extra : pip install 'mail2graph[imap]'") from e
        crit = AND(date_gte=since.date()) if since else AND(all=True)
        with MailBox(self.cfg.host, self.cfg.port).login(self.cfg.user, self._password(), initial_folder=self.cfg.mailbox) as mb:
            for m in mb.fetch(crit, limit=self.cfg.limit, mark_seen=False, bulk=True, reverse=True):
                mid = (m.headers.get("message-id") or (f"uid-{m.uid}",))[0].strip()
                yield Message(id=mid, subject=m.subject or "", sender=m.from_ or "", date=m.date,
                              body=m.text or "", attachments=tuple(a.filename for a in m.attachments))
