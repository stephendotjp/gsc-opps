# GSC Content Opportunity Analyzer

A web application that connects to Google Search Console API, analyzes SEO data, and identifies content opportunities. The app helps you find keywords to target, pages to expand, and new content to create.

**Deployment Options:**
- Local development with SQLite
- Production deployment on Railway with PostgreSQL

## Features

- **Google Search Console Integration**: OAuth 2.0 authentication with automatic token refresh
- **Quick Win Keywords**: Find keywords ranking positions 4-20 with high impressions
- **CTR Optimization**: Identify pages ranking well but with low click-through rates
- **Content Expansion**: Discover pages ranking for multiple keywords
- **Content Gaps**: Find keyword clusters that need dedicated pages
- **Declining Keywords**: Track keywords losing traffic over time
- **Historical Tracking**: Store data locally for trend analysis
- **Export to CSV**: Download all analysis data for further processing

## Prerequisites

- Python 3.8 or higher
- A Google Cloud Console project with Search Console API enabled
- A website verified in Google Search Console

## Quick Start

### 1. Clone the Repository

```bash
git clone <repository-url>
cd gsc-opps
```

### 2. Create Virtual Environment

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Set Up Google Cloud Console

Follow the detailed instructions below to create your OAuth credentials.

### 5. Run the Application

```bash
python app.py
```

Open your browser to `http://localhost:5000`

## Railway Deployment

Railway is the recommended platform for this app - it provides persistent servers with no timeout limits, making it ideal for data processing tasks.

### Prerequisites for Railway

