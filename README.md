# GSC Content Opportunity Analyzer

A local web application that connects to Google Search Console API, analyzes SEO data, and identifies content opportunities.

## Features

- **Google Search Console Integration**: OAuth 2.0 authentication with automatic token refresh
- **Quick Win Keywords**: Find keywords ranking positions 4-20 with high impressions
- **CTR Optimization**: Identify pages ranking well but with low click-through rates
- **Content Expansion**: Discover pages ranking for multiple keywords
- **Content Gaps**: Find keyword clusters that need dedicated pages
- **Declining Keywords**: Track keywords losing traffic over time
- **Historical Tracking**: Store data locally for trend analysis
- **Export to CSV**: Download all analysis data

## Prerequisites

- Python 3.8 or higher
- A Google Cloud Console project with Search Console API enabled
- A website verified in Google Search Console

## Quick Start (Windows 11)

### 1. Download or Clone

Download and extract the project, or clone:
```bash
git clone <repository-url>
cd gsc-opps
```

### 2. Create Virtual Environment

Open Command Prompt or PowerShell in the project folder:
```bash
python -m venv venv
venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Set Up Google Cloud Console

Follow the steps below to create your OAuth credentials.

### 5. Run the Application

```bash
python app.py
```

Open your browser to `http://localhost:5000`

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
2. Select **External** user type
3. Click **Create**
4. Fill in:
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
├── gsc_client.py          # GSC API wrapper
├── analyzer.py            # Data analysis logic
├── database.py            # SQLite database operations
├── requirements.txt       # Python dependencies
├── templates/             # HTML templates
├── static/                # CSS and JavaScript
└── data/
    ├── credentials.json   # OAuth credentials (you add this)
    ├── token.pickle       # Auth token (auto-created)
    └── database.db        # SQLite database (auto-created)
```

## Usage

### Dashboard

The dashboard shows:
- Summary statistics (keywords, impressions, clicks, CTR)
- Opportunity breakdown chart
- Clicks and impressions over time

### Quick Wins

Keywords ranking positions 4-20 with high impressions - easiest opportunities to improve.

### CTR Optimization

Pages ranking in top 3 but with below-average CTR - improve titles and meta descriptions.

### Pages to Expand

Pages ranking for many keywords - expand these to capture more traffic.

### Content Gaps

Keyword clusters where you rank poorly - create new dedicated pages.

### Declining Keywords

Keywords losing traffic - update and refresh this content.

## Troubleshooting

### "credentials.json not found"

1. Download OAuth credentials from Google Cloud Console
2. Rename to `credentials.json`
3. Place in the `data/` folder

### "Authentication failed"

1. Check you added yourself as a test user in OAuth consent screen
2. Try deleting `data/token.pickle` and re-authenticating

### "No sites found"

1. Verify you have access to the property in Google Search Console
2. Make sure the Search Console API is enabled

## Data Storage

All data is stored locally:
- **database.db**: SQLite database with all your GSC data
- **token.pickle**: Your OAuth authentication token
- **credentials.json**: Your Google Cloud credentials

No data is sent to external servers (except Google's API).
