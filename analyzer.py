"""
Content Opportunity Analyzer for GSC data.
Identifies quick wins, CTR opportunities, content gaps, and declining keywords.
"""

import re
from collections import defaultdict
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional
import database as db


def get_quick_wins(
    site_url: str,
    start_date: str,
    end_date: str,
    min_position: float = 4,
    max_position: float = 20,
    min_impressions: int = 100,
    limit: int = 100
) -> List[Dict]:
    """
    Find quick win keywords: high impressions, position 4-20.
    These are keywords close to page 1 that could be improved with minor effort.

    Priority Score = Impressions × (1 / Position)
    Higher score = better opportunity.
    """
    data = db.get_aggregated_data(site_url, start_date, end_date, group_by='query')

    quick_wins = []
    for row in data:
        position = row.get('avg_position', 0)
        impressions = row.get('total_impressions', 0)

        if min_position <= position <= max_position and impressions >= min_impressions:
            # Calculate opportunity score
            priority_score = impressions * (1 / position) if position > 0 else 0

            # Estimate potential clicks if position improved to top 3
            # Using average CTR for position 1-3 (~15-30%)
            current_ctr = row.get('avg_ctr', 0)
            potential_ctr = 0.25  # Assume 25% CTR if top 3
            potential_clicks = int(impressions * potential_ctr)
            current_clicks = row.get('total_clicks', 0)
            click_uplift = potential_clicks - current_clicks

            quick_wins.append({
                'query': row.get('query', ''),
                'page': row.get('page', ''),
                'position': round(position, 1),
                'impressions': impressions,
                'clicks': current_clicks,
                'ctr': round(current_ctr * 100, 2),
                'priority_score': round(priority_score, 2),
                'potential_clicks': potential_clicks,
                'click_uplift': max(0, click_uplift),
                'opportunity_type': 'quick_win'
            })

    # Sort by priority score descending
    quick_wins.sort(key=lambda x: x['priority_score'], reverse=True)

    return quick_wins[:limit]


def get_ctr_opportunities(
    site_url: str,
    start_date: str,
    end_date: str,
    max_position: float = 3,
    max_ctr: float = 0.20,
    min_impressions: int = 50,
    limit: int = 100
) -> List[Dict]:
    """
    Find low CTR opportunities: ranking in top 3 but low click-through rate.
    These pages need better titles/meta descriptions.

    Industry average CTR for top 3 positions is ~30-40%.
    """
    data = db.get_aggregated_data(site_url, start_date, end_date, group_by='query')

    opportunities = []
    for row in data:
        position = row.get('avg_position', 0)
        ctr = row.get('avg_ctr', 0)
        impressions = row.get('total_impressions', 0)

        if position <= max_position and ctr < max_ctr and impressions >= min_impressions:
            # Expected CTR based on position
            expected_ctr = get_expected_ctr(position)
            ctr_gap = expected_ctr - ctr

            # Calculate potential additional clicks
            current_clicks = row.get('total_clicks', 0)
            potential_clicks = int(impressions * expected_ctr)
            click_uplift = potential_clicks - current_clicks

            opportunities.append({
                'query': row.get('query', ''),
                'page': row.get('page', ''),
                'position': round(position, 1),
                'impressions': impressions,
                'clicks': current_clicks,
                'ctr': round(ctr * 100, 2),
                'expected_ctr': round(expected_ctr * 100, 2),
                'ctr_gap': round(ctr_gap * 100, 2),
                'potential_clicks': potential_clicks,
                'click_uplift': max(0, click_uplift),
                'opportunity_type': 'ctr_optimization',
                'priority': 'high' if ctr_gap > 0.15 else 'medium' if ctr_gap > 0.10 else 'low'
            })

    # Sort by CTR gap descending (biggest opportunity first)
    opportunities.sort(key=lambda x: x['ctr_gap'], reverse=True)

    return opportunities[:limit]


def get_expected_ctr(position: float) -> float:
    """
    Get expected CTR based on position.
    Based on industry averages from various CTR studies.
    """
    ctr_by_position = {
        1: 0.32,
        2: 0.24,
        3: 0.18,
        4: 0.13,
        5: 0.10,
        6: 0.07,
        7: 0.06,
        8: 0.05,
        9: 0.04,
        10: 0.03
    }

    pos = round(position)
    if pos <= 0:
        return 0.32
    if pos > 10:
        return 0.02

    return ctr_by_position.get(pos, 0.03)


