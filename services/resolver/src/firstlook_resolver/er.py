"""Entity resolution v1.

Order of evidence, strongest first:

1. Deterministic identifiers: an email address, company domain or registry ID
   already on file maps to exactly one entity (identifiers table).
2. Similarity: 0.7 * name similarity (rapidfuzz, initial-aware)
             + 0.3 * name-embedding similarity
             + 0.15 if the mention shares an email domain or company (capped at 1).
     score >= AUTO_LINK and same domain  -> link automatically
     score >= REVIEW                     -> create a provisional entity and
                                            queue the pair for human review
     otherwise                           -> create a new entity

Provisional entities let ingestion continue without waiting for a reviewer;
accepting a review item merges the provisional entity into the candidate
(merge_entities in packages/schema).
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

import psycopg
from psycopg.types.json import Jsonb
from rapidfuzz import fuzz

from firstlook_core.embeddings import cosine, to_pgvector
from firstlook_core.llm import LlmClient, get_llm

AUTO_LINK = 0.92
REVIEW = 0.72

FREE_MAIL_DOMAINS = frozenset(
    {
        "gmail.com",
        "googlemail.com",
        "yahoo.com",
        "yahoo.co.uk",
        "ymail.com",
        "outlook.com",
        "hotmail.com",
        "live.com",
        "msn.com",
        "icloud.com",
        "me.com",
        "mac.com",
        "aol.com",
        "proton.me",
        "protonmail.com",
        "gmx.com",
        "gmx.de",
        "mail.com",
        "yandex.com",
        "zoho.com",
        "fastmail.com",
        "hey.com",
    }
)

_COMPANY_SUFFIXES = re.compile(
    r"\b(inc|incorporated|llc|ltd|limited|plc|corp|corporation|co|company|gmbh|sa|sas|bv|pty|holdings?|group|"
    r"technologies|technology|labs?|hq|africa|kenya|nigeria)\b\.?",
    re.I,
)
_HONORIFICS = re.compile(r"^(dr|mr|mrs|ms|mx|prof|eng|hon)\.?\s+", re.I)


def domain_of(email: str | None) -> str | None:
    if not email or "@" not in email:
        return None
    return email.rsplit("@", 1)[1].lower().strip()


def is_business_domain(domain: str | None) -> bool:
    return bool(domain) and domain not in FREE_MAIL_DOMAINS


def normalise_person_name(name: str) -> str:
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    name = _HONORIFICS.sub("", name.strip())
    if "," in name:  # "Doe, Jane" -> "Jane Doe"
        last, _, first = name.partition(",")
        name = f"{first} {last}"
    name = re.sub(r"[^\w\s'-]", " ", name)
    return re.sub(r"\s+", " ", name).strip().lower()


def normalise_company_name(name: str) -> str:
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    name = _COMPANY_SUFFIXES.sub(" ", name)
    name = re.sub(r"[^\w\s]", " ", name)
    return re.sub(r"\s+", " ", name).strip()


def derived_company_name(domain: str) -> str:
    return domain.split(".")[0].replace("-", " ").title()


def name_from_email(email: str) -> str:
    local = email.split("@", 1)[0]
    local = re.sub(r"\+.*$", "", local)
    parts = [p for p in re.split(r"[._-]+", local) if p and not p.isdigit()]
    return " ".join(p.capitalize() for p in parts) or email


def person_name_similarity(a: str, b: str) -> float:
    na, nb = normalise_person_name(a), normalise_person_name(b)
    if not na or not nb:
        return 0.0
    score = fuzz.token_sort_ratio(na, nb) / 100
    # "Jane Doe" vs "Jane A. Doe" / "J. Doe": compare first initial + surname.
    ta, tb = na.split(), nb.split()
    if len(ta) >= 2 and len(tb) >= 2 and ta[-1] == tb[-1] and ta[0][0] == tb[0][0]:
        score = max(score, 0.9)
    return score


@dataclass
class Resolution:
    entity_id: UUID
    created: bool
    method: str  # identifier, similarity, new, provisional
    score: float = 1.0
    queued: bool = False
    features: dict[str, Any] = field(default_factory=dict)


class Resolver:
    """Resolves mentions within one tenant. conn must be tenant-scoped."""

    def __init__(self, conn: psycopg.Connection, tenant_id: UUID | str, llm: LlmClient | None = None):
        self.conn = conn
        self.tenant_id = str(tenant_id)
        self.llm = llm or get_llm()
        self._cache: dict[tuple[str, str], UUID] = {}

    # -- helpers ---------------------------------------------------------------

    def _by_identifier(self, kind: str, value: str) -> UUID | None:
        key = (kind, value.lower())
        if key in self._cache:
            return self._cache[key]
        row = self.conn.execute(
            "SELECT e.id, e.merged_into FROM identifiers i JOIN entities e ON e.id = i.entity_id"
            " WHERE i.tenant_id = %s AND i.kind = %s AND i.value = %s",
            (self.tenant_id, kind, value),
        ).fetchone()
        if row is None:
            return None
        entity_id = self._follow_merges(row["id"]) if row["merged_into"] else row["id"]
        self._cache[key] = entity_id
        return entity_id

    def _follow_merges(self, entity_id: UUID) -> UUID:
        for _ in range(10):
            row = self.conn.execute("SELECT merged_into FROM entities WHERE id = %s", (entity_id,)).fetchone()
            if row is None or row["merged_into"] is None:
                return entity_id
            entity_id = row["merged_into"]
        return entity_id

    def add_identifier(self, entity_id: UUID, kind: str, value: str, source_id: UUID | None = None) -> None:
        self.conn.execute(
            "INSERT INTO identifiers (tenant_id, entity_id, kind, value, source_id) VALUES (%s, %s, %s, %s, %s)"
            " ON CONFLICT (tenant_id, kind, value) DO NOTHING",
            (
                self.tenant_id,
                entity_id,
                kind,
                value.lower() if kind in ("email", "domain") else value,
                source_id,
            ),
        )
        self._cache[(kind, value.lower())] = entity_id

    def _embed(self, text: str) -> list[float]:
        return self.llm.embed(self.tenant_id, [text], task="embed.entity_name")[0]

    def _new_entity(self, type_: str, name: str) -> UUID:
        vec = self._embed(name)
        return self.conn.execute(
            "INSERT INTO entities (tenant_id, type, canonical_name, name_embedding) VALUES (%s, %s, %s, %s)"
            " RETURNING id",
            (self.tenant_id, type_, name, to_pgvector(vec)),
        ).fetchone()["id"]

    def _queue(
        self,
        entity_type: str,
        mention: dict[str, Any],
        provisional: UUID,
        candidate: UUID,
        score: float,
        features: dict[str, Any],
        source_id: UUID | None,
    ) -> None:
        self.conn.execute(
            "INSERT INTO er_candidates (tenant_id, entity_type, mention, provisional_entity_id,"
            " candidate_entity_id, score, features, source_id) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"
            " ON CONFLICT (tenant_id, provisional_entity_id, candidate_entity_id) DO NOTHING",
            (
                self.tenant_id,
                entity_type,
                Jsonb(mention),
                provisional,
                candidate,
                score,
                Jsonb(features),
                source_id,
            ),
        )

    def _candidates(self, type_: str, name: str, limit: int = 8) -> list[dict[str, Any]]:
        """Nearest entities by trigram similarity and by name embedding."""
        vec = to_pgvector(self._embed(name))
        return self.conn.execute(
            """
            (SELECT id, canonical_name, name_embedding::text AS emb FROM entities
              WHERE tenant_id = %(t)s AND type = %(type)s AND merged_into IS NULL
                AND similarity(canonical_name, %(name)s) > 0.3
              ORDER BY similarity(canonical_name, %(name)s) DESC LIMIT %(n)s)
            UNION
            (SELECT id, canonical_name, name_embedding::text AS emb FROM entities
              WHERE tenant_id = %(t)s AND type = %(type)s AND merged_into IS NULL AND name_embedding IS NOT NULL
              ORDER BY name_embedding <=> %(vec)s::vector LIMIT %(n)s)
            """,
            {"t": self.tenant_id, "type": type_, "name": name, "vec": vec, "n": limit},
        ).fetchall()

    @staticmethod
    def _parse_vec(text: str | None) -> list[float] | None:
        if not text:
            return None
        return [float(x) for x in text.strip("[]").split(",")]

    # -- companies -------------------------------------------------------------

    def resolve_company(
        self,
        *,
        name: str | None = None,
        domain: str | None = None,
        registry_id: str | None = None,
        source_id: UUID | None = None,
        **attrs: Any,
    ) -> Resolution | None:
        domain = domain.lower().removeprefix("www.") if domain else None
        if domain and not is_business_domain(domain):
            domain = None
        if registry_id and (hit := self._by_identifier("registry_id", registry_id)):
            if domain:
                self.add_identifier(hit, "domain", domain, source_id)
            return Resolution(hit, False, "identifier")
        if domain and (hit := self._by_identifier("domain", domain)):
            if registry_id:
                self.add_identifier(hit, "registry_id", registry_id, source_id)
            if name:
                self._upgrade_derived_name(hit, domain, name)
            return Resolution(hit, False, "identifier")
        if not name and not domain:
            return None
        name = name or derived_company_name(domain)  # type: ignore[arg-type]

        best: tuple[float, dict[str, Any]] | None = None
        norm = normalise_company_name(name)
        if norm:
            for cand in self._candidates("company", name):
                row = self.conn.execute(
                    "SELECT domain FROM companies WHERE id = %s", (cand["id"],)
                ).fetchone()
                cand_domain = row["domain"] if row else None
                if domain and cand_domain and cand_domain != domain:
                    continue  # two different registered domains: different companies
                sim = fuzz.token_sort_ratio(norm, normalise_company_name(cand["canonical_name"])) / 100
                if best is None or sim > best[0]:
                    best = (sim, {"candidate": cand, "name_sim": sim})

        if best and best[0] >= 0.97:
            entity_id = best[1]["candidate"]["id"]
            if domain:
                self.add_identifier(entity_id, "domain", domain, source_id)
                self.conn.execute(
                    "UPDATE companies SET domain = coalesce(domain, %s) WHERE id = %s", (domain, entity_id)
                )
            return Resolution(entity_id, False, "similarity", best[0])

        entity_id = self._new_entity("company", name)
        self.conn.execute(
            "INSERT INTO companies (id, tenant_id, name, domain, registry_id, country, description, website)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            (
                entity_id,
                self.tenant_id,
                name,
                domain,
                registry_id,
                attrs.get("country"),
                attrs.get("description"),
                attrs.get("website"),
            ),
        )
        if domain:
            self.add_identifier(entity_id, "domain", domain, source_id)
        if registry_id:
            self.add_identifier(entity_id, "registry_id", registry_id, source_id)

        if best and best[0] >= REVIEW:
            self._queue(
                "company",
                {"name": name, "domain": domain},
                entity_id,
                best[1]["candidate"]["id"],
                best[0],
                {"name_sim": best[0]},
                source_id,
            )
            return Resolution(entity_id, True, "provisional", best[0], queued=True)
        return Resolution(entity_id, True, "new")

    def _upgrade_derived_name(self, company_id: UUID, domain: str, name: str) -> None:
        """A company first seen only as an email domain gets a placeholder name
        ("Kilimodata"); replace it when a source supplies the real one."""
        derived = derived_company_name(domain)
        if name.strip() and name.strip() != derived:
            self.conn.execute(
                "UPDATE companies SET name = %s WHERE id = %s AND name = %s", (name.strip(), company_id, derived)
            )
            self.conn.execute(
                "UPDATE entities SET canonical_name = %s, updated_at = now() WHERE id = %s AND canonical_name = %s",
                (name.strip(), company_id, derived),
            )

    # -- people ----------------------------------------------------------------

    def resolve_person(
        self,
        *,
        email: str | None = None,
        name: str | None = None,
        title: str | None = None,
        company_id: UUID | None = None,
        source_id: UUID | None = None,
        context: str | None = None,
        crm_id: str | None = None,
    ) -> Resolution | None:
        email = email.lower().strip() if email else None
        if email and (hit := self._by_identifier("email", email)):
            self._enrich_person(hit, title=title, company_id=company_id)
            return Resolution(hit, False, "identifier")
        if crm_id and (hit := self._by_identifier("crm_id", crm_id)):
            if email:
                self.add_identifier(hit, "email", email, source_id)
            self._enrich_person(hit, title=title, company_id=company_id)
            return Resolution(hit, False, "identifier")
        if not email and not name:
            return None
        display = name.strip() if name and name.strip() and "@" not in name else name_from_email(email or "")
        domain = domain_of(email)

        if company_id is None and is_business_domain(domain):
            company = self.resolve_company(domain=domain, source_id=source_id)
            company_id = company.entity_id if company else None

        best = self._best_person_match(display, domain, company_id)

        if best and best["score"] >= AUTO_LINK and best["same_org"]:
            entity_id = best["id"]
            if email:
                self.add_identifier(entity_id, "email", email, source_id)
            if crm_id:
                self.add_identifier(entity_id, "crm_id", crm_id, source_id)
            self._enrich_person(entity_id, title=title, company_id=company_id)
            return Resolution(entity_id, False, "similarity", best["score"], features=best["features"])

        entity_id = self._new_entity("person", display)
        self.conn.execute(
            "INSERT INTO people (id, tenant_id, full_name, primary_email, title, company_id)"
            " VALUES (%s, %s, %s, %s, %s, %s)",
            (entity_id, self.tenant_id, display, email, title, company_id),
        )
        if email:
            self.add_identifier(entity_id, "email", email, source_id)
        if crm_id:
            self.add_identifier(entity_id, "crm_id", crm_id, source_id)
        if company_id:
            self.link_works_at(entity_id, company_id, source_id, title)

        if best and best["score"] >= REVIEW:
            self._queue(
                "person",
                {"name": display, "email": email, "context": context},
                entity_id,
                best["id"],
                best["score"],
                best["features"],
                source_id,
            )
            return Resolution(
                entity_id, True, "provisional", best["score"], queued=True, features=best["features"]
            )
        return Resolution(entity_id, True, "new")

    def _best_person_match(
        self, name: str, domain: str | None, company_id: UUID | None
    ) -> dict[str, Any] | None:
        vec = self._embed(name)
        best: dict[str, Any] | None = None
        for cand in self._candidates("person", name):
            name_sim = person_name_similarity(name, cand["canonical_name"])
            if name_sim < 0.5:
                continue
            cand_vec = self._parse_vec(cand["emb"])
            embed_sim = max(0.0, cosine(vec, cand_vec)) if cand_vec else name_sim
            info = self.conn.execute(
                "SELECT p.company_id, array_agg(i.value::text) FILTER (WHERE i.kind = 'email') AS emails"
                " FROM people p LEFT JOIN identifiers i ON i.entity_id = p.id WHERE p.id = %s"
                " GROUP BY p.company_id",
                (cand["id"],),
            ).fetchone()
            cand_domains = {domain_of(e) for e in (info["emails"] or [])} if info else set()
            same_org = bool(
                (domain and is_business_domain(domain) and domain in cand_domains)
                or (company_id and info and info["company_id"] == company_id)
            )
            score = min(1.0, 0.7 * name_sim + 0.3 * embed_sim + (0.15 if same_org else 0.0))
            features = {
                "name_sim": round(name_sim, 3),
                "embed_sim": round(embed_sim, 3),
                "same_org": same_org,
            }
            if best is None or score > best["score"]:
                best = {
                    "id": cand["id"],
                    "score": round(score, 4),
                    "same_org": same_org,
                    "features": features,
                }
        return best

    def _enrich_person(self, person_id: UUID, *, title: str | None, company_id: UUID | None) -> None:
        if title or company_id:
            self.conn.execute(
                "UPDATE people SET title = coalesce(title, %s), company_id = coalesce(company_id, %s) WHERE id = %s",
                (title, company_id, person_id),
            )
        if company_id:
            self.link_works_at(person_id, company_id, None, title)

    def link_works_at(
        self, person_id: UUID, company_id: UUID, source_id: UUID | None, title: str | None
    ) -> None:
        self.conn.execute(
            "INSERT INTO edges (tenant_id, src_id, dst_id, type, props, source_id)"
            " VALUES (%s, %s, %s, 'works_at', %s, %s)"
            " ON CONFLICT (tenant_id, src_id, dst_id, type) WHERE valid_to IS NULL DO NOTHING",
            (self.tenant_id, person_id, company_id, Jsonb({"title": title} if title else {}), source_id),
        )
