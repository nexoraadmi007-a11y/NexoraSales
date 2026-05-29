from __future__ import annotations

import asyncio
from typing import Any
from urllib.parse import quote

import httpx

from src.config.settings import Settings
from src.database.repository import Repository, lead_fingerprint
from src.lead_generation.sources import LOCATION_PRIORITY, SEARCH_QUERIES, is_allowed_industry
from src.models.schemas import Industry, LeadCandidate, LeadSource
from src.utils.logging import get_logger

logger = get_logger(__name__)


class ApifyLeadScraper:
    def __init__(self, settings: Settings, repository: Repository | None = None):
        self.settings = settings
        self.repository = repository or Repository()

    async def collect(self, industry: Industry, target_count: int) -> list[LeadCandidate]:
        collected: list[LeadCandidate] = []
        seen: set[str] = set()
        for location in LOCATION_PRIORITY:
            for template in SEARCH_QUERIES[industry]:
                if len(collected) >= target_count:
                    break
                query = template.format(location=location)
                rows = await self._run_google_maps_actor(query, location)
                candidates: list[LeadCandidate] = []
                for row in rows:
                    lead = self._normalize(row, industry, location)
                    if not lead:
                        continue
                    fp = lead_fingerprint(lead.business_name, lead.location, lead.phone_number, lead.website)
                    if fp in seen:
                        continue
                    seen.add(fp)
                    candidates.append(lead)
                existing = self.repository.existing_fingerprints(
                    [lead_fingerprint(lead.business_name, lead.location, lead.phone_number, lead.website) for lead in candidates]
                )
                for lead in candidates:
                    fp = lead_fingerprint(lead.business_name, lead.location, lead.phone_number, lead.website)
                    if fp in existing:
                        continue
                    collected.append(lead)
                    if len(collected) >= target_count:
                        break
            if len(collected) >= target_count:
                break

        if len(collected) < target_count:
            logger.warning("Lead target underfilled", extra={"industry": industry.value, "fresh": len(collected), "target": target_count})
        return collected[:target_count]

    async def _run_google_maps_actor(self, query: str, location: str) -> list[dict[str, Any]]:
        actor = quote(self.settings.apify_google_maps_actor_id, safe="")
        token = self.settings.apify_api_key
        if not token:
            raise RuntimeError("APIFY_API_KEY is required for lead generation.")
        payload = {
            "searchStringsArray": [query],
            "locationQuery": location,
            "maxCrawledPlacesPerSearch": 50,
            "language": "en",
            "countryCode": "ng",
        }
        async with httpx.AsyncClient(timeout=180) as client:
            run = await client.post(
                f"https://api.apify.com/v2/acts/{actor}/runs?token={token}",
                json=payload,
            )
            self._raise_for_apify_error(run, "actor start")
            run_id = run.json()["data"]["id"]
            for _ in range(60):
                status = await client.get(f"https://api.apify.com/v2/actor-runs/{run_id}?token={token}")
                self._raise_for_apify_error(status, "actor status")
                data = status.json()["data"]
                if data["status"] == "SUCCEEDED":
                    dataset_id = data["defaultDatasetId"]
                    items = await client.get(f"https://api.apify.com/v2/datasets/{dataset_id}/items?token={token}&clean=true")
                    self._raise_for_apify_error(items, "dataset fetch")
                    return items.json()
                if data["status"] in {"FAILED", "ABORTED", "TIMED-OUT"}:
                    raise RuntimeError(f"Apify actor failed: {data['status']}")
                await asyncio.sleep(5)
        raise TimeoutError(f"Apify actor did not finish for query: {query}")

    @staticmethod
    def _raise_for_apify_error(response: httpx.Response, operation: str) -> None:
        if response.is_success:
            return
        try:
            payload = response.json()
        except ValueError:
            payload = {}
        error = payload.get("error", {}) if isinstance(payload, dict) else {}
        message = error.get("message") if isinstance(error, dict) else None
        raise RuntimeError(f"Apify {operation} failed: {response.status_code} {message or response.reason_phrase}")

    def _normalize(self, row: dict[str, Any], industry: Industry, fallback_location: str) -> LeadCandidate | None:
        name = row.get("title") or row.get("name") or row.get("businessName")
        category = row.get("categoryName") or row.get("categories")
        if not name or not is_allowed_industry(name, str(category), industry):
            return None
        phone = row.get("phone") or row.get("phoneNumber")
        website = row.get("website") or row.get("url")
        email = row.get("email")
        if not any([phone, website, email]):
            return None
        location = row.get("city") or row.get("address") or fallback_location
        size = self._estimate_size(row, industry)
        return LeadCandidate(
            business_name=name.strip(),
            industry=industry,
            location=str(location),
            phone_number=phone,
            email=email,
            website=website,
            social_url=row.get("instagram") or row.get("facebook") or row.get("linkedIn"),
            contact_person=row.get("contactPerson"),
            estimated_organization_size=size,
            source=LeadSource.google_maps,
            source_url=row.get("placeUrl") or row.get("url"),
            raw_payload=row,
        )

    @staticmethod
    def _estimate_size(row: dict[str, Any], industry: Industry) -> str:
        reviews = int(row.get("reviewsCount") or row.get("totalScoreReviews") or 0)
        if reviews >= 100:
            return "Large"
        if reviews >= 30:
            return "Medium"
        return "Small-to-medium" if industry == Industry.solar else "Medium"
