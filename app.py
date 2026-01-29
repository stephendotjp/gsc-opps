"""
GSC Content Opportunity Analyzer - Main Flask Application.
A local web application that connects to Google Search Console API,
analyzes SEO data, and identifies content opportunities.
"""

import os
from datetime import datetime, timedelta
from functools import wraps

from flask import (
    Flask, render_template, request, jsonify, redirect, url_for,
    session, flash, Response
)
from dotenv import load_dotenv

import database as db
import analyzer
from gsc_client import get_client, get_available_date_range

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'gsc-analyzer-secret-key-change-in-production')

# Store OAuth flow in session (for multi-step auth)
oauth_flows = {}


def get_date_range_from_request():
    """Get date range from request args or use defaults."""
    days = request.args.get('days', '90')

    if days == 'custom':
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
    else:
        days = int(days)
        end_date = (datetime.now() - timedelta(days=3)).strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=days + 3)).strftime('%Y-%m-%d')

    return start_date, end_date


def get_current_site():
    """Get the currently selected site from session."""
    return session.get('current_site')


def site_required(f):
    """Decorator to ensure a site is selected."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not get_current_site():
            flash('Please select a website first.', 'warning')
            return redirect(url_for('settings'))
        return f(*args, **kwargs)
    return decorated_function


def auth_required(f):
    """Decorator to ensure user is authenticated."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        client = get_client()
        if not client.is_authenticated():
            flash('Please authenticate with Google Search Console first.', 'warning')
            return redirect(url_for('auth'))
        return f(*args, **kwargs)
    return decorated_function


# ============================================================================
# Main Routes
# ============================================================================

@app.route('/')
def index():
    """Dashboard home page."""
    client = get_client()

    if not client.is_authenticated():
        return redirect(url_for('auth'))

    site_url = get_current_site()
    if not site_url:
        return redirect(url_for('settings'))

    start_date, end_date = get_date_range_from_request()
    days = request.args.get('days', '90')

    # Get summary stats
    stats = db.get_summary_stats(site_url, start_date, end_date)
    last_sync = db.get_last_sync(site_url)

    # Get opportunity summary
    opportunities = analyzer.get_opportunity_summary(site_url, start_date, end_date)

    # Get historical data for charts
    historical = db.get_historical_data(site_url, start_date=start_date, end_date=end_date)

    return render_template('index.html',
        site_url=site_url,
        stats=stats,
        opportunities=opportunities,
        last_sync=last_sync,
        historical=historical,
        start_date=start_date,
        end_date=end_date,
        days=days
    )


@app.route('/quick-wins')
@auth_required
@site_required
def quick_wins():
    """Quick win keywords page."""
    site_url = get_current_site()
    start_date, end_date = get_date_range_from_request()
    days = request.args.get('days', '90')

    # Get filter params
    min_impressions = int(request.args.get('min_impressions', 100))
    min_position = float(request.args.get('min_position', 4))
    max_position = float(request.args.get('max_position', 20))

    keywords = analyzer.get_quick_wins(
        site_url, start_date, end_date,
        min_position=min_position,
        max_position=max_position,
        min_impressions=min_impressions,
        limit=200
    )

    return render_template('quick-wins.html',
        site_url=site_url,
        keywords=keywords,
        start_date=start_date,
        end_date=end_date,
        days=days,
        min_impressions=min_impressions,
        min_position=min_position,
        max_position=max_position
    )


@app.route('/ctr-optimization')
@auth_required
@site_required
def ctr_optimization():
    """CTR optimization page."""
    site_url = get_current_site()
    start_date, end_date = get_date_range_from_request()
    days = request.args.get('days', '90')

    # Get filter params
    max_position = float(request.args.get('max_position', 3))
    max_ctr = float(request.args.get('max_ctr', 20)) / 100
    min_impressions = int(request.args.get('min_impressions', 50))

    keywords = analyzer.get_ctr_opportunities(
        site_url, start_date, end_date,
        max_position=max_position,
        max_ctr=max_ctr,
        min_impressions=min_impressions,
        limit=200
    )

    return render_template('ctr-optimization.html',
        site_url=site_url,
        keywords=keywords,
        start_date=start_date,
        end_date=end_date,
        days=days,
        max_position=max_position,
        max_ctr=max_ctr * 100,
        min_impressions=min_impressions
    )


@app.route('/expand-content')
@auth_required
@site_required
def expand_content():
    """Pages to expand page."""
    site_url = get_current_site()
    start_date, end_date = get_date_range_from_request()
    days = request.args.get('days', '90')

    min_keywords = int(request.args.get('min_keywords', 5))

    pages = analyzer.get_pages_to_expand(
        site_url, start_date, end_date,
        min_keywords=min_keywords,
        limit=200
    )

    return render_template('expand-content.html',
        site_url=site_url,
        pages=pages,
        start_date=start_date,
        end_date=end_date,
        days=days,
        min_keywords=min_keywords
    )


