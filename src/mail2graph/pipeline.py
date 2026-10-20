"""Orchestration : fetch -> filtrer -> extraire -> lier -> proposer. Dépend uniquement des ports."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Sequence

from .config import Config
from .domain import (Candidate, GraphContext, Mention, Message, Proposition, RunReport, clean_body, link_decision)
from .ports import Extractor, GraphStore, Linker, MailSource, ReviewQueue, StateStore


@dataclass
class MessageFilter:
    senders_allow: Sequence[str] = ()
    subject_regex: str | None = None

    def accepts(self, m: Message) -> bool:
        if self.senders_allow:
            s = m.sender.lower()
            if not any(s == a.lower() or s.endswith("@" + a.lower().lstrip("@")) for a in self.senders_allow):
                return False
        if self.subject_regex and not re.search(self.subject_regex, m.subject, re.IGNORECASE):
            return False
        return True


@dataclass
class Pipeline:
    cfg: Config
    source: MailSource
    store: GraphStore
    queue: ReviewQueue
    state: StateStore
    linker: Linker
    extractors: list[Extractor] = field(default_factory=list)

    def run(self) -> RunReport:
        rep = RunReport()
        flt = MessageFilter(self.cfg.filter.senders_allow, self.cfg.filter.subject_regex)
        ctx = self.store.context()
        for raw in self.source.fetch(self.state.last_run()):
            rep.fetched += 1
            if self.state.seen(raw.id):
                rep.skipped_known += 1
                continue
            msg = Message(raw.id, raw.subject, raw.sender, raw.date, clean_body(raw.body), raw.attachments)
            if flt.accepts(msg):
                props = self.propose(msg, ctx)
                rep.propositions += len(props)
                rep.new_propositions += self.queue.publish(props)
            else:
                rep.skipped_filtered += 1
            self.state.mark(msg.id)
        self.state.touch()
        return rep

    def mentions(self, msg: Message, ctx: GraphContext) -> list[Mention]:
        out: list[Mention] = []
        for ex in self.extractors:
            out.extend(ex.extract(msg, ctx))
        return out

    def propose(self, msg: Message, ctx: GraphContext) -> list[Proposition]:
        g = self.cfg.graph
        mail_uri = f"{g.base_uri}courriel-{msg.digest}"
        head = Proposition("message", msg.id, {
            "uri": mail_uri, "subject": msg.subject, "date": msg.date.date().isoformat(),
            "sender_domain": msg.sender_domain, "hash": msg.digest,
        })
        props = [head]
        linked: set[str] = set()
        suggested: set[str] = set()
        for men in self.mentions(msg, ctx):
            cands = self._candidates(men, ctx)
            best = cands[0] if cands else None
            action = link_decision(best.score, self.cfg.link.link_threshold, self.cfg.link.suggest_threshold) if best else "none"
            if best and action in ("link", "suggest") and best.entity.id not in linked:
                linked.add(best.entity.id)
                props.append(Proposition("link", msg.id, {
                    "mail_uri": mail_uri, "entity_uri": best.entity.id, "entity_label": best.entity.label,
                    "mention": men.text, "score": round(best.score, 3),
                }, confidence=best.score, parent=head.id,
                    note="" if action == "link" else "Correspondance incertaine : à vérifier."))
            elif action == "none" and men.kind in g.new_entity_kinds and men.text.lower() not in suggested:
                suggested.add(men.text.lower())
                props.append(Proposition("new_entity", msg.id, {
                    "label": men.text, "class_uri": g.new_entity_kinds[men.kind],
                    "mail_uri": mail_uri, "mention": men.text,
                }, confidence=men.confidence, parent=head.id,
                    note="Entité absente du graphe : proposée à la création."))
        if g.event_from_message:
            props.append(Proposition("event", msg.id, {
                "mail_uri": mail_uri, "label": msg.subject, "date": msg.date.date().isoformat(),
            }, parent=head.id, note="Un événement daté de la réception du courriel."))
        return props

    def _candidates(self, men: Mention, ctx: GraphContext) -> list[Candidate]:
        return list(self.linker.link(men, ctx))

    def commit(self) -> int:
        acc = self.queue.accepted()
        done = self.store.commit(acc)
        self.queue.mark_committed([p.id for p in acc])
        return done
