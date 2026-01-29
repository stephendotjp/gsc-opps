"""
Google Search Console API Client.
Handles OAuth 2.0 authentication and data fetching from GSC API.
Adapted for Vercel deployment with environment variables and database token storage.
"""

import os
import json
import ssl
import certifi
import httplib2
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import time

# Configure SSL certificates for serverless environments
os.environ['SSL_CERT_FILE'] = certifi.where()
os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()

# OAuth scopes required for GSC API
SCOPES = ['https://www.googleapis.com/auth/webmasters.readonly']

# GSC API limits
MAX_ROWS_PER_REQUEST = 25000
RATE_LIMIT_DELAY = 1  # seconds between API calls

# Get credentials from environment variables
GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID')
GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET')
GOOGLE_REDIRECT_URI = os.environ.get('GOOGLE_REDIRECT_URI', 'urn:ietf:wg:oauth:2.0:oob')


def get_client_config() -> Dict:
    """Get OAuth client configuration from environment variables."""
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        return None

    return {
        "installed": {
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [GOOGLE_REDIRECT_URI]
        }
    }


class GSCClient:
    """Google Search Console API Client."""

    def __init__(self):
        self.service = None
        self.credentials = None

    def is_credentials_configured(self) -> bool:
        """Check if OAuth credentials are configured via environment variables."""
        return bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET)

    def is_authenticated(self) -> bool:
        """Check if we have valid credentials."""
        # Import here to avoid circular import
        from database import get_oauth_token

        try:
            token_data = get_oauth_token()
            if not token_data:
                return False

            token_info = json.loads(token_data)
            self.credentials = Credentials(
                token=token_info.get('token'),
                refresh_token=token_info.get('refresh_token'),
                token_uri=token_info.get('token_uri', 'https://oauth2.googleapis.com/token'),
                client_id=GOOGLE_CLIENT_ID,
                client_secret=GOOGLE_CLIENT_SECRET,
                scopes=SCOPES
            )

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

        except Exception as e:
            print(f"Error loading credentials: {e}")
            return False

        return False

    def _save_token(self):
        """Save credentials token to database."""
        from database import save_oauth_token

        if self.credentials:
            token_data = {
                'token': self.credentials.token,
                'refresh_token': self.credentials.refresh_token,
                'token_uri': self.credentials.token_uri,
                'expiry': self.credentials.expiry.isoformat() if self.credentials.expiry else None
            }
            save_oauth_token(json.dumps(token_data))

    def get_auth_url(self) -> Tuple[str, any]:
        """
        Get the authorization URL for OAuth flow.
        Returns tuple of (auth_url, flow_object).
        """
        client_config = get_client_config()
        if not client_config:
            raise ValueError(
                "OAuth credentials not configured. Set GOOGLE_CLIENT_ID and "
                "GOOGLE_CLIENT_SECRET environment variables."
            )

        flow = Flow.from_client_config(
            client_config,
            scopes=SCOPES,
            redirect_uri=GOOGLE_REDIRECT_URI
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

    def authenticate_with_code_stateless(self, code: str) -> bool:
        """
        Complete OAuth flow with authorization code without needing the original flow.
        This is used for serverless environments where the flow can't be stored in memory.
        Returns True if successful.
        """
        try:
            client_config = get_client_config()
            if not client_config:
                raise ValueError("OAuth credentials not configured")

            flow = Flow.from_client_config(
                client_config,
                scopes=SCOPES,
                redirect_uri=GOOGLE_REDIRECT_URI
            )
            flow.fetch_token(code=code)
            self.credentials = flow.credentials
            self._save_token()
            return True
        except Exception as e:
            print(f"Error authenticating: {e}")
            return False

    def _get_service(self):
        """Get or create the GSC API service."""
        if self.service is None:
            if not self.is_authenticated():
                raise Exception("Not authenticated. Please authenticate first.")
            # Use httplib2 with proper SSL certificates for serverless environments
            http = httplib2.Http(ca_certs=certifi.where())
            self.service = build(
                'searchconsole', 'v1',
                credentials=self.credentials,
                cache_discovery=False  # Disable cache for serverless
            )
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
        from database import delete_oauth_token
        delete_oauth_token()
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
