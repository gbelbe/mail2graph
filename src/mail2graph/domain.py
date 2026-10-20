"""Cœur du module : objets métier et règles pures. Aucune entrée-sortie, aucune dépendance externe."""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class Message:
    id: str                       # Message-ID (ou identifiant de repli)
    subject: str
    sender: str                   # adresse complète, jamais écrite dans le graphe
    date: datetime
    body: str                     # texte brut utile (voir clean_body)
    attachments: tuple[str, ...] = ()

    @property
    def digest(self) -> str:
        return hashlib.sha256(self.id.encode()).hexdigest()[:16]

    @property
    def sender_domain(self) -> str:
        return self.sender.rsplit("@", 1)[-1].lower() if "@" in self.sender else ""


@dataclass(frozen=True)
class Mention:
    message_id: str
    kind: str                     # ex. "dp_number", "parcelle", "gazetteer"
    text: str
    confidence: float = 1.0
    entity_id: str | None = None  # renseigné quand l'extracteur sait déjà de quelle entité il s'agit


@dataclass(frozen=True)
class EntityRef:
    id: str
    label: str
    class_id: str
    names: tuple[str, ...] = ()   # libellés et identifiants servant à la liaison


@dataclass(frozen=True)
class ClassInfo:
    id: str
    label: str


@dataclass(frozen=True)
class GraphContext:
    """Ce que le graphe expose aux extracteurs et au lieur : classes et entités connues."""
    classes: tuple[ClassInfo, ...] = ()
    entities: tuple[EntityRef, ...] = ()


@dataclass(frozen=True)
class Candidate:
    entity: EntityRef
    score: float                  # 0..1


@dataclass
class Proposition:
    kind: str                     # "message" | "link" | "new_entity" | "event"
    message_id: str
    payload: dict[str, Any]
    confidence: float = 1.0
    parent: str | None = None     # une liaison ou un événement dépend de la proposition « message »
    status: str = "pending"       # pending | accepted | rejected | committed
    note: str = ""
    id: str = field(default="")

    def __post_init__(self) -> None:
        if not self.id:
            key = f"{self.kind}|{self.message_id}|{sorted(self.payload.items())}"
            self.id = hashlib.sha1(key.encode()).hexdigest()[:12]


@dataclass(frozen=True)
class Decision:
    proposition_id: str
    accepted: bool
    note: str = ""


@dataclass
class RunReport:
    fetched: int = 0
    skipped_known: int = 0
    skipped_filtered: int = 0
    propositions: int = 0
    new_propositions: int = 0


_QUOTE = re.compile(r"^\s*>.*$", re.MULTILINE)
_SIGNATURE = re.compile(r"^\s*-- ?\s*$.*", re.MULTILINE | re.DOTALL)
_REPLY_HEADER = re.compile(r"^(Le .{5,80} a écrit :|On .{5,80} wrote:)\s*$.*", re.MULTILINE | re.DOTALL)


def clean_body(text: str) -> str:
    """Retire citations, en-tête de réponse et signature ; garde le texte nouveau du message."""
    t = text.replace("\r\n", "\n")
    t = _REPLY_HEADER.sub("", t)
    t = _SIGNATURE.sub("", t)
    t = _QUOTE.sub("", t)
    return re.sub(r"\n{3,}", "\n\n", t).strip()


def normalize(text: str) -> str:
    """Forme de comparaison : minuscules, sans accents ni ponctuation superflue."""
    import unicodedata
    t = unicodedata.normalize("NFKD", text.lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", t).strip()


def link_decision(score: float, link_threshold: float, suggest_threshold: float) -> str:
    """'link' (proposer la liaison), 'suggest' (proposer l'entité avec réserve) ou 'none'."""
    if score >= link_threshold:
        return "link"
    if score >= suggest_threshold:
        return "suggest"
    return "none"
