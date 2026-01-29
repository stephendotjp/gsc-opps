"""
Database operations for GSC Content Opportunity Analyzer.
Uses PostgreSQL for Vercel deployment with connection pooling.
"""

import os
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from contextlib import contextmanager
import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2 import pool

# Database URL from environment variable (Vercel Postgres)
DATABASE_URL = os.environ.get('POSTGRES_URL') or os.environ.get('DATABASE_URL')

# Connection pool
_connection_pool = None


def get_pool():
    """Get or create the connection pool."""
    global _connection_pool
    if _connection_pool is None and DATABASE_URL:
        _connection_pool = pool.SimpleConnectionPool(
            1, 10,
            DATABASE_URL,
            sslmode='require'
        )
    return _connection_pool


@contextmanager
def get_connection():
    """Get a database connection from the pool."""
    db_pool = get_pool()
    if db_pool is None:
        raise Exception("Database not configured. Set POSTGRES_URL environment variable.")

    conn = db_pool.getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        db_pool.putconn(conn)


def get_cursor(conn):
    """Get a cursor with dict-like access."""
    return conn.cursor(cursor_factory=RealDictCursor)


def init_db():
    """Initialize the database with required tables."""
    if not DATABASE_URL:
        print("Warning: DATABASE_URL not set. Database operations will fail.")
        return

    with get_connection() as conn:
        cursor = conn.cursor()

        # Table for storing GSC properties (websites)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS properties (
                id SERIAL PRIMARY KEY,
                site_url TEXT UNIQUE NOT NULL,
                permission_level TEXT,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Main table for storing GSC query data
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS search_data (
                id SERIAL PRIMARY KEY,
                site_url TEXT NOT NULL,
                date TEXT NOT NULL,
                query TEXT NOT NULL,
                page TEXT,
                clicks INTEGER DEFAULT 0,
                impressions INTEGER DEFAULT 0,
                ctr REAL DEFAULT 0,
                position REAL DEFAULT 0,
                fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(site_url, date, query, page)
            )
        ''')

        # Table for tracking sync history
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sync_history (
                id SERIAL PRIMARY KEY,
                site_url TEXT NOT NULL,
                sync_type TEXT NOT NULL,
                start_date TEXT,
                end_date TEXT,
                rows_fetched INTEGER DEFAULT 0,
                status TEXT DEFAULT 'pending',
                error_message TEXT,
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP
            )
        ''')

        # Table for storing keyword clusters
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS keyword_clusters (
                id SERIAL PRIMARY KEY,
                site_url TEXT NOT NULL,
                cluster_name TEXT NOT NULL,
                queries TEXT NOT NULL,
                total_impressions INTEGER DEFAULT 0,
                total_clicks INTEGER DEFAULT 0,
                avg_position REAL DEFAULT 0,
                page_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Table for storing historical snapshots
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS historical_snapshots (
                id SERIAL PRIMARY KEY,
                site_url TEXT NOT NULL,
                snapshot_date TEXT NOT NULL,
                total_queries INTEGER DEFAULT 0,
                total_clicks INTEGER DEFAULT 0,
                total_impressions INTEGER DEFAULT 0,
                avg_ctr REAL DEFAULT 0,
                avg_position REAL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(site_url, snapshot_date)
            )
        ''')

        # Table for storing OAuth tokens
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS oauth_tokens (
                id SERIAL PRIMARY KEY,
                user_id TEXT UNIQUE NOT NULL DEFAULT 'default',
                token_data TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Create indexes for performance
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_search_data_site ON search_data(site_url)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_search_data_date ON search_data(date)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_search_data_query ON search_data(query)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_search_data_page ON search_data(page)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_search_data_position ON search_data(position)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_search_data_impressions ON search_data(impressions)')


def save_property(site_url: str, permission_level: str = None) -> int:
    """Save a GSC property to the database."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO properties (site_url, permission_level)
            VALUES (%s, %s)
            ON CONFLICT (site_url) DO UPDATE SET permission_level = EXCLUDED.permission_level
            RETURNING id
        ''', (site_url, permission_level))
        result = cursor.fetchone()
        return result[0] if result else 0


def get_properties() -> List[Dict]:
    """Get all stored properties."""
    with get_connection() as conn:
        cursor = get_cursor(conn)
        cursor.execute('SELECT * FROM properties ORDER BY added_at DESC')
        return [dict(row) for row in cursor.fetchall()]


