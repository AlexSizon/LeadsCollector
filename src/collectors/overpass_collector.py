"""
OpenStreetMap Overpass API collector.

Drop-in fallback for GooglePlacesCollector when no API key is available.
Returns real business data from OpenStreetMap, normalised to the same
dict schema the pipeline expects from Google Places.

No API key required. Rate limits: Nominatim ≤1 req/s, Overpass ≤1 req/3s.
"""

from __future__ import annotations

import logging
import time
from typing import Dict, List, Optional, Tuple

import requests

log = logging.getLogger(__name__)

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
OVERPASS_URL  = "https://overpass-api.de/api/interpreter"

_HEADERS = {"User-Agent": "SMBLeadAgent/1.0 (github.com/smb-lead-agent)"}

# Canonical niche label → list of OSM tag dicts to search
OSM_NICHE_TAGS: Dict[str, List[Dict[str, str]]] = {
    "restaurant":          [{"k": "amenity", "v": "restaurant"},
                            {"k": "amenity", "v": "cafe"}],
    "beauty salon":        [{"k": "shop",    "v": "beauty"},
                            {"k": "amenity", "v": "beauty_salon"}],
    "gift shop":           [{"k": "shop",    "v": "gift"}],
    "florist":             [{"k": "shop",    "v": "florist"}],
    "bakery":              [{"k": "shop",    "v": "bakery"}],
    "boutique":            [{"k": "shop",    "v": "clothes"},
                            {"k": "shop",    "v": "boutique"}],
    "cosmetics shop":      [{"k": "shop",    "v": "cosmetics"},
                            {"k": "shop",    "v": "perfumery"}],
    "specialty food shop": [{"k": "shop",    "v": "deli"},
                            {"k": "shop",    "v": "cheese"},
                            {"k": "shop",    "v": "spices"},
                            {"k": "shop",    "v": "tea"},
                            {"k": "shop",    "v": "chocolate"}],
    "pet shop":            [{"k": "shop",    "v": "pet"}],
    "home decor shop":     [{"k": "shop",    "v": "interior_decoration"},
                            {"k": "shop",    "v": "furniture"},
                            {"k": "shop",    "v": "home"}],
    "craft store":         [{"k": "shop",    "v": "craft"},
                            {"k": "shop",    "v": "art"}],
}

# Map config niche strings → canonical keys above
NICHE_NORMALIZATION: Dict[str, str] = {
    "restaurant":          "restaurant",
    "beauty salon":        "beauty salon",
    "beauty studio":       "beauty salon",
    "gift shop":           "gift shop",
    "florist":             "florist",
    "bakery":              "bakery",
    "boutique":            "boutique",
    "cosmetics shop":      "cosmetics shop",
    "specialty food shop": "specialty food shop",
    "pet shop":            "pet shop",
    "home decor shop":     "home decor shop",
    "craft store":         "craft store",
}

# Reverse map: OSM tag value → canonical niche
_TAG_VALUE_TO_NICHE: Dict[str, str] = {}
for _niche, _tag_list in OSM_NICHE_TAGS.items():
    for _tag in _tag_list:
        _TAG_VALUE_TO_NICHE[_tag["v"]] = _niche


