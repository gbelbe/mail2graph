"""File de relecture (YAML) et état d'avancement (JSON) sur fichiers locaux, lisibles et versionnables."""
from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

import yaml

from ..domain import Proposition


class YamlQueue:
    def __init__(self, path: Path):
        self.path = path

    def _read(self) -> list[Proposition]:
        if not self.path.exists():
            return []
        return [Proposition(**d) for d in (yaml.safe_load(self.path.read_text(encoding="utf-8")) or [])]

    def _write(self, props: list[Proposition]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(yaml.safe_dump([asdict(p) for p in props], allow_unicode=True, sort_keys=False), encoding="utf-8")

    def publish(self, propositions: Sequence[Proposition]) -> int:
        cur = self._read()
        known = {p.id for p in cur}
        new = [p for p in propositions if p.id not in known]
        if new:
            self._write(cur + new)
        return len(new)

    def pending(self) -> list[Proposition]:
        return [p for p in self._read() if p.status == "pending"]

    def decide(self, proposition_id: str, accepted: bool, note: str = "") -> None:
        props = self._read()
        for p in props:
            if p.id == proposition_id and p.status in ("pending", "accepted", "rejected"):
                p.status = "accepted" if accepted else "rejected"
                p.note = note or p.note
                self._write(props)
                return
        raise KeyError(proposition_id)

    def accepted(self) -> list[Proposition]:
        return [p for p in self._read() if p.status == "accepted"]

    def mark_committed(self, ids: Sequence[str]) -> None:
        props = self._read()
        for p in props:
            if p.id in set(ids):
                p.status = "committed"
        self._write(props)


class JsonState:
    def __init__(self, path: Path):
        self.path = path
        self._d = json.loads(path.read_text()) if path.exists() else {"seen": [], "last_run": None}

    def seen(self, message_id: str) -> bool:
        return message_id in self._d["seen"]

    def mark(self, message_id: str) -> None:
        if message_id not in self._d["seen"]:
            self._d["seen"].append(message_id)
        self._save()

    def last_run(self) -> datetime | None:
        v = self._d.get("last_run")
        return datetime.fromisoformat(v) if v else None

    def touch(self) -> None:
        self._d["last_run"] = datetime.now(timezone.utc).isoformat()
        self._save()

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self._d, indent=1))