def save_search_data(site_url: str, data: List[Dict]) -> int:
    """
    Save GSC search data to the database.
    Uses upsert to handle duplicates.
    Returns the number of rows inserted/updated.
    """
    if not data:
        return 0

    with get_connection() as conn:
        cursor = conn.cursor()
        rows_affected = 0

        for row in data:
            try:
                cursor.execute('''
                    INSERT INTO search_data
                    (site_url, date, query, page, clicks, impressions, ctr, position)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (site_url, date, query, page)
                    DO UPDATE SET
                        clicks = EXCLUDED.clicks,
                        impressions = EXCLUDED.impressions,
                        ctr = EXCLUDED.ctr,
                        position = EXCLUDED.position,
                        fetched_at = CURRENT_TIMESTAMP
                ''', (
                    site_url,
                    row.get('date', ''),
                    row.get('query', ''),
                    row.get('page', ''),
                    row.get('clicks', 0),
                    row.get('impressions', 0),
                    row.get('ctr', 0),
                    row.get('position', 0)
                ))
                rows_affected += 1
            except Exception as e:
                print(f"Error saving row: {e}")

        return rows_affected


def get_search_data(
    site_url: str,
    start_date: str = None,
    end_date: str = None,
    query_filter: str = None,
    page_filter: str = None,
    min_impressions: int = None,
    min_position: float = None,
    max_position: float = None,
    limit: int = None,
    offset: int = 0
) -> Tuple[List[Dict], int]:
    """
    Get search data with optional filters.
    Returns a tuple of (data, total_count).
    """
    with get_connection() as conn:
        cursor = get_cursor(conn)

        where_clauses = ['site_url = %s']
        params = [site_url]

        if start_date:
            where_clauses.append('date >= %s')
            params.append(start_date)

        if end_date:
            where_clauses.append('date <= %s')
            params.append(end_date)

        if query_filter:
            where_clauses.append('query ILIKE %s')
            params.append(f'%{query_filter}%')

        if page_filter:
            where_clauses.append('page ILIKE %s')
            params.append(f'%{page_filter}%')

        if min_impressions is not None:
            where_clauses.append('impressions >= %s')
            params.append(min_impressions)

        if min_position is not None:
            where_clauses.append('position >= %s')
            params.append(min_position)

        if max_position is not None:
            where_clauses.append('position <= %s')
            params.append(max_position)

        where_sql = ' AND '.join(where_clauses)

        # Get total count
        cursor.execute(f'SELECT COUNT(*) as count FROM search_data WHERE {where_sql}', params)
        total_count = cursor.fetchone()['count']

        # Get data with pagination
        sql = f'''
            SELECT * FROM search_data
            WHERE {where_sql}
            ORDER BY impressions DESC, clicks DESC
        '''

        if limit:
            sql += f' LIMIT {limit} OFFSET {offset}'

        cursor.execute(sql, params)
        rows = cursor.fetchall()

        return [dict(row) for row in rows], total_count


def get_aggregated_data(
    site_url: str,
    start_date: str = None,
    end_date: str = None,
    group_by: str = 'query'
) -> List[Dict]:
    """
    Get aggregated search data grouped by query or page.
    Aggregates clicks, impressions, and calculates weighted avg position.
    """
    with get_connection() as conn:
        cursor = get_cursor(conn)

        where_clauses = ['site_url = %s']
        params = [site_url]

        if start_date:
            where_clauses.append('date >= %s')
            params.append(start_date)

        if end_date:
            where_clauses.append('date <= %s')
            params.append(end_date)

        where_sql = ' AND '.join(where_clauses)

        if group_by == 'query':
            sql = f'''
                SELECT
                    query,
                    page,
                    SUM(clicks) as total_clicks,
                    SUM(impressions) as total_impressions,
                    CASE WHEN SUM(impressions) > 0
                        THEN CAST(SUM(clicks) AS FLOAT) / SUM(impressions)
                        ELSE 0
                    END as avg_ctr,
                    CASE WHEN SUM(impressions) > 0
                        THEN SUM(position * impressions) / SUM(impressions)
                        ELSE 0
                    END as avg_position
                FROM search_data
                WHERE {where_sql}
                GROUP BY query, page
                ORDER BY total_impressions DESC
            '''
        else:  # group by page
            sql = f'''
                SELECT
                    page,
                    COUNT(DISTINCT query) as query_count,
                    SUM(clicks) as total_clicks,
                    SUM(impressions) as total_impressions,
                    CASE WHEN SUM(impressions) > 0
                        THEN CAST(SUM(clicks) AS FLOAT) / SUM(impressions)
                        ELSE 0
                    END as avg_ctr,
                    CASE WHEN SUM(impressions) > 0
                        THEN SUM(position * impressions) / SUM(impressions)
                        ELSE 0
                    END as avg_position
                FROM search_data
                WHERE {where_sql}
                GROUP BY page
                ORDER BY total_impressions DESC
            '''

        cursor.execute(sql, params)
        return [dict(row) for row in cursor.fetchall()]