@app.route('/content-gaps')
@auth_required
@site_required
def content_gaps():
    """Content gaps page."""
    site_url = get_current_site()
    start_date, end_date = get_date_range_from_request()
    days = request.args.get('days', '90')

    min_position = float(request.args.get('min_position', 20))
    min_impressions = int(request.args.get('min_impressions', 50))

    gaps = analyzer.get_content_gaps(
        site_url, start_date, end_date,
        min_position=min_position,
        min_impressions=min_impressions,
        limit=100
    )

    return render_template('content-gaps.html',
        site_url=site_url,
        gaps=gaps,
        start_date=start_date,
        end_date=end_date,
        days=days,
        min_position=min_position,
        min_impressions=min_impressions
    )


@app.route('/declining')
@auth_required
@site_required
def declining():
    """Declining keywords page."""
    site_url = get_current_site()
    days = request.args.get('days', '90')

    min_previous_clicks = int(request.args.get('min_clicks', 50))
    min_decline = float(request.args.get('min_decline', 30))

    keywords = analyzer.get_declining_keywords(
        site_url,
        min_previous_clicks=min_previous_clicks,
        min_decline_percent=min_decline,
        limit=200
    )

    return render_template('declining.html',
        site_url=site_url,
        keywords=keywords,
        days=days,
        min_previous_clicks=min_previous_clicks,
        min_decline=min_decline
    )


@app.route('/all-keywords')
@auth_required
@site_required
def all_keywords():
    """All keywords page with search and pagination."""
    site_url = get_current_site()
    start_date, end_date = get_date_range_from_request()
    days = request.args.get('days', '90')

    # Pagination and sorting
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 50))
    search = request.args.get('search', '')
    sort_by = request.args.get('sort', 'impressions')
    sort_order = request.args.get('order', 'desc')

    keywords, total_count, total_pages = analyzer.get_all_keywords(
        site_url, start_date, end_date,
        search=search,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        per_page=per_page
    )

    return render_template('all-keywords.html',
        site_url=site_url,
        keywords=keywords,
        start_date=start_date,
        end_date=end_date,
        days=days,
        page=page,
        per_page=per_page,
        total_count=total_count,
        total_pages=total_pages,
        search=search,
        sort_by=sort_by,
        sort_order=sort_order
    )


# ============================================================================
# Authentication Routes
# ============================================================================

@app.route('/auth')
def auth():
    """Authentication page."""
    client = get_client()

    has_credentials = client.is_credentials_file_present()
    is_authenticated = client.is_authenticated()

    return render_template('auth.html',
        has_credentials=has_credentials,
        is_authenticated=is_authenticated
    )


@app.route('/auth/start')
def auth_start():
    """Start OAuth flow."""
    client = get_client()

    if not client.is_credentials_file_present():
        flash('Please add credentials.json to the data folder first.', 'error')
        return redirect(url_for('auth'))

    try:
        auth_url, flow = client.get_auth_url()
        # Store flow for later use
        flow_id = str(datetime.now().timestamp())
        oauth_flows[flow_id] = flow
        session['oauth_flow_id'] = flow_id

        return render_template('auth-start.html', auth_url=auth_url)
    except Exception as e:
        flash(f'Error starting authentication: {str(e)}', 'error')
        return redirect(url_for('auth'))


@app.route('/auth/callback', methods=['POST'])
def auth_callback():
    """Handle OAuth callback with authorization code."""
    code = request.form.get('code', '').strip()
    flow_id = session.get('oauth_flow_id')

    if not code:
        flash('Please enter the authorization code.', 'error')
        return redirect(url_for('auth_start'))

    if not flow_id or flow_id not in oauth_flows:
        flash('Authentication session expired. Please try again.', 'error')
        return redirect(url_for('auth'))

    client = get_client()
    flow = oauth_flows.pop(flow_id)

    if client.authenticate_with_code(flow, code):
        flash('Successfully authenticated with Google Search Console!', 'success')
        return redirect(url_for('settings'))
    else:
        flash('Authentication failed. Please try again.', 'error')
        return redirect(url_for('auth'))


@app.route('/auth/logout')
def auth_logout():
    """Log out and clear credentials."""
    client = get_client()
    client.logout()
    session.clear()
    flash('Successfully logged out.', 'success')
    return redirect(url_for('auth'))


# ============================================================================
# Settings Routes
# ============================================================================

@app.route('/settings')
@auth_required
def settings():
    """Settings page - site selection and data sync."""
    client = get_client()

    # Get available sites
    try:
        sites = client.get_sites()
    except Exception as e:
        flash(f'Error fetching sites: {str(e)}', 'error')
        sites = []

    current_site = get_current_site()

    # Get stored properties with sync info
    stored_properties = db.get_properties()

    # Get sync info for current site
    last_sync = None
    date_range = (None, None)
    if current_site:
        last_sync = db.get_last_sync(current_site)
        date_range = db.get_date_range(current_site)

    return render_template('settings.html',
        sites=sites,
        current_site=current_site,
        stored_properties=stored_properties,
        last_sync=last_sync,
        date_range=date_range
    )