def get_pages_to_expand(
    site_url: str,
    start_date: str,
    end_date: str,
    min_keywords: int = 5,
    limit: int = 100
) -> List[Dict]:
    """
    Find pages that rank for multiple keywords.
    These are good candidates for content expansion.
    """
    data = db.get_aggregated_data(site_url, start_date, end_date, group_by='query')

    # Group by page
    page_data = defaultdict(lambda: {
        'keywords': [],
        'total_clicks': 0,
        'total_impressions': 0,
        'positions': [],
        'keyword_details': []
    })

    for row in data:
        page = row.get('page', '')
        if not page:
            continue

        page_data[page]['keywords'].append(row.get('query', ''))
        page_data[page]['total_clicks'] += row.get('total_clicks', 0)
        page_data[page]['total_impressions'] += row.get('total_impressions', 0)
        page_data[page]['positions'].append(row.get('avg_position', 0))
        page_data[page]['keyword_details'].append({
            'query': row.get('query', ''),
            'impressions': row.get('total_impressions', 0),
            'clicks': row.get('total_clicks', 0),
            'position': round(row.get('avg_position', 0), 1)
        })

    # Filter and format results
    pages_to_expand = []
    for page, data in page_data.items():
        keyword_count = len(data['keywords'])
        if keyword_count >= min_keywords:
            # Calculate keyword diversity score
            # Higher diversity = more opportunity to consolidate/expand
            avg_position = sum(data['positions']) / len(data['positions']) if data['positions'] else 0

            # Sort keyword details by impressions
            top_keywords = sorted(
                data['keyword_details'],
                key=lambda x: x['impressions'],
                reverse=True
            )[:10]

            pages_to_expand.append({
                'page': page,
                'keyword_count': keyword_count,
                'total_clicks': data['total_clicks'],
                'total_impressions': data['total_impressions'],
                'avg_position': round(avg_position, 1),
                'top_keywords': top_keywords,
                'opportunity_type': 'expand_content',
                'priority': 'high' if keyword_count >= 20 else 'medium' if keyword_count >= 10 else 'low'
            })

    # Sort by keyword count descending
    pages_to_expand.sort(key=lambda x: x['keyword_count'], reverse=True)

    return pages_to_expand[:limit]


def get_content_gaps(
    site_url: str,
    start_date: str,
    end_date: str,
    min_position: float = 20,
    min_impressions: int = 50,
    min_cluster_size: int = 2,
    limit: int = 50
) -> List[Dict]:
    """
    Find content gaps: keyword clusters without dedicated pages.
    Groups similar keywords that could benefit from a new dedicated page.
    """
    data = db.get_aggregated_data(site_url, start_date, end_date, group_by='query')

    # Filter for keywords ranking poorly (no dedicated content)
    poor_ranking = []
    for row in data:
        position = row.get('avg_position', 0)
        impressions = row.get('total_impressions', 0)

        if position >= min_position and impressions >= min_impressions:
            poor_ranking.append({
                'query': row.get('query', ''),
                'page': row.get('page', ''),
                'position': position,
                'impressions': impressions,
                'clicks': row.get('total_clicks', 0)
            })

    # Cluster similar keywords
    clusters = cluster_keywords(poor_ranking)

    # Format results
    content_gaps = []
    for cluster_name, cluster_data in clusters.items():
        if len(cluster_data['queries']) >= min_cluster_size:
            content_gaps.append({
                'cluster_name': cluster_name,
                'queries': cluster_data['queries'],
                'query_count': len(cluster_data['queries']),
                'total_impressions': cluster_data['total_impressions'],
                'total_clicks': cluster_data['total_clicks'],
                'best_position': cluster_data['best_position'],
                'current_pages': list(cluster_data['pages'])[:5],
                'suggested_action': f"Create dedicated page for '{cluster_name}' topic",
                'opportunity_type': 'content_gap',
                'priority': 'high' if cluster_data['total_impressions'] > 500 else 'medium'
            })

    # Sort by total impressions descending
    content_gaps.sort(key=lambda x: x['total_impressions'], reverse=True)

    return content_gaps[:limit]