- A [Railway account](https://railway.app) (free tier available)
- Google Cloud OAuth credentials configured for web application

### Step 1: Deploy to Railway

1. Push your code to GitHub
2. Go to [Railway](https://railway.app) and click **New Project**
3. Select **Deploy from GitHub repo**
4. Choose your repository

### Step 2: Add PostgreSQL Database

1. In your Railway project, click **New** → **Database** → **PostgreSQL**
2. Railway will automatically create `DATABASE_URL` environment variable
3. Add a new variable: `POSTGRES_URL` = `${{Postgres.DATABASE_URL}}`

### Step 3: Configure Google OAuth for Web

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Select your project (or create one following the setup below)
3. Go to **APIs & Services** > **Credentials**
4. Click **Create Credentials** > **OAuth client ID**
5. Select **Web application** (not Desktop app)
6. Add your Railway domain to **Authorized redirect URIs**:
   - `https://your-app.up.railway.app/oauth-callback`
   - For custom domains: `https://yourdomain.com/oauth-callback`
7. Click **Create** and note the **Client ID** and **Client Secret**

### Step 4: Set Environment Variables

In Railway dashboard, go to your service → **Variables** and add:

```env
# Google OAuth
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-client-secret
GOOGLE_REDIRECT_URI=https://your-app.up.railway.app/oauth-callback

# Flask
SECRET_KEY=generate-a-secure-random-string

# Database (reference the PostgreSQL service)
POSTGRES_URL=${{Postgres.DATABASE_URL}}
```

### Step 5: Deploy

Railway will automatically deploy when you push to GitHub. The database tables are created automatically on first request.

### Railway Environment Variables Reference

| Variable | Description | Required |
|----------|-------------|----------|
| `POSTGRES_URL` | PostgreSQL connection string | Yes |
| `GOOGLE_CLIENT_ID` | OAuth 2.0 Client ID | Yes |
| `GOOGLE_CLIENT_SECRET` | OAuth 2.0 Client Secret | Yes |
| `GOOGLE_REDIRECT_URI` | OAuth callback URL | Yes |
| `SECRET_KEY` | Flask session secret | Yes |

## Google Cloud Console Setup

### Step 1: Create a Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click **Select a project** > **New Project**
3. Enter a project name (e.g., "GSC Analyzer")
4. Click **Create**

### Step 2: Enable the Search Console API

1. In your project, go to **APIs & Services** > **Library**
2. Search for "Google Search Console API"
3. Click on it and press **Enable**

### Step 3: Configure OAuth Consent Screen

1. Go to **APIs & Services** > **OAuth consent screen**
2. Select **External** user type (unless you have Google Workspace)
3. Click **Create**
4. Fill in the required fields:
   - **App name**: GSC Analyzer
   - **User support email**: Your email
   - **Developer contact**: Your email
5. Click **Save and Continue**
6. On Scopes page, click **Add or Remove Scopes**
7. Find and select `https://www.googleapis.com/auth/webmasters.readonly`
8. Click **Update** > **Save and Continue**
9. Add your email as a test user
10. Click **Save and Continue** > **Back to Dashboard**

### Step 4: Create OAuth Credentials

1. Go to **APIs & Services** > **Credentials**
2. Click **Create Credentials** > **OAuth client ID**
3. Select **Desktop app** as the application type
4. Name it "GSC Analyzer"
5. Click **Create**
6. Click **Download JSON**
7. Rename the downloaded file to `credentials.json`
8. Move it to the `data/` folder in your project

### Step 5: Authenticate

1. Start the application: `python app.py`
2. Open `http://localhost:5000` in your browser
3. Click **Connect with Google**
4. Follow the authorization flow
5. Copy the authorization code and paste it in the app
6. Select your website property
7. Click **Sync Data** to fetch your data

## Project Structure

```
gsc-opps/
├── app.py                 # Main Flask application
├── gsc_client.py         # GSC API wrapper
├── analyzer.py           # Data analysis logic
├── database.py           # PostgreSQL database operations
├── requirements.txt      # Python dependencies
├── README.md            # This file
├── .env.example         # Environment variables template
├── .gitignore           # Git ignore rules
├── Procfile             # Railway/Heroku process configuration
├── railway.json         # Railway deployment configuration
├── templates/
│   ├── base.html        # Base template
│   ├── index.html       # Dashboard
│   ├── auth.html        # Authentication page
│   ├── auth-start.html  # OAuth flow page
│   ├── settings.html    # Settings page
│   ├── quick-wins.html  # Quick wins analysis
│   ├── ctr-optimization.html
│   ├── expand-content.html
│   ├── content-gaps.html
│   ├── declining.html
│   ├── all-keywords.html
│   └── error.html
├── static/
│   ├── css/
│   │   └── style.css
│   └── js/
│       └── main.js
└── data/
    └── .gitkeep         # Placeholder for local development
```

## Usage Guide

### Dashboard

The dashboard shows:
- Summary statistics (keywords, impressions, clicks, CTR)
- Opportunity breakdown chart
- Clicks and impressions over time
- Quick access to all analysis sections

### Quick Wins

Keywords ranking positions 4-20 with high impressions. These are the easiest opportunities because:
- You're already close to page 1
- Minor content improvements can push you up
- High impressions mean lots of potential clicks

**Actions to take:**
- Add the target keyword to your title and H1
- Expand content to cover the topic more comprehensively
- Improve internal linking to the page

### CTR Optimization

Pages ranking in top 3 positions but with below-average CTR. This indicates:
- Your title tag isn't compelling
- Your meta description doesn't match search intent
- Rich snippets might be taking your clicks

**Actions to take:**
- Rewrite title tags with compelling hooks
- Add clear value propositions to meta descriptions
- Implement structured data for rich snippets

### Pages to Expand

Pages already ranking for many keywords have proven topical authority. Expanding these pages can:
- Capture more long-tail variations
- Improve rankings for existing keywords
- Establish stronger topical authority

**Actions to take:**
- Add sections covering related subtopics
- Include FAQs addressing common questions
- Add more examples, case studies, or data

### Content Gaps

Keyword clusters where you rank poorly (position 20+) despite getting impressions. This means:
- People are searching for these topics
- You don't have dedicated content
- Creating new pages could capture this traffic

**Actions to take:**
- Create a new, comprehensive page for each cluster
- Target the highest-impression keywords
- Link to existing related content

### Declining Keywords

Keywords that have lost significant traffic compared to previous periods. Causes include:
- Content becoming outdated
- Competitors publishing better content
- Search intent changes
- Algorithm updates

**Actions to take:**
- Update content with fresh information
- Improve formatting and readability
- Add new sections or media
- Check competitor content for gaps

## Configuration

### Environment Variables

Create a `.env` file based on `.env.example`:

```env
# Flask configuration
SECRET_KEY=your-secret-key-change-this
DEBUG=true
PORT=5000
```

### Database

Data is stored in PostgreSQL (for Railway deployment). The database includes:
- **search_data**: All GSC query data
- **properties**: Tracked websites
- **sync_history**: Data sync records
- **keyword_clusters**: Generated clusters
- **historical_snapshots**: Trend data
- **oauth_tokens**: OAuth credentials (replaces local token.pickle)

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/sync` | POST | Sync data from GSC |
| `/api/stats` | GET | Get summary statistics |
| `/api/historical` | GET | Get historical data |
| `/api/opportunities` | GET | Get opportunity summary |
| `/api/action-list` | GET | Get prioritized actions |
| `/api/export/<type>` | GET | Export data as CSV |

## Troubleshooting

### "Google credentials not configured" (Railway)

Make sure you have set these environment variables in Railway:
- `GOOGLE_CLIENT_ID`
- `GOOGLE_CLIENT_SECRET`
- `GOOGLE_REDIRECT_URI`

### "Database connection failed" (Railway)

1. Check that `POSTGRES_URL` is correctly set (use `${{Postgres.DATABASE_URL}}` to reference Railway's PostgreSQL)
2. Verify the PostgreSQL service is running in your Railway project
3. Ensure the connection string includes SSL if required

### "Authentication failed"

1. Check that you added yourself as a test user in OAuth consent screen
2. Make sure you selected the correct Google account
3. Verify the redirect URI matches exactly what's configured in Google Cloud Console
4. For Railway: ensure `GOOGLE_REDIRECT_URI` matches your deployed URL (e.g., `https://your-app.up.railway.app/oauth-callback`)

### "No sites found"

1. Verify you have access to the property in [Google Search Console](https://search.google.com/search-console)
2. Try both URL prefix and domain property formats
3. Ensure the API is enabled in Google Cloud Console

### "Sync taking too long"

Large sites may take several minutes. The app fetches up to 25,000 rows per API call. For sites with millions of queries:
1. Start with a shorter date range (7-28 days)
2. Run syncs during off-peak hours
3. Consider filtering by specific pages

### "No data showing"

1. Make sure you've synced data first
2. Check the date range selector
3. Verify data exists in the database by checking the sync history in Settings

## Data Retention

- GSC API provides up to 16 months of historical data
- The app stores all fetched data locally
- Data older than 500 days is automatically cleaned up
- You can manually clear data in Settings

## Privacy & Security

- For Railway: Data is stored in your PostgreSQL database
- OAuth tokens are securely stored in the database
- Credentials are managed via environment variables
- No data is shared with third parties beyond Google's API

## Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

See [LICENSE](LICENSE) file for details.

## Support

For issues and feature requests, please use the GitHub issue tracker.
