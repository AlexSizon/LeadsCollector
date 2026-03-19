"""
Collector module for interacting with the Google Places API.

This class encapsulates the logic for submitting text-based queries
for businesses and retrieving structured metadata such as name,
address, rating, review count and website URL.
"""

from typing import Dict, List, Optional
import os
import time
import requests


class GooglePlacesCollector:
    """Interface to search and fetch place details using Google Places API."""

    SEARCH_ENDPOINT = "https://places.googleapis.com/v1/places:searchText"
    DETAILS_ENDPOINT = "https://places.googleapis.com/v1/places/"

    # Business statuses considered closed/ineligible
    _EXCLUDED_STATUSES = frozenset({"PERMANENTLY_CLOSED", "CLOSED_TEMPORARILY"})

    def __init__(self, api_key: Optional[str] = None, request_delay: float = 0.3):
        """
        Parameters
        ----------
        api_key : Optional[str]
            Google Places API key. Falls back to GOOGLE_PLACES_API_KEY env var.
        request_delay : float
            Seconds to sleep between API calls to respect rate limits.
        """
        self.api_key = api_key or os.getenv("GOOGLE_PLACES_API_KEY")
        if not self.api_key:
            raise ValueError(
                "Google Places API key must be provided via argument or GOOGLE_PLACES_API_KEY env var"
            )
        self.request_delay = request_delay

    def search(self, query: str, max_results: int = 20, language: str = "en") -> List[Dict]:
        """Perform a text search for places matching the query.

        Filters out permanently or temporarily closed businesses from the
        returned list.

        Parameters
        ----------
        query : str
            Free-form search string, e.g. "dentist in Berlin".
        max_results : int
            Maximum number of place results to return.
        language : str
            ISO-639 language code for the returned results.

        Returns
        -------
        List[Dict]
            Filtered list of place dicts (no PERMANENTLY_CLOSED entries).
        """
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self.api_key,
            "X-Goog-FieldMask": "places.id,places.displayName,places.formattedAddress,places.types,places.businessStatus,places.rating,places.userRatingCount",
        }
        body = {
            "textQuery": query,
            "languageCode": language,
            "maxResultCount": max_results,
        }
        time.sleep(self.request_delay)
        response = requests.post(self.SEARCH_ENDPOINT, headers=headers, json=body)
        response.raise_for_status()
        data = response.json()
        places = data.get("places", [])
        # Filter out closed businesses
        return [
            p for p in places
            if p.get("businessStatus", "OPERATIONAL") not in self._EXCLUDED_STATUSES
        ]

    def get_place_details(self, place_id: str, language: str = "en") -> Dict:
        """Retrieve detailed information about a place using its place ID.

        Requests ratings, review counts, website URI, phone and types.
        """
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self.api_key,
            "X-Goog-FieldMask": "id,displayName,formattedAddress,internationalPhoneNumber,rating,userRatingCount,websiteUri,types,businessStatus,googleMapsUri",
        }
        url = f"{self.DETAILS_ENDPOINT}{place_id}"
        params = {"languageCode": language}
        time.sleep(self.request_delay)
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        return response.json()