class OverpassCollector:
    """Queries OpenStreetMap Overpass API for business POIs.

    Provides the same ``search()`` / ``get_place_details()`` interface as
    ``GooglePlacesCollector``, so the pipeline can use it transparently.

    All details are fetched in the initial search query and cached in-memory;
    ``get_place_details()`` returns from cache without additional HTTP calls.
    """

    def __init__(self, request_delay: float = 1.0) -> None:
        self.request_delay = request_delay
        self._details_cache: Dict[str, Dict] = {}
        self._geocode_cache: Dict[str, Optional[Tuple[float, float, float, float]]] = {}
        self._session = requests.Session()
        self._session.headers.update(_HEADERS)
        self.last_query_meta: Dict[str, object] = {
            "status": "success",
            "retry_count": 0,
            "error": None,
            "result_count": 0,
        }
        self._last_geocode_meta: Dict[str, object] = {
            "status": "success",
            "retry_count": 0,
            "error": None,
        }
        self._last_overpass_meta: Dict[str, object] = {
            "status": "success",
            "retry_count": 0,
            "error": None,
        }

    # ------------------------------------------------------------------
    # Public interface (matches GooglePlacesCollector)
    # ------------------------------------------------------------------

    def search(
        self,
        query: str,
        max_results: int = 20,
        language: str = "en",
        city: str = "",
        country: str = "",
        niches: Optional[List[str]] = None,
    ) -> List[Dict]:
        """Search for businesses matching the query.

        ``query`` is the same ``"<niche> in <city>"`` format the pipeline uses.
        ``city`` and ``country`` are accepted as explicit kwargs and take
        precedence over parsing the query string.
        """
        if not city or not country:
            city, country = _parse_query(query)
        self.last_query_meta = {
            "status": "success",
            "retry_count": 0,
            "error": None,
            "result_count": 0,
            "query": query,
            "city": city,
            "country": country,
        }
        if not city:
            log.warning("Could not determine city from query: %s", query)
            self.last_query_meta.update(status="upstream_error", error="city_parse_failed")
            return []

        niche_label = _extract_niche(query) if not niches else (niches[0] if niches else "")
        canonical_niche = NICHE_NORMALIZATION.get(niche_label.lower(), niche_label.lower())
        tag_list = OSM_NICHE_TAGS.get(canonical_niche, [])
        if not tag_list:
            log.warning("No OSM tag mapping for niche '%s' (query: %s)", canonical_niche, query)
            self.last_query_meta.update(status="upstream_error", error="niche_mapping_missing")
            return []

        bbox = self._geocode_city(city, country)
        if bbox is None:
            log.warning("Could not geocode city='%s' country='%s'", city, country)
            self.last_query_meta.update(
                status="geocode_failed",
                retry_count=self._last_geocode_meta.get("retry_count", 0),
                error=self._last_geocode_meta.get("error", "geocode_failed"),
                result_count=0,
            )
            return []

        elements = self._overpass_query(bbox, tag_list, max_results * 3)  # fetch extra, then cap
        results: List[Dict] = []
        seen_ids: set = set()
        for el in elements:
            osm_id = f"osm:{el['type']}:{el['id']}"
            if osm_id in seen_ids:
                continue
            seen_ids.add(osm_id)
            tags = el.get("tags", {})
            name = tags.get("name", "").strip()
            if not name:
                continue  # Skip unnamed businesses
            # Assign niche from element tags or fallback to query niche
            assigned_niche = _infer_niche(tags, canonical_niche)
            place = self._build_place_dict(osm_id, tags, el, city, country, assigned_niche)
            self._details_cache[osm_id] = place
            results.append(place)
            if len(results) >= max_results:
                break

        retry_count = (
            int(self._last_geocode_meta.get("retry_count", 0))
            + int(self._last_overpass_meta.get("retry_count", 0))
        )
        if self._last_overpass_meta.get("status") == "upstream_error":
            status = "upstream_error"
            error = self._last_overpass_meta.get("error")
        elif not results:
            status = "zero_results"
            error = None
        elif retry_count > 0:
            status = "success_after_retry"
            error = None
        else:
            status = "success"
            error = None
        self.last_query_meta.update(
            status=status,
            retry_count=retry_count,
            error=error,
            result_count=len(results),
        )
        log.info("OSM search '%s': %d results", query, len(results))
        return results

    def get_place_details(self, place_id: str, language: str = "en") -> Dict:
        """Return cached details from the search call (no additional HTTP)."""
        return self._details_cache.get(place_id, {})

    # ------------------------------------------------------------------
    # Geocoding
    # ------------------------------------------------------------------

    def _geocode_city(self, city: str, country: str) -> Optional[Tuple[float, float, float, float]]:
        """Return (south, north, west, east) bounding box for city+country.

        Successful results AND definitive 'city not found' responses are cached.
        Transient network errors are NOT cached so the next call will retry.
        """
        cache_key = f"{city.lower()}::{country.lower()}"
        self._last_geocode_meta = {
            "status": "success",
            "retry_count": 0,
            "error": None,
        }
        if cache_key in self._geocode_cache:
            return self._geocode_cache[cache_key]

        params = {
            "q": f"{city}, {country}",
            "format": "json",
            "limit": 1,
            "addressdetails": 1,
            "extratags": 0,
        }

        max_retries = 3
        backoff = 5.0
        for attempt in range(max_retries):
            time.sleep(1.1)  # Nominatim ToS: ≤1 req/s
            try:
                resp = self._session.get(NOMINATIM_URL, params=params, timeout=20)
                resp.raise_for_status()
                hits = resp.json()
                if not hits:
                    log.warning("Nominatim: no result for '%s, %s'", city, country)
                    self._last_geocode_meta = {
                        "status": "geocode_failed",
                        "retry_count": attempt,
                        "error": "geocode_not_found",
                    }
                    self._geocode_cache[cache_key] = None  # definitive miss → cache
                    return None
                bbox = hits[0]["boundingbox"]  # [min_lat, max_lat, min_lon, max_lon]
                result = (float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3]))
                log.debug("Geocoded '%s, %s' → bbox %s", city, country, result)
                self._last_geocode_meta = {
                    "status": "success",
                    "retry_count": attempt,
                    "error": None,
                }
                self._geocode_cache[cache_key] = result  # success → cache
                return result
            except Exception as exc:
                if attempt < max_retries - 1:
                    wait = backoff * (2 ** attempt)
                    log.warning(
                        "Nominatim error for '%s, %s' (retry %d/%d in %.0fs): %s",
                        city, country, attempt + 1, max_retries - 1, wait, exc,
                    )
                    time.sleep(wait)
                else:
                    log.warning(
                        "Nominatim failed for '%s, %s' after %d attempts: %s",
                        city, country, max_retries, exc,
                    )
                    self._last_geocode_meta = {
                        "status": "upstream_error",
                        "retry_count": max_retries - 1,
                        "error": "nominatim_request_failed",
                    }
                    # Do NOT cache transient failure — allow retry on next run
                    return None
        return None

    # ------------------------------------------------------------------
    # Overpass query
    # ------------------------------------------------------------------

    def _overpass_query(
        self,
        bbox: Tuple[float, float, float, float],
        tag_list: List[Dict[str, str]],
        limit: int,
    ) -> List[Dict]:
        """Run an Overpass API query for the given bbox and tag alternatives."""
        south, north, west, east = bbox
        bbox_str = f"{south},{west},{north},{east}"
        self._last_overpass_meta = {
            "status": "success",
            "retry_count": 0,
            "error": None,
        }

        # Build union of node/way queries for each tag combination
        parts: List[str] = []
        for tag in tag_list:
            k, v = tag["k"], tag["v"]
            for elem_type in ("node", "way"):
                parts.append(f'  {elem_type}["{k}"="{v}"]["name"]({bbox_str});')

        union_body = "\n".join(parts)
        query = (
            f"[out:json][timeout:60];\n"
            f"(\n{union_body}\n);\n"
            f"out body center qt {limit};"
        )

        time.sleep(self.request_delay)
        max_retries = 4
        backoff = 10.0  # seconds before first retry
        for attempt in range(max_retries):
            try:
                resp = self._session.post(
                    OVERPASS_URL,
                    data={"data": query},
                    timeout=(15, 75),  # (connect timeout, read timeout)
                )
                resp.raise_for_status()
                data = resp.json()
                self._last_overpass_meta = {
                    "status": "success",
                    "retry_count": attempt,
                    "error": None,
                }
                return data.get("elements", [])
            except Exception as exc:
                status_code = getattr(getattr(exc, "response", None), "status_code", None)
                retriable = status_code in (429, 500, 502, 503, 504) or status_code is None
                if retriable and attempt < max_retries - 1:
                    wait = backoff * (2 ** attempt)
                    log.warning(
                        "Overpass query failed (%s), retry %d/%d in %.0fs",
                        exc, attempt + 1, max_retries - 1, wait,
                    )
                    time.sleep(wait)
                else:
                    log.warning("Overpass query failed: %s", exc)
                    if status_code == 429:
                        error = "overpass_rate_limited"
                    elif status_code == 504:
                        error = "overpass_timeout"
                    else:
                        error = "overpass_request_failed"
                    self._last_overpass_meta = {
                        "status": "upstream_error",
                        "retry_count": attempt,
                        "error": error,
                    }
                    return []
        return []

    # ------------------------------------------------------------------
    # Dict normalisation (matches GooglePlacesCollector schema)
    # ------------------------------------------------------------------

    @staticmethod
    def _build_place_dict(
        osm_id: str,
        tags: Dict,
        element: Dict,
        city: str,
        country: str,
        niche: str,
    ) -> Dict:
        """Build a place dict compatible with the pipeline's expected schema."""
        # Coordinates (for ways, 'center' is injected by Overpass)
        lat = element.get("lat") or element.get("center", {}).get("lat")
        lon = element.get("lon") or element.get("center", {}).get("lon")

        # Build formatted address from OSM addr: tags
        addr_parts = []
        street = tags.get("addr:street", "")
        housenumber = tags.get("addr:housenumber", "")
        postcode = tags.get("addr:postcode", "")
        addr_city = tags.get("addr:city", city)
        if street and housenumber:
            addr_parts.append(f"{street} {housenumber}")
        elif street:
            addr_parts.append(street)
        if postcode:
            addr_parts.append(postcode)
        addr_parts.append(addr_city)
        formatted_address = ", ".join(filter(None, addr_parts))

        # Phone: try several OSM tag variations
        phone = (
            tags.get("phone") or
            tags.get("contact:phone") or
            tags.get("telephone")
        )

        # Website: try several OSM tag variations
        website = (
            tags.get("website") or
            tags.get("contact:website") or
            tags.get("url") or
            tags.get("contact:url")
        )

        # Maps URL approximation
        maps_url: Optional[str] = None
        if lat and lon:
            maps_url = f"https://www.openstreetmap.org/?mlat={lat}&mlon={lon}#map=18/{lat}/{lon}"

        name = tags.get("name", "")

        return {
            # GooglePlaces-compatible fields used by the pipeline
            "id": osm_id,
            "displayName": {"text": name},
            "formattedAddress": formatted_address,
            "businessStatus": "OPERATIONAL",  # OSM has no closure flag
            "rating": None,          # OSM has no ratings
            "userRatingCount": None, # OSM has no review counts
            # Detail fields (returned by get_place_details)
            "internationalPhoneNumber": phone,
            "websiteUri": website,
            "googleMapsUri": maps_url,
            "types": [f"{tags.get('amenity') or tags.get('shop', 'business')}"],
            # Extra metadata
            "_niche": niche,
            "_city": city,
            "_country": country,
            "_osm_tags": tags,
        }


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _parse_query(query: str) -> Tuple[str, str]:
    """Parse 'niche in City' → ('', City). Country must be passed separately."""
    lower = query.lower()
    idx = lower.rfind(" in ")
    if idx == -1:
        return "", ""
    city = query[idx + 4:].strip()
    return city, ""


def _extract_niche(query: str) -> str:
    """Extract niche label from '<niche> in <city>' query string."""
    lower = query.lower()
    idx = lower.rfind(" in ")
    if idx == -1:
        return query.strip()
    return query[:idx].strip()


def _infer_niche(tags: Dict, fallback: str) -> str:
    """Infer canonical niche from OSM tags."""
    for k in ("amenity", "shop"):
        v = tags.get(k, "")
        if v and v in _TAG_VALUE_TO_NICHE:
            return _TAG_VALUE_TO_NICHE[v]
    return fallback