def cluster_keywords(keywords: List[Dict], min_shared_words: int = 2) -> Dict:
    """
    Cluster keywords based on shared words.
    Simple but effective clustering for SEO purposes.
    """
    clusters = defaultdict(lambda: {
        'queries': [],
        'total_impressions': 0,
        'total_clicks': 0,
        'best_position': 100,
        'pages': set()
    })

    # Stopwords to ignore
    stopwords = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been',
                 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
                 'would', 'could', 'should', 'may', 'might', 'must', 'shall',
                 'can', 'need', 'dare', 'ought', 'used', 'to', 'of', 'in',
                 'for', 'on', 'with', 'at', 'by', 'from', 'up', 'about',
                 'into', 'over', 'after', 'and', 'but', 'or', 'not', 'what',
                 'which', 'who', 'whom', 'this', 'that', 'these', 'those',
                 'am', 'than', 'how', 'when', 'where', 'why', 'all', 'each',
                 'every', 'both', 'few', 'more', 'most', 'other', 'some',
                 'such', 'no', 'nor', 'only', 'own', 'same', 'so', 'just', 'vs'}

    for kw in keywords:
        query = kw.get('query', '').lower()
        words = set(re.findall(r'\b\w+\b', query)) - stopwords

        if len(words) < 2:
            # Single word queries go to their own cluster
            cluster_name = query
        else:
            # Use the most significant words as cluster name
            # Sort by length (longer words usually more specific)
            significant_words = sorted(words, key=len, reverse=True)[:3]
            cluster_name = ' '.join(sorted(significant_words))

        clusters[cluster_name]['queries'].append({
            'query': kw.get('query', ''),
            'impressions': kw.get('impressions', 0),
            'clicks': kw.get('clicks', 0),
            'position': kw.get('position', 0)
        })
        clusters[cluster_name]['total_impressions'] += kw.get('impressions', 0)
        clusters[cluster_name]['total_clicks'] += kw.get('clicks', 0)
        clusters[cluster_name]['best_position'] = min(
            clusters[cluster_name]['best_position'],
            kw.get('position', 100)
        )
        if kw.get('page'):
            clusters[cluster_name]['pages'].add(kw.get('page'))

    return dict(clusters)


def get_declining_keywords(
    site_url: str,
    comparison_months: int = 3,
    min_previous_clicks: int = 50,
    min_decline_percent: float = 30,
    limit: int = 100
) -> List[Dict]:
    """
    Find keywords that have declined significantly.
    Compares recent period to previous period.
    """
    now = datetime.now()

    # Recent period (last 30 days)
    recent_end = now - timedelta(days=3)
    recent_start = recent_end - timedelta(days=30)

    # Previous period (comparison_months ago)
    previous_end = recent_start - timedelta(days=30 * (comparison_months - 1))
    previous_start = previous_end - timedelta(days=30)

    # Get data for both periods
    recent_data = db.get_aggregated_data(
        site_url,
        recent_start.strftime('%Y-%m-%d'),
        recent_end.strftime('%Y-%m-%d'),
        group_by='query'
    )

    previous_data = db.get_aggregated_data(
        site_url,
        previous_start.strftime('%Y-%m-%d'),
        previous_end.strftime('%Y-%m-%d'),
        group_by='query'
    )

    # Create lookup for previous data
    previous_lookup = {
        (row['query'], row['page']): row
        for row in previous_data
    }

    # Find declining keywords
    declining = []
    for row in recent_data:
        key = (row['query'], row['page'])
        if key in previous_lookup:
            prev = previous_lookup[key]
            prev_clicks = prev.get('total_clicks', 0)
            curr_clicks = row.get('total_clicks', 0)

            if prev_clicks >= min_previous_clicks:
                decline = prev_clicks - curr_clicks
                decline_percent = (decline / prev_clicks * 100) if prev_clicks > 0 else 0

                if decline_percent >= min_decline_percent:
                    declining.append({
                        'query': row.get('query', ''),
                        'page': row.get('page', ''),
                        'previous_clicks': prev_clicks,
                        'current_clicks': curr_clicks,
                        'decline': decline,
                        'decline_percent': round(decline_percent, 1),
                        'previous_position': round(prev.get('avg_position', 0), 1),
                        'current_position': round(row.get('avg_position', 0), 1),
                        'position_change': round(
                            row.get('avg_position', 0) - prev.get('avg_position', 0), 1
                        ),
                        'previous_impressions': prev.get('total_impressions', 0),
                        'current_impressions': row.get('total_impressions', 0),
                        'opportunity_type': 'declining',
                        'priority': 'high' if decline_percent >= 50 else 'medium'
                    })

    # Sort by decline descending
    declining.sort(key=lambda x: x['decline'], reverse=True)

    return declining[:limit]


