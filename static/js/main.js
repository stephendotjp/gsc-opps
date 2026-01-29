/**
 * GSC Content Opportunity Analyzer - Main JavaScript
 */

// Global state
const GSCAnalyzer = {
    currentSite: null,
    dateRange: {
        start: null,
        end: null
    }
};

/**
 * Initialize the application
 */
document.addEventListener('DOMContentLoaded', function() {
    initializeApp();
});

function initializeApp() {
    // Initialize any global handlers
    setupFlashMessageDismissal();
    setupTableSorting();
    setupSearchHandlers();
}

/**
 * Auto-dismiss flash messages after 5 seconds
 */
function setupFlashMessageDismissal() {
    const flashMessages = document.querySelectorAll('[data-flash-message]');
    flashMessages.forEach(function(message) {
        setTimeout(function() {
            message.style.opacity = '0';
            message.style.transition = 'opacity 0.3s ease';
            setTimeout(function() {
                message.remove();
            }, 300);
        }, 5000);
    });
}

/**
 * Setup client-side table sorting
 */
function setupTableSorting() {
    const sortableHeaders = document.querySelectorAll('th[data-sortable]');
    sortableHeaders.forEach(function(header) {
        header.style.cursor = 'pointer';
        header.addEventListener('click', function() {
            const table = header.closest('table');
            const column = header.dataset.column;
            const currentOrder = header.dataset.order || 'asc';
            const newOrder = currentOrder === 'asc' ? 'desc' : 'asc';

            sortTable(table, column, newOrder);
            header.dataset.order = newOrder;

            // Update sort indicators
            sortableHeaders.forEach(h => h.classList.remove('sorted-asc', 'sorted-desc'));
            header.classList.add('sorted-' + newOrder);
        });
    });
}

/**
 * Sort table by column
 */
function sortTable(table, column, order) {
    const tbody = table.querySelector('tbody');
    const rows = Array.from(tbody.querySelectorAll('tr'));

    rows.sort(function(a, b) {
        const aCell = a.querySelector(`td[data-column="${column}"]`) || a.cells[column];
        const bCell = b.querySelector(`td[data-column="${column}"]`) || b.cells[column];

        let aValue = aCell ? aCell.textContent.trim() : '';
        let bValue = bCell ? bCell.textContent.trim() : '';

        // Try to parse as numbers
        const aNum = parseFloat(aValue.replace(/[^0-9.-]/g, ''));
        const bNum = parseFloat(bValue.replace(/[^0-9.-]/g, ''));

        if (!isNaN(aNum) && !isNaN(bNum)) {
            return order === 'asc' ? aNum - bNum : bNum - aNum;
        }

        // String comparison
        return order === 'asc'
            ? aValue.localeCompare(bValue)
            : bValue.localeCompare(aValue);
    });

    // Re-append sorted rows
    rows.forEach(row => tbody.appendChild(row));
}

/**
 * Setup search handlers
 */
function setupSearchHandlers() {
    const searchInputs = document.querySelectorAll('[data-search-input]');
    searchInputs.forEach(function(input) {
        let debounceTimer;
        input.addEventListener('input', function() {
            clearTimeout(debounceTimer);
            debounceTimer = setTimeout(function() {
                filterTable(input);
            }, 300);
        });
    });
}

/**
 * Filter table based on search input
 */
function filterTable(input) {
    const searchTerm = input.value.toLowerCase();
    const tableId = input.dataset.tableId;
    const table = document.getElementById(tableId);

    if (!table) return;

    const rows = table.querySelectorAll('tbody tr');

    rows.forEach(function(row) {
        const text = row.textContent.toLowerCase();
        row.style.display = text.includes(searchTerm) ? '' : 'none';
    });

    // Update count if there's a counter element
    const counter = document.querySelector('[data-results-count]');
    if (counter) {
        const visibleRows = table.querySelectorAll('tbody tr:not([style*="display: none"])');
        counter.textContent = visibleRows.length;
    }
}

/**
 * Format numbers with commas
 */
function formatNumber(num) {
    return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ',');
}

/**
 * Format percentage
 */
function formatPercent(num, decimals = 2) {
    return num.toFixed(decimals) + '%';
}

/**
 * Show loading indicator
 */
function showLoading(message = 'Loading...') {
    const modal = document.getElementById('loading-modal');
    if (modal) {
        const title = document.getElementById('loading-title');
        if (title) title.textContent = message;
        modal.classList.remove('hidden');
    }
}

/**
 * Hide loading indicator
 */
function hideLoading() {
    const modal = document.getElementById('loading-modal');
    if (modal) {
        modal.classList.add('hidden');
    }
}

/**
 * Show a toast notification
 */
function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `fixed bottom-4 right-4 px-6 py-3 rounded-lg shadow-lg text-white z-50 fade-in ${
        type === 'success' ? 'bg-green-500' :
        type === 'error' ? 'bg-red-500' :
        type === 'warning' ? 'bg-yellow-500' :
        'bg-blue-500'
    }`;
    toast.textContent = message;

    document.body.appendChild(toast);

    setTimeout(function() {
        toast.style.opacity = '0';
        toast.style.transition = 'opacity 0.3s ease';
        setTimeout(function() {
            toast.remove();
        }, 300);
    }, 3000);
}

