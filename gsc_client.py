"""
Google Search Console API Client.
Handles OAuth 2.0 authentication and data fetching from GSC API.
For local use with credentials.json file.
"""

import os
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

# GSC API limits
MAX_ROWS_PER_REQUEST = 25000
RATE_LIMIT_DELAY = 1  # seconds between API calls

# File paths
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
CREDENTIALS_FILE = os.path.join(DATA_DIR, 'credentials.json')
TOKEN_FILE = os.path.join(DATA_DIR, 'token.pickle')


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
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(TOKEN_FILE, 'wb') as token:
            pickle.dump(self.credentials, token)

    def get_auth_url(self) -> Tuple[str, any]:
        """
        Get the authorization URL for OAuth flow.
        Returns tuple of (auth_url, flow_object).
        """
        if not self.is_credentials_file_present():
            raise FileNotFoundError(
                f"credentials.json not found. Please download it from Google Cloud Console "
                f"and place it in the {DATA_DIR} folder."
            )

        flow = InstalledAppFlow.from_client_secrets_file(
            CREDENTIALS_FILE,
            SCOPES,
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

    def logout(self):
        """Clear stored credentials."""
        if os.path.exists(TOKEN_FILE):
            os.remove(TOKEN_FILE)
        self.credentials = None
        self.service = None

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
            List of data rows
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

            # Process the rows to flatten the keys array
            processed_rows = []
            for row in rows:
                processed_row = {
                    'clicks': row.get('clicks', 0),
                    'impressions': row.get('impressions', 0),
                    'ctr': row.get('ctr', 0),
                    'position': row.get('position', 0)
                }

                # Map keys to dimension names
                keys = row.get('keys', [])
                for i, dim in enumerate(dimensions):
                    if i < len(keys):
                        processed_row[dim] = keys[i]

                processed_rows.append(processed_row)

            return processed_rows

        except HttpError as e:
            print(f"Error fetching search analytics: {e}")
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
        Fetch all search analytics data with automatic pagination.

        Args:
            site_url: The site URL
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            dimensions: List of dimensions
            progress_callback: Optional callback for progress updates

        Returns:
            List of all data rows
        """
        if dimensions is None:
            dimensions = ['query', 'page', 'date']

        all_rows = []
        start_row = 0

        while True:
            if progress_callback:
                progress_callback(len(all_rows))

            rows = self.get_search_analytics(
                site_url=site_url,
                start_date=start_date,
                end_date=end_date,
                dimensions=dimensions,
                row_limit=MAX_ROWS_PER_REQUEST,
                start_row=start_row
            )

            if not rows:
                break

            all_rows.extend(rows)
            start_row += len(rows)

            # If we got fewer rows than the limit, we've reached the end
            if len(rows) < MAX_ROWS_PER_REQUEST:
                break

            # Rate limiting
            time.sleep(RATE_LIMIT_DELAY)

        return all_rows

    def get_date_range_data(
        self,
        site_url: str,
        days: int = 90,
        dimensions: List[str] = None,
        progress_callback=None
    ) -> List[Dict]:
        """
        Fetch data for the last N days.

        Args:
            site_url: The site URL
            days: Number of days to fetch (default 90)
            dimensions: List of dimensions
            progress_callback: Optional callback for progress updates

        Returns:
            List of all data rows
        """
        end_date = (datetime.now() - timedelta(days=3)).strftime('%Y-%m-%d')  # GSC has 3-day delay
        start_date = (datetime.now() - timedelta(days=days + 3)).strftime('%Y-%m-%d')

        return self.fetch_all_data(
            site_url=site_url,
            start_date=start_date,
            end_date=end_date,
            dimensions=dimensions,
            progress_callback=progress_callback
        )