def get_all_keywords(
    site_url: str,
    start_date: str,
    end_date: str,
    search: str = None,
    sort_by: str = 'impressions',
    sort_order: str = 'desc',
    page: int = 1,
    per_page: int = 50
) -> Tuple[List[Dict], int, int]:
    """
    Get all keywords with pagination and filtering.
    Returns tuple of (data, total_count, total_pages).
    """
    data = db.get_aggregated_data(site_url, start_date, end_date, group_by='query')

    # Filter by search term
    if search:
        search_lower = search.lower()
        data = [row for row in data if search_lower in row.get('query', '').lower()
                or search_lower in row.get('page', '').lower()]

    # Sort
    reverse = sort_order == 'desc'
    sort_key = {
        'impressions': lambda x: x.get('total_impressions', 0),
        'clicks': lambda x: x.get('total_clicks', 0),
        'ctr': lambda x: x.get('avg_ctr', 0),
        'position': lambda x: x.get('avg_position', 0),
        'query': lambda x: x.get('query', '').lower()
    }.get(sort_by, lambda x: x.get('total_impressions', 0))

    if sort_by == 'position':
        # For position, lower is better, so reverse the sort
        reverse = not reverse

    data.sort(key=sort_key, reverse=reverse)

    # Pagination
    total_count = len(data)
    total_pages = (total_count + per_page - 1) // per_page
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page

    paginated_data = data[start_idx:end_idx]

    # Format data
    formatted = []
    for row in paginated_data:
        formatted.append({
            'query': row.get('query', ''),
            'page': row.get('page', ''),
            'impressions': row.get('total_impressions', 0),
            'clicks': row.get('total_clicks', 0),
            'ctr': round(row.get('avg_ctr', 0) * 100, 2),
            'position': round(row.get('avg_position', 0), 1)
        })

    return formatted, total_count, total_pages


def get_opportunity_summary(site_url: str, start_date: str, end_date: str) -> Dict:
    """
    Get a summary of all opportunities for the dashboard.
    """
    quick_wins = get_quick_wins(site_url, start_date, end_date, limit=10)
    ctr_opps = get_ctr_opportunities(site_url, start_date, end_date, limit=10)
    pages_expand = get_pages_to_expand(site_url, start_date, end_date, limit=10)
    content_gaps = get_content_gaps(site_url, start_date, end_date, limit=10)
    declining = get_declining_keywords(site_url, limit=10)

    # Calculate total potential impact
    total_quick_win_uplift = sum(kw.get('click_uplift', 0) for kw in quick_wins)
    total_ctr_uplift = sum(kw.get('click_uplift', 0) for kw in ctr_opps)

    return {
        'quick_wins': {
            'count': len(quick_wins),
            'top_items': quick_wins[:5],
            'potential_clicks': total_quick_win_uplift
        },
        'ctr_opportunities': {
            'count': len(ctr_opps),
            'top_items': ctr_opps[:5],
            'potential_clicks': total_ctr_uplift
        },
        'pages_to_expand': {
            'count': len(pages_expand),
            'top_items': pages_expand[:5]
        },
        'content_gaps': {
            'count': len(content_gaps),
            'top_items': content_gaps[:5],
            'total_impressions': sum(g.get('total_impressions', 0) for g in content_gaps)
        },
        'declining_keywords': {
            'count': len(declining),
            'top_items': declining[:5],
            'total_decline': sum(d.get('decline', 0) for d in declining)
        },
        'total_opportunities': (
            len(quick_wins) + len(ctr_opps) + len(pages_expand) +
            len(content_gaps) + len(declining)
        )
    }


