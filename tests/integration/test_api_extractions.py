"""Integration tests — extractions listing, filters, pagination."""

from __future__ import annotations


def test_extractions_list_and_get(simple_api_client) -> None:
    client, eid = simple_api_client
    listing = client.get("/api/v1/extractions?ticker=TSLA").json()
    assert listing["total"] == 1
    assert listing["items"][0]["ticker"] == "TSLA"
    assert listing["items"][0]["dated_effects"][0]["sector"] == "lithium"

    detail = client.get(f"/api/v1/extractions/ext_{eid:05d}").json()
    assert detail["id"] == f"ext_{eid:05d}"
    assert detail["filing_url"].startswith("https://www.sec.gov/")


def test_explorer_ticker_and_date_filters(demo_api_client) -> None:
    client, _ = demo_api_client
    response = client.get(
        "/api/v1/extractions",
        params={"ticker": "TSLA,GM", "from": "2026-01-01", "to": "2026-06-30"},
    )
    assert response.status_code == 200
    data = response.json()
    tickers = {item["ticker"] for item in data["items"]}
    assert tickers == {"TSLA", "GM"}
    assert data["total"] == 2

    material_response = client.get(
        "/api/v1/extractions",
        params={"material": "copper", "from": "2026-01-01", "to": "2026-12-31"},
    )
    copper_tickers = {item["ticker"] for item in material_response.json()["items"]}
    assert copper_tickers == {"TSLA", "FCX"}


def test_extraction_detail_links_to_listing(demo_api_client) -> None:
    client, _ = demo_api_client
    listing = client.get("/api/v1/extractions?ticker=TSLA").json()
    public_id = listing["items"][0]["id"]
    detail = client.get(f"/api/v1/extractions/{public_id}").json()
    assert detail["id"] == public_id
    assert detail["ticker"] == "TSLA"
    assert len(detail["dated_effects"]) == 2
    assert {e["sector"] for e in detail["dated_effects"]} == {"lithium", "copper"}


def test_sector_case_normalization_in_api(demo_api_client) -> None:
    client, _ = demo_api_client
    items = client.get("/api/v1/extractions").json()["items"]
    sectors = {e["sector"] for item in items for e in item["dated_effects"]}
    assert "lithium" in sectors
    assert "Lithium" not in sectors


def test_pagination(demo_api_client) -> None:
    client, _ = demo_api_client
    page1 = client.get("/api/v1/extractions", params={"limit": 2, "offset": 0}).json()
    page2 = client.get("/api/v1/extractions", params={"limit": 2, "offset": 2}).json()
    assert page1["total"] == 3
    assert len(page1["items"]) == 2
    assert len(page2["items"]) == 1
    ids_page1 = {item["id"] for item in page1["items"]}
    ids_page2 = {item["id"] for item in page2["items"]}
    assert ids_page1.isdisjoint(ids_page2)