def get_date_range(site_url: str) -> Tuple[Optional[str], Optional[str]]:
    """Get the min and max dates in the database for a site."""
    with get_connection() as conn:
        cursor = get_cursor(conn)
        cursor.execute('''
            SELECT MIN(date) as min_date, MAX(date) as max_date
            FROM search_data
            WHERE site_url = %s
        ''', (site_url,))
        row = cursor.fetchone()
        if row:
            return row['min_date'], row['max_date']
        return None, None


def get_summary_stats(site_url: str, start_date: str = None, end_date: str = None) -> Dict:
    """Get summary statistics for a site within a date range."""
    with get_connection() as conn:
        cursor = get_cursor(conn)

        where_clauses = ['site_url = %s']
        params = [site_url]

        if start_date:
            where_clauses.append('date >= %s')
            params.append(start_date)

        if end_date:
            where_clauses.append('date <= %s')
            params.append(end_date)

        where_sql = ' AND '.join(where_clauses)

        cursor.execute(f'''
            SELECT
                COUNT(DISTINCT query) as total_keywords,
                COUNT(DISTINCT page) as total_pages,
                COALESCE(SUM(clicks), 0) as total_clicks,
                COALESCE(SUM(impressions), 0) as total_impressions,
                CASE WHEN SUM(impressions) > 0
                    THEN CAST(SUM(clicks) AS FLOAT) / SUM(impressions)
                    ELSE 0
                END as avg_ctr,
                CASE WHEN SUM(impressions) > 0
                    THEN SUM(position * impressions) / SUM(impressions)
                    ELSE 0
                END as avg_position
            FROM search_data
            WHERE {where_sql}
        ''', params)

        row = cursor.fetchone()
        if row:
            return {
                'total_keywords': row['total_keywords'] or 0,
                'total_pages': row['total_pages'] or 0,
                'total_clicks': row['total_clicks'] or 0,
                'total_impressions': row['total_impressions'] or 0,
                'avg_ctr': row['avg_ctr'] or 0,
                'avg_position': row['avg_position'] or 0
            }

        return {
            'total_keywords': 0,
            'total_pages': 0,
            'total_clicks': 0,
            'total_impressions': 0,
            'avg_ctr': 0,
            'avg_position': 0
        }


def save_sync_history(
    site_url: str,
    sync_type: str,
    start_date: str,
    end_date: str,
    status: str = 'pending'
) -> int:
    """Create a sync history record and return its ID."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO sync_history (site_url, sync_type, start_date, end_date, status)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
        ''', (site_url, sync_type, start_date, end_date, status))
        result = cursor.fetchone()
        return result[0] if result else 0


def update_sync_history(
    sync_id: int,
    status: str,
    rows_fetched: int = 0,
    error_message: str = None
):
    """Update a sync history record."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE sync_history
            SET status = %s, rows_fetched = %s, error_message = %s, completed_at = CURRENT_TIMESTAMP
            WHERE id = %s
        ''', (status, rows_fetched, error_message, sync_id))


def get_last_sync(site_url: str) -> Optional[Dict]:
    """Get the last successful sync for a site."""
    with get_connection() as conn:
        cursor = get_cursor(conn)
        cursor.execute('''
            SELECT * FROM sync_history
            WHERE site_url = %s AND status = 'completed'
            ORDER BY completed_at DESC
            LIMIT 1
        ''', (site_url,))
        row = cursor.fetchone()
        return dict(row) if row else None


def get_historical_data(
    site_url: str,
    query: str = None,
    page: str = None,
    start_date: str = None,
    end_date: str = None
) -> List[Dict]:
    """Get historical data for trend analysis."""
    with get_connection() as conn:
        cursor = get_cursor(conn)

        where_clauses = ['site_url = %s']
        params = [site_url]

        if query:
            where_clauses.append('query = %s')
            params.append(query)

        if page:
            where_clauses.append('page = %s')
            params.append(page)

        if start_date:
            where_clauses.append('date >= %s')
            params.append(start_date)

        if end_date:
            where_clauses.append('date <= %s')
            params.append(end_date)

        where_sql = ' AND '.join(where_clauses)

        cursor.execute(f'''
            SELECT
                date,
                SUM(clicks) as clicks,
                SUM(impressions) as impressions,
                CASE WHEN SUM(impressions) > 0
                    THEN CAST(SUM(clicks) AS FLOAT) / SUM(impressions)
                    ELSE 0
                END as ctr,
                CASE WHEN SUM(impressions) > 0
                    THEN SUM(position * impressions) / SUM(impressions)
                    ELSE 0
                END as position
            FROM search_data
            WHERE {where_sql}
            GROUP BY date
            ORDER BY date ASC
        ''', params)

        return [dict(row) for row in cursor.fetchall()]


def save_snapshot(
    site_url: str,
    snapshot_date: str,
    total_queries: int,
    total_clicks: int,
    total_impressions: int,
    avg_ctr: float,
    avg_position: float
):
    """Save a historical snapshot for trend tracking."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO historical_snapshots
            (site_url, snapshot_date, total_queries, total_clicks, total_impressions, avg_ctr, avg_position)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (site_url, snapshot_date)
            DO UPDATE SET
                total_queries = EXCLUDED.total_queries,
                total_clicks = EXCLUDED.total_clicks,
                total_impressions = EXCLUDED.total_impressions,
                avg_ctr = EXCLUDED.avg_ctr,
                avg_position = EXCLUDED.avg_position
        ''', (site_url, snapshot_date, total_queries, total_clicks, total_impressions, avg_ctr, avg_position))