/**
 * Copy text to clipboard
 */
function copyToClipboard(text) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(function() {
            showToast('Copied to clipboard!', 'success');
        }).catch(function() {
            fallbackCopy(text);
        });
    } else {
        fallbackCopy(text);
    }
}

function fallbackCopy(text) {
    const textarea = document.createElement('textarea');
    textarea.value = text;
    textarea.style.position = 'fixed';
    textarea.style.left = '-9999px';
    document.body.appendChild(textarea);
    textarea.select();

    try {
        document.execCommand('copy');
        showToast('Copied to clipboard!', 'success');
    } catch (err) {
        showToast('Failed to copy', 'error');
    }

    document.body.removeChild(textarea);
}

/**
 * Debounce function
 */
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

/**
 * Throttle function
 */
function throttle(func, limit) {
    let inThrottle;
    return function(...args) {
        if (!inThrottle) {
            func.apply(this, args);
            inThrottle = true;
            setTimeout(() => inThrottle = false, limit);
        }
    };
}

/**
 * API helper functions
 */
const API = {
    /**
     * Make a GET request
     */
    get: async function(url) {
        try {
            const response = await fetch(url);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return await response.json();
        } catch (error) {
            console.error('API GET error:', error);
            throw error;
        }
    },

    /**
     * Make a POST request
     */
    post: async function(url, data) {
        try {
            const response = await fetch(url, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(data)
            });
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return await response.json();
        } catch (error) {
            console.error('API POST error:', error);
            throw error;
        }
    },

    /**
     * Sync data from GSC
     */
    syncData: async function(type = 'recent') {
        showLoading(type === 'full' ? 'Full sync in progress...' : 'Syncing recent data...');
        try {
            const result = await this.post('/api/sync', { type: type });
            hideLoading();
            if (result.success) {
                showToast(`Synced ${formatNumber(result.rows_fetched)} rows`, 'success');
                return result;
            } else {
                throw new Error(result.error || 'Sync failed');
            }
        } catch (error) {
            hideLoading();
            showToast('Sync failed: ' + error.message, 'error');
            throw error;
        }
    },

    /**
     * Get summary stats
     */
    getStats: async function(days = 90) {
        return await this.get(`/api/stats?days=${days}`);
    },

    /**
     * Get opportunities
     */
    getOpportunities: async function(days = 90) {
        return await this.get(`/api/opportunities?days=${days}`);
    },

    /**
     * Get action list
     */
    getActionList: async function(days = 90) {
        return await this.get(`/api/action-list?days=${days}`);
    }
};

/**
 * Chart utilities
 */
const ChartUtils = {
    /**
     * Create a line chart
     */
    createLineChart: function(ctx, labels, datasets, options = {}) {
        return new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: datasets
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: {
                    mode: 'index',
                    intersect: false
                },
                plugins: {
                    legend: {
                        position: 'top'
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true
                    }
                },
                ...options
            }
        });
    },

    /**
     * Create a doughnut chart
     */
    createDoughnutChart: function(ctx, labels, data, colors, options = {}) {
        return new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: labels,
                datasets: [{
                    data: data,
                    backgroundColor: colors
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'right'
                    }
                },
                ...options
            }
        });
    },

    /**
     * Create a bar chart
     */
    createBarChart: function(ctx, labels, data, color, options = {}) {
        return new Chart(ctx, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [{
                    data: data,
                    backgroundColor: color
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true
                    }
                },
                ...options
            }
        });
    }
};

/**
 * Export utilities
 */
const ExportUtils = {
    /**
     * Export table to CSV
     */
    tableToCSV: function(tableId) {
        const table = document.getElementById(tableId);
        if (!table) return '';

        const rows = [];
        const headers = [];

        // Get headers
        table.querySelectorAll('thead th').forEach(th => {
            headers.push('"' + th.textContent.trim().replace(/"/g, '""') + '"');
        });
        rows.push(headers.join(','));

        // Get data rows
        table.querySelectorAll('tbody tr').forEach(tr => {
            const row = [];
            tr.querySelectorAll('td').forEach(td => {
                row.push('"' + td.textContent.trim().replace(/"/g, '""') + '"');
            });
            rows.push(row.join(','));
        });

        return rows.join('\n');
    },

    /**
     * Download CSV
     */
    downloadCSV: function(csv, filename) {
        const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
        const link = document.createElement('a');
        const url = URL.createObjectURL(blob);

        link.setAttribute('href', url);
        link.setAttribute('download', filename);
        link.style.visibility = 'hidden';

        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    },

    /**
     * Export table and download
     */
    exportTable: function(tableId, filename) {
        const csv = this.tableToCSV(tableId);
        this.downloadCSV(csv, filename);
    }
};

// Make utilities available globally
window.GSCAnalyzer = GSCAnalyzer;
window.API = API;
window.ChartUtils = ChartUtils;
window.ExportUtils = ExportUtils;
window.formatNumber = formatNumber;
window.formatPercent = formatPercent;
window.showLoading = showLoading;
window.hideLoading = hideLoading;
window.showToast = showToast;
window.copyToClipboard = copyToClipboard;