def generate_action_list(
    site_url: str,
    start_date: str,
    end_date: str
) -> List[Dict]:
    """
    Generate a prioritized action list for content improvement.
    """
    actions = []

    # Quick wins - top 10
    quick_wins = get_quick_wins(site_url, start_date, end_date, limit=10)
    for i, kw in enumerate(quick_wins):
        actions.append({
            'priority': i + 1,
            'type': 'Quick Win',
            'query': kw['query'],
            'page': kw['page'],
            'action': f"Optimize content for '{kw['query']}' - currently position {kw['position']}",
            'potential_impact': f"+{kw['click_uplift']} clicks",
            'metrics': f"Position: {kw['position']}, Impressions: {kw['impressions']}"
        })

    # CTR opportunities - top 5
    ctr_opps = get_ctr_opportunities(site_url, start_date, end_date, limit=5)
    for i, kw in enumerate(ctr_opps):
        actions.append({
            'priority': len(quick_wins) + i + 1,
            'type': 'CTR Optimization',
            'query': kw['query'],
            'page': kw['page'],
            'action': f"Improve title/description for '{kw['query']}' - CTR only {kw['ctr']}%",
            'potential_impact': f"+{kw['click_uplift']} clicks",
            'metrics': f"Position: {kw['position']}, CTR: {kw['ctr']}%, Expected: {kw['expected_ctr']}%"
        })

    # Content gaps - top 5
    content_gaps = get_content_gaps(site_url, start_date, end_date, limit=5)
    for i, gap in enumerate(content_gaps):
        actions.append({
            'priority': len(quick_wins) + len(ctr_opps) + i + 1,
            'type': 'Content Gap',
            'query': gap['cluster_name'],
            'page': 'New page needed',
            'action': f"Create new content for '{gap['cluster_name']}' cluster",
            'potential_impact': f"{gap['total_impressions']} impressions available",
            'metrics': f"Queries: {gap['query_count']}, Best position: {gap['best_position']}"
        })

    return actions


def export_opportunities_csv(
    site_url: str,
    start_date: str,
    end_date: str,
    opportunity_type: str = 'all'
) -> str:
    """
    Generate CSV content for opportunities export.
    Returns CSV as a string.
    """
    import csv
    from io import StringIO

    output = StringIO()
    writer = csv.writer(output)

    if opportunity_type in ['all', 'quick_wins']:
        writer.writerow(['Quick Win Keywords'])
        writer.writerow(['Query', 'Page', 'Position', 'Impressions', 'Clicks', 'CTR', 'Potential Clicks', 'Click Uplift'])
        for kw in get_quick_wins(site_url, start_date, end_date, limit=100):
            writer.writerow([
                kw['query'], kw['page'], kw['position'], kw['impressions'],
                kw['clicks'], kw['ctr'], kw['potential_clicks'], kw['click_uplift']
            ])
        writer.writerow([])

    if opportunity_type in ['all', 'ctr']:
        writer.writerow(['CTR Opportunities'])
        writer.writerow(['Query', 'Page', 'Position', 'Impressions', 'Clicks', 'CTR', 'Expected CTR', 'Click Uplift'])
        for kw in get_ctr_opportunities(site_url, start_date, end_date, limit=100):
            writer.writerow([
                kw['query'], kw['page'], kw['position'], kw['impressions'],
                kw['clicks'], kw['ctr'], kw['expected_ctr'], kw['click_uplift']
            ])
        writer.writerow([])

    if opportunity_type in ['all', 'expand']:
        writer.writerow(['Pages to Expand'])
        writer.writerow(['Page', 'Keyword Count', 'Total Impressions', 'Total Clicks', 'Avg Position', 'Top Keywords'])
        for page in get_pages_to_expand(site_url, start_date, end_date, limit=100):
            top_kw = ', '.join([k['query'] for k in page['top_keywords'][:5]])
            writer.writerow([
                page['page'], page['keyword_count'], page['total_impressions'],
                page['total_clicks'], page['avg_position'], top_kw
            ])
        writer.writerow([])

    if opportunity_type in ['all', 'gaps']:
        writer.writerow(['Content Gaps'])
        writer.writerow(['Cluster', 'Query Count', 'Total Impressions', 'Total Clicks', 'Best Position', 'Sample Queries'])
        for gap in get_content_gaps(site_url, start_date, end_date, limit=100):
            sample = ', '.join([q['query'] for q in gap['queries'][:5]])
            writer.writerow([
                gap['cluster_name'], gap['query_count'], gap['total_impressions'],
                gap['total_clicks'], gap['best_position'], sample
            ])
        writer.writerow([])

    if opportunity_type in ['all', 'declining']:
        writer.writerow(['Declining Keywords'])
        writer.writerow(['Query', 'Page', 'Previous Clicks', 'Current Clicks', 'Decline %', 'Previous Position', 'Current Position'])
        for kw in get_declining_keywords(site_url, limit=100):
            writer.writerow([
                kw['query'], kw['page'], kw['previous_clicks'], kw['current_clicks'],
                kw['decline_percent'], kw['previous_position'], kw['current_position']
            ])

    return output.getvalue()
