/**
 * HR Ticket Triage - Dashboard Logic
 */

// API endpoints
const API_BASE = '';

// Chart instances
let categoryChart = null;
let statusChart = null;

// Chart colors
const COLORS = {
    primary: '#6366f1',
    success: '#10b981',
    warning: '#f59e0b',
    danger: '#ef4444',
    info: '#3b82f6',
    purple: '#8b5cf6',
    pink: '#ec4899',
    teal: '#14b8a6'
};

const CATEGORY_COLORS = {
    'Benefits': COLORS.primary,
    'PTO': COLORS.success,
    'Payroll': COLORS.warning,
    'Policy': COLORS.info,
    'Onboarding': COLORS.purple,
    'Offboarding': COLORS.pink,
    'Complaint': COLORS.danger,
    'General': COLORS.teal,
    'Unclassified': '#64748b'
};

const STATUS_COLORS = {
    'pending': COLORS.warning,
    'classified': COLORS.info,
    'resolved': COLORS.success
};

/**
 * Initialize dashboard
 */
document.addEventListener('DOMContentLoaded', () => {
    refreshData();

    // Auto-refresh every 10 seconds
    setInterval(refreshData, 10000);
});

/**
 * Refresh all dashboard data
 */
async function refreshData() {
    try {
        const [tickets, analytics] = await Promise.all([
            fetchTickets(),
            fetchAnalytics()
        ]);

        updateStats(analytics);
        updateCharts(analytics);
        updateTable(tickets);

    } catch (error) {
        console.error('Error fetching dashboard data:', error);
    }
}

/**
 * Fetch tickets from API
 */
async function fetchTickets() {
    const response = await fetch(`${API_BASE}/api/tickets`);
    if (!response.ok) throw new Error('Failed to fetch tickets');
    return response.json();
}

/**
 * Fetch analytics from API
 */
async function fetchAnalytics() {
    const response = await fetch(`${API_BASE}/api/analytics`);
    if (!response.ok) throw new Error('Failed to fetch analytics');
    return response.json();
}

/**
 * Update stats cards
 */
function updateStats(analytics) {
    document.getElementById('totalTickets').textContent = analytics.total_tickets || 0;
    document.getElementById('pendingTickets').textContent = analytics.status_counts?.pending || 0;
    document.getElementById('classifiedTickets').textContent = analytics.status_counts?.classified || 0;
    document.getElementById('resolvedTickets').textContent = analytics.status_counts?.resolved || 0;
}

/**
 * Update charts
 */
function updateCharts(analytics) {
    updateCategoryChart(analytics.category_counts || {});
    updateStatusChart(analytics.status_counts || {});
}

/**
 * Update category distribution chart
 */
function updateCategoryChart(categoryData) {
    const ctx = document.getElementById('categoryChart').getContext('2d');

    const labels = Object.keys(categoryData);
    const data = Object.values(categoryData);
    const colors = labels.map(label => CATEGORY_COLORS[label] || CATEGORY_COLORS['Unclassified']);

    if (categoryChart) {
        categoryChart.data.labels = labels;
        categoryChart.data.datasets[0].data = data;
        categoryChart.data.datasets[0].backgroundColor = colors;
        categoryChart.update();
    } else {
        categoryChart = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: labels,
                datasets: [{
                    data: data,
                    backgroundColor: colors,
                    borderWidth: 0
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                plugins: {
                    legend: {
                        position: 'right',
                        labels: {
                            color: '#94a3b8',
                            padding: 15
                        }
                    }
                }
            }
        });
    }
}

/**
 * Update status distribution chart
 */
function updateStatusChart(statusData) {
    const ctx = document.getElementById('statusChart').getContext('2d');

    const labels = Object.keys(statusData).map(s => s.charAt(0).toUpperCase() + s.slice(1));
    const data = Object.values(statusData);
    const colors = Object.keys(statusData).map(s => STATUS_COLORS[s] || '#64748b');

    if (statusChart) {
        statusChart.data.labels = labels;
        statusChart.data.datasets[0].data = data;
        statusChart.data.datasets[0].backgroundColor = colors;
        statusChart.update();
    } else {
        statusChart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [{
                    data: data,
                    backgroundColor: colors,
                    borderRadius: 6,
                    barThickness: 40
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                plugins: {
                    legend: {
                        display: false
                    }
                },
                scales: {
                    x: {
                        grid: {
                            display: false
                        },
                        ticks: {
                            color: '#94a3b8'
                        }
                    },
                    y: {
                        beginAtZero: true,
                        grid: {
                            color: 'rgba(148, 163, 184, 0.1)'
                        },
                        ticks: {
                            color: '#94a3b8',
                            stepSize: 1
                        }
                    }
                }
            }
        });
    }
}

/**
 * Update tickets table
 */