@app.route('/settings/select-site', methods=['POST'])
@auth_required
def select_site():
    """Select a site to analyze."""
    site_url = request.form.get('site_url')

    if site_url:
        session['current_site'] = site_url
        db.save_property(site_url)
        flash(f'Selected site: {site_url}', 'success')
    else:
        flash('Please select a valid site.', 'error')

    return redirect(url_for('settings'))


# ============================================================================
# API Routes
# ============================================================================

@app.route('/api/sync', methods=['POST'])
@auth_required
def api_sync():
    """Sync data from GSC API."""
    site_url = get_current_site()
    if not site_url:
        return jsonify({'error': 'No site selected'}), 400

    sync_type = request.json.get('type', 'recent')  # 'recent' or 'full'

    client = get_client()

    # Calculate date range
    if sync_type == 'full':
        start_date, end_date = get_available_date_range()
    else:
        # Last 90 days
        end_date = (datetime.now() - timedelta(days=3)).strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=93)).strftime('%Y-%m-%d')

    # Create sync record
    sync_id = db.save_sync_history(site_url, sync_type, start_date, end_date, 'in_progress')

    try:
        # Fetch data
        data = client.fetch_all_data(site_url, start_date, end_date)

        # Save to database
        rows_saved = db.save_search_data(site_url, data)

        # Update sync record
        db.update_sync_history(sync_id, 'completed', rows_saved)

        return jsonify({
            'success': True,
            'rows_fetched': len(data),
            'rows_saved': rows_saved,
            'start_date': start_date,
            'end_date': end_date
        })

    except Exception as e:
        db.update_sync_history(sync_id, 'failed', error_message=str(e))
        return jsonify({'error': str(e)}), 500


@app.route('/api/stats')
@auth_required
@site_required
def api_stats():
    """Get summary statistics."""
    site_url = get_current_site()
    start_date, end_date = get_date_range_from_request()

    stats = db.get_summary_stats(site_url, start_date, end_date)
    return jsonify(stats)


@app.route('/api/historical')
@auth_required
@site_required
def api_historical():
    """Get historical data for charts."""
    site_url = get_current_site()
    start_date, end_date = get_date_range_from_request()

    data = db.get_historical_data(site_url, start_date=start_date, end_date=end_date)
    return jsonify(data)


@app.route('/api/opportunities')
@auth_required
@site_required
def api_opportunities():
    """Get opportunity summary."""
    site_url = get_current_site()
    start_date, end_date = get_date_range_from_request()

    opportunities = analyzer.get_opportunity_summary(site_url, start_date, end_date)
    return jsonify(opportunities)


@app.route('/api/export/<opportunity_type>')
@auth_required
@site_required
def api_export(opportunity_type):
    """Export opportunities as CSV."""
    site_url = get_current_site()
    start_date, end_date = get_date_range_from_request()

    csv_content = analyzer.export_opportunities_csv(
        site_url, start_date, end_date, opportunity_type
    )

    filename = f"gsc-{opportunity_type}-{datetime.now().strftime('%Y%m%d')}.csv"

    return Response(
        csv_content,
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename={filename}'}
    )


@app.route('/api/action-list')
@auth_required
@site_required
def api_action_list():
    """Get prioritized action list."""
    site_url = get_current_site()
    start_date, end_date = get_date_range_from_request()

    actions = analyzer.generate_action_list(site_url, start_date, end_date)
    return jsonify(actions)


# ============================================================================
# Error Handlers
# ============================================================================

@app.errorhandler(404)
def not_found(e):
    return render_template('error.html', error='Page not found', code=404), 404


@app.errorhandler(500)
def server_error(e):
    return render_template('error.html', error='Internal server error', code=500), 500


# ============================================================================
# Template Filters
# ============================================================================

@app.template_filter('format_number')
def format_number(value):
    """Format large numbers with commas."""
    try:
        return '{:,}'.format(int(value))
    except (ValueError, TypeError):
        return value


@app.template_filter('format_percent')
def format_percent(value):
    """Format percentage values."""
    try:
        return '{:.2f}%'.format(float(value))
    except (ValueError, TypeError):
        return value


@app.template_filter('format_position')
def format_position(value):
    """Format position values."""
    try:
        return '{:.1f}'.format(float(value))
    except (ValueError, TypeError):
        return value


@app.template_filter('truncate_url')
def truncate_url(url, length=50):
    """Truncate URL for display."""
    if len(url) > length:
        return url[:length] + '...'
    return url


# ============================================================================
# Main Entry Point
# ============================================================================

if __name__ == '__main__':
    # Initialize database
    db.init_db()

    # Run Flask app
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('DEBUG', 'true').lower() == 'true'

    print(f"\n{'='*60}")
    print("GSC Content Opportunity Analyzer")
    print(f"{'='*60}")
    print(f"Starting server on http://localhost:{port}")
    print(f"Debug mode: {debug}")
    print(f"{'='*60}\n")

    app.run(host='0.0.0.0', port=port, debug=debug)