def get_snapshots(site_url: str, limit: int = 30) -> List[Dict]:
    """Get historical snapshots for a site."""
    with get_connection() as conn:
        cursor = get_cursor(conn)
        cursor.execute('''
            SELECT * FROM historical_snapshots
            WHERE site_url = %s
            ORDER BY snapshot_date DESC
            LIMIT %s
        ''', (site_url, limit))
        return [dict(row) for row in cursor.fetchall()]


def save_keyword_clusters(site_url: str, clusters: List[Dict]):
    """Save keyword clusters to the database."""
    with get_connection() as conn:
        cursor = conn.cursor()

        # Clear existing clusters for this site
        cursor.execute('DELETE FROM keyword_clusters WHERE site_url = %s', (site_url,))

        for cluster in clusters:
            cursor.execute('''
                INSERT INTO keyword_clusters
                (site_url, cluster_name, queries, total_impressions, total_clicks, avg_position, page_count)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            ''', (
                site_url,
                cluster['name'],
                json.dumps(cluster['queries']),
                cluster.get('total_impressions', 0),
                cluster.get('total_clicks', 0),
                cluster.get('avg_position', 0),
                cluster.get('page_count', 0)
            ))


def get_keyword_clusters(site_url: str) -> List[Dict]:
    """Get keyword clusters for a site."""
    with get_connection() as conn:
        cursor = get_cursor(conn)
        cursor.execute('''
            SELECT * FROM keyword_clusters
            WHERE site_url = %s
            ORDER BY total_impressions DESC
        ''', (site_url,))

        result = []
        for row in cursor.fetchall():
            cluster = dict(row)
            cluster['queries'] = json.loads(cluster['queries'])
            result.append(cluster)
        return result


def delete_old_data(site_url: str, days_to_keep: int = 500) -> int:
    """Delete data older than specified days."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cutoff_date = (datetime.now() - timedelta(days=days_to_keep)).strftime('%Y-%m-%d')
        cursor.execute('''
            DELETE FROM search_data
            WHERE site_url = %s AND date < %s
        ''', (site_url, cutoff_date))
        return cursor.rowcount


def clear_site_data(site_url: str):
    """Clear all data for a specific site."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM search_data WHERE site_url = %s', (site_url,))
        cursor.execute('DELETE FROM sync_history WHERE site_url = %s', (site_url,))
        cursor.execute('DELETE FROM keyword_clusters WHERE site_url = %s', (site_url,))
        cursor.execute('DELETE FROM historical_snapshots WHERE site_url = %s', (site_url,))


# OAuth token storage functions
def save_oauth_token(token_data: str, user_id: str = 'default'):
    """Save OAuth token to database."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO oauth_tokens (user_id, token_data, updated_at)
            VALUES (%s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (user_id)
            DO UPDATE SET token_data = EXCLUDED.token_data, updated_at = CURRENT_TIMESTAMP
        ''', (user_id, token_data))


def get_oauth_token(user_id: str = 'default') -> Optional[str]:
    """Get OAuth token from database."""
    with get_connection() as conn:
        cursor = get_cursor(conn)
        cursor.execute('''
            SELECT token_data FROM oauth_tokens WHERE user_id = %s
        ''', (user_id,))
        row = cursor.fetchone()
        return row['token_data'] if row else None


def delete_oauth_token(user_id: str = 'default'):
    """Delete OAuth token from database."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM oauth_tokens WHERE user_id = %s', (user_id,))


# Initialize database on import if DATABASE_URL is set
if DATABASE_URL:
    try:
        init_db()
    except Exception as e:
        print(f"Warning: Could not initialize database: {e}")