function updateTable(tickets) {
    const tbody = document.getElementById('ticketsTableBody');

    if (!tickets || tickets.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="7" class="empty-state">
                    No tickets yet. <a href="/">Submit your first ticket</a>
                </td>
            </tr>
        `;
        return;
    }

    // Sort by created_at descending
    tickets.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));

    tbody.innerHTML = tickets.map(ticket => `
        <tr onclick="showTicketDetail('${ticket.id}')">
            <td><code>${ticket.id.substring(0, 8)}...</code></td>
            <td>${escapeHtml(ticket.employee_name)}</td>
            <td>${escapeHtml(ticket.subject || ticket.description?.substring(0, 30) + '...')}</td>
            <td>${ticket.ai_category ? `<span class="category-badge">${ticket.ai_category}</span>` : '-'}</td>
            <td>${ticket.ai_confidence ? renderConfidence(ticket.ai_confidence) : '-'}</td>
            <td><span class="badge badge-${ticket.status}">${ticket.status}</span></td>
            <td>${formatDate(ticket.created_at)}</td>
        </tr>
    `).join('');
}

/**
 * Render confidence indicator
 */
function renderConfidence(confidence) {
    const percent = Math.round(confidence * 100);
    return `
        <div class="confidence">
            <div class="confidence-bar">
                <div class="confidence-fill" style="width: ${percent}%"></div>
            </div>
            <span class="confidence-text">${percent}%</span>
        </div>
    `;
}

/**
 * Show ticket detail modal
 */
async function showTicketDetail(ticketId) {
    try {
        const response = await fetch(`${API_BASE}/api/tickets/${ticketId}`);
        if (!response.ok) throw new Error('Failed to fetch ticket');
        const ticket = await response.json();

        const modal = document.getElementById('ticketModal');
        const details = document.getElementById('ticketDetails');

        details.innerHTML = `
            <div class="ticket-detail">
                <div class="label">Ticket ID</div>
                <div class="value"><code>${ticket.id}</code></div>
            </div>
            <div class="ticket-detail">
                <div class="label">Employee</div>
                <div class="value">${escapeHtml(ticket.employee_name)} (${escapeHtml(ticket.employee_email)})</div>
            </div>
            <div class="ticket-detail">
                <div class="label">Subject</div>
                <div class="value">${escapeHtml(ticket.subject)}</div>
            </div>
            <div class="ticket-detail">
                <div class="label">Description</div>
                <div class="value">${escapeHtml(ticket.description)}</div>
            </div>
            <div class="ticket-detail">
                <div class="label">Status</div>
                <div class="value"><span class="badge badge-${ticket.status}">${ticket.status}</span></div>
            </div>
            ${ticket.ai_category ? `
                <div class="ticket-detail">
                    <div class="label">AI Classification</div>
                    <div class="value">
                        <span class="category-badge">${ticket.ai_category}</span>
                        ${ticket.ai_confidence ? `(${Math.round(ticket.ai_confidence * 100)}% confidence)` : ''}
                    </div>
                </div>
            ` : ''}
            ${ticket.ai_response ? `
                <div class="ai-response">
                    <h4>🤖 AI Suggested Response</h4>
                    <p>${escapeHtml(ticket.ai_response)}</p>
                </div>
            ` : ''}
            <div class="ticket-detail">
                <div class="label">Created</div>
                <div class="value">${formatDate(ticket.created_at, true)}</div>
            </div>
            ${ticket.status !== 'resolved' ? `
                <div class="modal-actions" style="margin-top: 24px; text-align: right;">
                    <button class="btn btn-primary" onclick="resolveTicket('${ticket.id}')">
                        ✅ Resolve Ticket
                    </button>
                </div>
            ` : ''}
        `;

        modal.style.display = 'flex';

    } catch (error) {
        console.error('Error fetching ticket details:', error);
    }
}

/**
 * Close ticket modal
 */
function closeTicketModal() {
    document.getElementById('ticketModal').style.display = 'none';
}

// Close modal on outside click
document.getElementById('ticketModal').addEventListener('click', (e) => {
    if (e.target.id === 'ticketModal') {
        closeTicketModal();
    }
});

/**
 * Format date string
 */
function formatDate(dateStr, full = false) {
    const date = new Date(dateStr);
    if (full) {
        return date.toLocaleString();
    }
    return date.toLocaleDateString();
}

/**
 * Resolve a ticket
 */
async function resolveTicket(ticketId) {
    if (!confirm('Are you sure you want to mark this ticket as resolved?')) {
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/api/tickets/${ticketId}/resolve`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                action: 'resolved',
                user: 'Dashboard User'
            })
        });

        if (!response.ok) {
            throw new Error('Failed to resolve ticket');
        }

        // Close modal and refresh data
        closeTicketModal();
        await refreshData();

        // Show success message
        alert('✅ Ticket resolved successfully!');

    } catch (error) {
        console.error('Error resolving ticket:', error);
        alert('❌ Failed to resolve ticket. Please try again.');
    }
}

/**
 * Escape HTML to prevent XSS
 */
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
