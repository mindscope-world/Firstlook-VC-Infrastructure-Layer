"""Pull records from CRM APIs (the "API" half of CSV + API migration).

Credentials are the firm's own: a HubSpot private-app token, an Affinity API
key, a Salesforce access token + instance URL, or an Airtable personal access
token + base/table. They are used for the import and not stored.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import httpx

from .csv_import import _amount, _resolve_columns, clean_domain
from .model import CrmCompany, CrmDeal, CrmPerson, CrmRecords


def _paged_hubspot(
    http: httpx.Client, obj: str, props: list[str], extra: dict[str, Any] | None = None
) -> Iterator[dict[str, Any]]:
    after = None
    while True:
        params: dict[str, Any] = {"limit": 100, "properties": ",".join(props), **(extra or {})}
        if after:
            params["after"] = after
        r = http.get(f"https://api.hubapi.com/crm/v3/objects/{obj}", params=params)
        r.raise_for_status()
        body = r.json()
        yield from body.get("results", [])
        after = (body.get("paging") or {}).get("next", {}).get("after")
        if not after:
            return


def fetch_hubspot(token: str, http: httpx.Client | None = None) -> CrmRecords:
    http = http or httpx.Client(timeout=60)
    http.headers["Authorization"] = f"Bearer {token}"
    out = CrmRecords()
    company_by_id: dict[str, CrmCompany] = {}
    for c in _paged_hubspot(http, "companies", ["name", "domain", "country", "description"]):
        p = c["properties"]
        company = CrmCompany(
            p.get("name") or p.get("domain") or "",
            clean_domain(p.get("domain")),
            f"hubspot:{c['id']}",
            p.get("country"),
            p.get("description"),
        )
        company_by_id[c["id"]] = company
        out.companies.append(company)
    for c in _paged_hubspot(
        http,
        "contacts",
        ["firstname", "lastname", "email", "jobtitle", "company", "phone"],
        {"associations": "companies"},
    ):
        p = c["properties"]
        assoc = ((c.get("associations") or {}).get("companies") or {}).get("results", [])
        company = company_by_id.get(assoc[0]["id"]) if assoc else None
        out.people.append(
            CrmPerson(
                name=" ".join(x for x in (p.get("firstname"), p.get("lastname")) if x)
                or (p.get("email") or ""),
                email=p.get("email"),
                title=p.get("jobtitle"),
                company_name=company.name if company else p.get("company"),
                company_domain=company.domain if company else None,
                crm_id=f"hubspot:{c['id']}",
                phone=p.get("phone"),
            )
        )
    for d in _paged_hubspot(
        http, "deals", ["dealname", "dealstage", "amount"], {"associations": "companies"}
    ):
        p = d["properties"]
        assoc = ((d.get("associations") or {}).get("companies") or {}).get("results", [])
        company = company_by_id.get(assoc[0]["id"]) if assoc else None
        out.deals.append(
            CrmDeal(
                p.get("dealname") or "",
                p.get("dealstage"),
                _amount(p.get("amount")),
                company.name if company else p.get("dealname"),
                company.domain if company else None,
                f"hubspot:{d['id']}",
            )
        )
    return out


def fetch_affinity(api_key: str, http: httpx.Client | None = None) -> CrmRecords:
    http = http or httpx.Client(timeout=60)
    http.auth = ("", api_key)
    out = CrmRecords()
    orgs: dict[int, CrmCompany] = {}
    token = None
    while True:
        r = http.get(
            "https://api.affinity.co/organizations",
            params={"page_size": 500, **({"page_token": token} if token else {})},
        )
        r.raise_for_status()
        body = r.json()
        for o in body.get("organizations", []):
            company = CrmCompany(o["name"], clean_domain(o.get("domain")), f"affinity:{o['id']}")
            orgs[o["id"]] = company
            out.companies.append(company)
        token = body.get("next_page_token")
        if not token:
            break
    token = None
    while True:
        r = http.get(
            "https://api.affinity.co/persons",
            params={"page_size": 500, **({"page_token": token} if token else {})},
        )
        r.raise_for_status()
        body = r.json()
        for p in body.get("persons", []):
            org = orgs.get((p.get("organization_ids") or [None])[0])
            out.people.append(
                CrmPerson(
                    name=f"{p.get('first_name', '')} {p.get('last_name', '')}".strip(),
                    email=p.get("primary_email") or (p.get("emails") or [None])[0],
                    company_name=org.name if org else None,
                    company_domain=org.domain if org else None,
                    crm_id=f"affinity:{p['id']}",
                )
            )
        token = body.get("next_page_token")
        if not token:
            break
    return out


def fetch_salesforce(instance_url: str, access_token: str, http: httpx.Client | None = None) -> CrmRecords:
    http = http or httpx.Client(timeout=60)
    http.headers["Authorization"] = f"Bearer {access_token}"
    base = instance_url.rstrip("/")

    def query(soql: str) -> Iterator[dict[str, Any]]:
        r = http.get(f"{base}/services/data/v61.0/query", params={"q": soql})
        while True:
            r.raise_for_status()
            body = r.json()
            yield from body.get("records", [])
            if body.get("done", True) or not body.get("nextRecordsUrl"):
                return
            r = http.get(f"{base}{body['nextRecordsUrl']}")

    out = CrmRecords()
    for a in query("SELECT Id, Name, Website, BillingCountry, Description FROM Account"):
        out.companies.append(
            CrmCompany(
                a["Name"],
                clean_domain(a.get("Website")),
                f"salesforce:{a['Id']}",
                a.get("BillingCountry"),
                a.get("Description"),
            )
        )
    for c in query(
        "SELECT Id, FirstName, LastName, Email, Title, Phone, Account.Name, Account.Website FROM Contact"
    ):
        acct = c.get("Account") or {}
        out.people.append(
            CrmPerson(
                " ".join(x for x in (c.get("FirstName"), c.get("LastName")) if x),
                c.get("Email"),
                c.get("Title"),
                acct.get("Name"),
                clean_domain(acct.get("Website")),
                f"salesforce:{c['Id']}",
                c.get("Phone"),
            )
        )
    for o in query("SELECT Id, Name, StageName, Amount, Account.Name, Account.Website FROM Opportunity"):
        acct = o.get("Account") or {}
        out.deals.append(
            CrmDeal(
                o["Name"],
                o.get("StageName"),
                o.get("Amount"),
                acct.get("Name"),
                clean_domain(acct.get("Website")),
                f"salesforce:{o['Id']}",
            )
        )
    return out


def fetch_airtable(
    token: str,
    base_id: str,
    table: str,
    object_type: str,
    mapping: dict[str, str] | None = None,
    http: httpx.Client | None = None,
) -> CrmRecords:
    """Airtable tables are free-form: rows are converted to CSV-style dicts and
    mapped with the same aliases (or an explicit mapping) as CSV imports."""
    import csv
    import io

    from .csv_import import parse_csv

    http = http or httpx.Client(timeout=60)
    http.headers["Authorization"] = f"Bearer {token}"
    rows: list[dict[str, Any]] = []
    offset = None
    while True:
        r = http.get(
            f"https://api.airtable.com/v0/{base_id}/{table}",
            params={"pageSize": 100, **({"offset": offset} if offset else {})},
        )
        r.raise_for_status()
        body = r.json()
        for rec in body.get("records", []):
            fields = {
                k: ", ".join(map(str, v)) if isinstance(v, list) else v for k, v in rec["fields"].items()
            }
            rows.append({"Airtable ID": rec["id"], **fields})
        offset = body.get("offset")
        if not offset:
            break
    if not rows:
        return CrmRecords()
    headers = sorted({k for row in rows for k in row})
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=headers)
    writer.writeheader()
    writer.writerows(rows)
    _resolve_columns(headers, mapping)  # validate mapping early
    return parse_csv(buf.getvalue(), "airtable", object_type, mapping)
