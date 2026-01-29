"""
Google Search Console API Client.
Handles OAuth 2.0 authentication and data fetching from GSC API.
"""

import os
import json
import pickle
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import time

# OAuth scopes required for GSC API
SCOPES = ['https://www.googleapis.com/auth/webmasters.readonly']

# File paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CREDENTIALS_FILE = os.path.join(BASE_DIR, 'data', 'credentials.json')
TOKEN_FILE = os.path.join(BASE_DIR, 'data', 'token.pickle')

# GSC API limits
MAX_ROWS_PER_REQUEST = 25000
RATE_LIMIT_DELAY = 1  # seconds between API calls


class GSCClient:
    """Google Search Console API Client."""

    def __init__(self):
        self.service = None
        self.credentials = None

    def is_credentials_file_present(self) -> bool:
        """Check if credentials.json file exists."""
        return os.path.exists(CREDENTIALS_FILE)

    def is_authenticated(self) -> bool:
        """Check if we have valid credentials."""
        if os.path.exists(TOKEN_FILE):
            with open(TOKEN_FILE, 'rb') as token:
                self.credentials = pickle.load(token)

            if self.credentials and self.credentials.valid:
                return True

            if self.credentials and self.credentials.expired and self.credentials.refresh_token:
                try:
                    self.credentials.refresh(Request())
                    self._save_token()
                    return True
                except Exception as e:
                    print(f"Error refreshing token: {e}")
                    return False

        return False

    def _save_token(self):
        """Save credentials token to file."""
        os.makedirs(os.path.dirname(TOKEN_FILE), exist_ok=True)
        with open(TOKEN_FILE, 'wb') as token:
            pickle.dump(self.credentials, token)

    def get_auth_url(self) -> Tuple[str, any]:
        """
        Get the authorization URL for OAuth flow.
        Returns tuple of (auth_url, flow_object).
        """
        if not self.is_credentials_file_present():
            raise FileNotFoundError(
                "credentials.json not found. Please download OAuth credentials from "
                "Google Cloud Console and save to data/credentials.json"
            )

        flow = InstalledAppFlow.from_client_secrets_file(
            CREDENTIALS_FILE,
            scopes=SCOPES,
            redirect_uri='urn:ietf:wg:oauth:2.0:oob'
        )

        auth_url, _ = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            prompt='consent'
        )

        return auth_url, flow

    def authenticate_with_code(self, flow, code: str) -> bool:
        """
        Complete OAuth flow with authorization code.
        Returns True if successful.
        """
        try:
            flow.fetch_token(code=code)
            self.credentials = flow.credentials
            self._save_token()
            return True
        except Exception as e:
            print(f"Error authenticating: {e}")
            return False

    def authenticate_local(self) -> bool:
        """
        Perform local OAuth flow (opens browser).
        Use this for initial setup.
        """
        if not self.is_credentials_file_present():
            raise FileNotFoundError(
                "credentials.json not found. Please download OAuth credentials from "
                "Google Cloud Console and save to data/credentials.json"
            )

        flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
        self.credentials = flow.run_local_server(port=8090)
        self._save_token()
        return True

    def _get_service(self):
        """Get or create the GSC API service."""
        if self.service is None:
            if not self.is_authenticated():
                raise Exception("Not authenticated. Please authenticate first.")
            self.service = build('searchconsole', 'v1', credentials=self.credentials)
        return self.service

    def get_sites(self) -> List[Dict]:
        """Get list of sites/properties the user has access to."""
        service = self._get_service()
        result = service.sites().list().execute()
        return result.get('siteEntry', [])

    def get_search_analytics(
        self,
        site_url: str,
        start_date: str,
        end_date: str,
        dimensions: List[str] = None,
        row_limit: int = MAX_ROWS_PER_REQUEST,
        start_row: int = 0
    ) -> List[Dict]:
        """
        Fetch search analytics data from GSC.

        Args:
            site_url: The site URL (e.g., 'sc-domain:example.com' or 'https://example.com/')
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            dimensions: List of dimensions (query, page, date, country, device)
            row_limit: Maximum rows to return (max 25000)
            start_row: Starting row for pagination

        Returns:
            List of data rows with keys, clicks, impressions, ctr, position
        """
        if dimensions is None:
            dimensions = ['query', 'page', 'date']

        service = self._get_service()

        request_body = {
            'startDate': start_date,
            'endDate': end_date,
            'dimensions': dimensions,
            'rowLimit': min(row_limit, MAX_ROWS_PER_REQUEST),
            'startRow': start_row
        }

        try:
            response = service.searchanalytics().query(
                siteUrl=site_url,
                body=request_body
            ).execute()

            rows = response.get('rows', [])

            # Transform rows to include dimension keys
            result = []
            for row in rows:
                data = {
                    'clicks': row.get('clicks', 0),
                    'impressions': row.get('impressions', 0),
                    'ctr': row.get('ctr', 0),
                    'position': row.get('position', 0)
                }

                # Map dimension values to keys
                keys = row.get('keys', [])
                for i, dim in enumerate(dimensions):
                    if i < len(keys):
                        data[dim] = keys[i]

                result.append(data)

            return result

        except HttpError as e:
            print(f"HTTP Error: {e}")
            raise

    def fetch_all_data(
        self,
        site_url: str,
        start_date: str,
        end_date: str,
        dimensions: List[str] = None,
        progress_callback=None
    ) -> List[Dict]:
        """
        Fetch all search analytics data with pagination.
        Handles GSC's 25000 row limit per request.

        Args:
            site_url: The site URL
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            dimensions: List of dimensions
            progress_callback: Optional callback function(rows_fetched, status_message)

        Returns:
            Complete list of all data rows
        """
        if dimensions is None:
            dimensions = ['query', 'page', 'date']

        all_data = []
        start_row = 0

        while True:
            if progress_callback:
                progress_callback(len(all_data), f"Fetching rows {start_row} to {start_row + MAX_ROWS_PER_REQUEST}...")

            batch = self.get_search_analytics(
                site_url=site_url,
                start_date=start_date,
                end_date=end_date,
                dimensions=dimensions,
                row_limit=MAX_ROWS_PER_REQUEST,
                start_row=start_row
            )

            if not batch:
                break

            all_data.extend(batch)
            start_row += len(batch)

            # If we got fewer rows than the limit, we've reached the end
            if len(batch) < MAX_ROWS_PER_REQUEST:
                break

            # Rate limiting to avoid hitting API limits
            time.sleep(RATE_LIMIT_DELAY)

        if progress_callback:
            progress_callback(len(all_data), f"Complete! Fetched {len(all_data)} total rows.")

        return all_data

    def fetch_data_by_month(
        self,
        site_url: str,
        months: int = 16,
        progress_callback=None
    ) -> List[Dict]:
        """
        Fetch data month by month for the specified number of months.
        GSC API has a max of 16 months of data available.

        Args:
            site_url: The site URL
            months: Number of months to fetch (default 16, max available)
            progress_callback: Optional callback function

        Returns:
            Complete list of all data
        """
        all_data = []
        end_date = datetime.now()

        # GSC data has ~3 day delay
        end_date = end_date - timedelta(days=3)

        for month_offset in range(months):
            # Calculate date range for this month
            month_end = end_date - timedelta(days=30 * month_offset)
            month_start = month_end - timedelta(days=30)

            # Don't go beyond 16 months (GSC limit)
            max_start_date = datetime.now() - timedelta(days=16 * 30)
            if month_start < max_start_date:
                month_start = max_start_date

            start_str = month_start.strftime('%Y-%m-%d')
            end_str = month_end.strftime('%Y-%m-%d')

            if progress_callback:
                progress_callback(len(all_data), f"Fetching data for {start_str} to {end_str}...")

            try:
                batch = self.fetch_all_data(
                    site_url=site_url,
                    start_date=start_str,
                    end_date=end_str
                )
                all_data.extend(batch)

            except Exception as e:
                print(f"Error fetching month {month_offset}: {e}")
                if progress_callback:
                    progress_callback(len(all_data), f"Error: {e}")
                continue

            # Small delay between months
            time.sleep(RATE_LIMIT_DELAY)

        return all_data

    def logout(self):
        """Remove stored credentials and log out."""
        if os.path.exists(TOKEN_FILE):
            os.remove(TOKEN_FILE)
        self.credentials = None
        self.service = None


def get_available_date_range() -> Tuple[str, str]:
    """
    Get the available date range for GSC data.
    Returns tuple of (start_date, end_date) in YYYY-MM-DD format.
    """
    # GSC data has ~3 day delay and max 16 months history
    end_date = datetime.now() - timedelta(days=3)
    start_date = datetime.now() - timedelta(days=16 * 30)  # ~16 months

    return start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')


# Singleton instance
_client = None


def get_client() -> GSCClient:
    """Get the singleton GSC client instance."""
    global _client
    if _client is None:
        _client = GSCClient()
    return _client
