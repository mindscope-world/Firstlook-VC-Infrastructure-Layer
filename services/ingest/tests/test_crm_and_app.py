import pytest
from fastapi.testclient import TestClient

from firstlook_ingest.crm import parse_csv
from firstlook_ingest.crm.csv_import import clean_domain
from firstlook_ingest.crm.importer import map_stage
from firstlook_ingest.slack import deal_message


def test_csv_vendor_headers():
    hubspot = "Record ID,First Name,Last Name,Email,Job Title,Company Name\n1,Nia,Odhiambo,nia@afya.health,CEO,AfyaLink\n"
    people = parse_csv(hubspot, "hubspot").people
    assert people[0].name == "Nia Odhiambo" and people[0].crm_id == "hubspot:1" and people[0].title == "CEO"

    sf = 'Id,Name,StageName,Amount,Account Name\n006x,Safiri Pre-seed,Closed Won,"$250,000",Safiri\n'
    deals = parse_csv(sf, "salesforce").deals
    assert (
        deals[0].amount_usd == 250000 and deals[0].stage == "Closed Won" and deals[0].company_name == "Safiri"
    )

    affinity = "Organization Id,Name,Website\n31,Baobab Capital,https://www.baobab.capital/about\n"
    companies = parse_csv(affinity, "affinity", "companies").companies
    assert companies[0].domain == "baobab.capital"

    airtable = 'Name,Emails,Company\nKofi Mensah,"kofi@solarnest.io; k@gmail.com",SolarNest\n'
    p = parse_csv(airtable, "airtable").people[0]
    assert p.email == "kofi@solarnest.io" and p.company_name == "SolarNest"


def test_helpers():
    assert clean_domain("HTTPS://www.Acme.io/path?x=1") == "acme.io"
    assert clean_domain("not a domain") is None
    assert map_stage("Closed Won") == "invested" and map_stage("due_diligence") == "diligence"
    assert map_stage("Something odd") == "sourced"
    msg = deal_message(
        {
            "type": "deal.stage_changed",
            "deal_id": "d1",
            "name": "Acme",
            "from_stage": "screening",
            "stage": "diligence",
            "actor_name": "Grace",
        },
        "http://web",
    )
    assert "Screening" in msg["text"] and "*Diligence*" in msg["text"] and "Grace" in msg["text"]


@pytest.mark.db
def test_ingest_app_auth_and_csv_import(make_tenant, llm):
    from firstlook_core.auth import Principal, issue_session
    from firstlook_core.db import tenant_tx
    from firstlook_ingest.app import app

    t, [(admin, _)] = make_tenant("Import Fund")
    with tenant_tx(t) as conn:
        from firstlook_core.tenants import create_user

        viewer, _ = create_user(conn, t, "viewer@import.vc", "Viewer", "viewer")
    client = TestClient(app)
    assert client.get("/connectors").status_code == 401

    admin_token = issue_session(Principal(admin, t, "admin", "admin@x"))
    viewer_token = issue_session(Principal(viewer, t, "viewer", "viewer@x"))
    csv = b"Record ID,First Name,Last Name,Email,Company Name,Company Domain Name\n1,Nia,O,nia@afya.health,AfyaLink,afya.health\n"

    r = client.post(
        "/imports/csv",
        data={"vendor": "hubspot"},
        files={"file": ("c.csv", csv, "text/csv")},
        headers={"Authorization": f"Bearer {viewer_token}"},
    )
    assert r.status_code == 403

    r = client.post(
        "/imports/csv",
        data={"vendor": "hubspot"},
        files={"file": ("c.csv", csv, "text/csv")},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["people"] == 1

    client.cookies.set("fl_session", admin_token)
    r = client.post("/imports/csv", data={"vendor": "hubspot"}, files={"file": ("c.csv", csv, "text/csv")})
    assert r.status_code == 409  # identical file

    assert client.get("/connectors", headers={"Authorization": f"Bearer {admin_token}"}).json() == []
    providers = client.get("/connectors/providers").json()
    assert {p["provider"] for p in providers} == {"google", "microsoft", "zoom", "google_meet"}
