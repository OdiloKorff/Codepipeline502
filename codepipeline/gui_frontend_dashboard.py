"""
GUI Frontend Dashboard für CodePipeline.

Implementiert:
- ID 414: GUI Frontend – Dashboard
- Frontend-Templates und Static Assets
- Dashboard-Komponenten und Live-Updates
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Any
import logging


logger = logging.getLogger(__name__)


# === ID 414: GUI Frontend – Dashboard ===

class DashboardGenerator:
    """Dashboard HTML/CSS/JS generator."""
    
    def __init__(self):
        self.template_dir = Path("templates")
        self.static_dir = Path("static")
    
    def generate_dashboard_html(self) -> str:
        """Generate dashboard HTML."""
        
        return '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CodePipeline Dashboard</title>
    <link rel="stylesheet" href="/static/dashboard.css">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
</head>
<body>
    <div id="app">
        <!-- Header -->
        <header class="header">
            <div class="header-content">
                <h1><i class="fas fa-code-branch"></i> CodePipeline Dashboard</h1>
                <div class="header-actions">
                    <button id="newRunBtn" class="btn btn-primary">
                        <i class="fas fa-plus"></i> New Run
                    </button>
                    <div class="connection-status" id="connectionStatus">
                        <i class="fas fa-circle"></i> <span>Connecting...</span>
                    </div>
                </div>
            </div>
        </header>

        <!-- Main Content -->
        <main class="main-content">
            <!-- Metrics Cards -->
            <section class="metrics-section">
                <div class="metrics-grid">
                    <div class="metric-card">
                        <div class="metric-icon">
                            <i class="fas fa-play-circle"></i>
                        </div>
                        <div class="metric-content">
                            <div class="metric-value" id="totalRuns">-</div>
                            <div class="metric-label">Total Runs</div>
                        </div>
                    </div>
                    
                    <div class="metric-card">
                        <div class="metric-icon success">
                            <i class="fas fa-check-circle"></i>
                        </div>
                        <div class="metric-content">
                            <div class="metric-value" id="successRate">-</div>
                            <div class="metric-label">Success Rate</div>
                        </div>
                    </div>
                    
                    <div class="metric-card">
                        <div class="metric-icon">
                            <i class="fas fa-shield-alt"></i>
                        </div>
                        <div class="metric-content">
                            <div class="metric-value" id="coverageMedian">-</div>
                            <div class="metric-label">Coverage Median</div>
                        </div>
                    </div>
                    
                    <div class="metric-card">
                        <div class="metric-icon warning">
                            <i class="fas fa-search"></i>
                        </div>
                        <div class="metric-content">
                            <div class="metric-value" id="activeScanners">-</div>
                            <div class="metric-label">Active Scanners</div>
                        </div>
                    </div>
                </div>
            </section>

            <!-- Filters -->
            <section class="filters-section">
                <div class="filters-container">
                    <div class="filter-group">
                        <label>Status:</label>
                        <div class="filter-chips" id="statusFilters">
                            <button class="filter-chip active" data-filter="all">All</button>
                            <button class="filter-chip" data-filter="running">Running</button>
                            <button class="filter-chip" data-filter="success">Success</button>
                            <button class="filter-chip" data-filter="failed">Failed</button>
                        </div>
                    </div>
                    
                    <div class="filter-group">
                        <label>Template:</label>
                        <div class="filter-chips" id="templateFilters">
                            <button class="filter-chip active" data-filter="all">All</button>
                            <button class="filter-chip" data-filter="cli">CLI</button>
                            <button class="filter-chip" data-filter="web-api">Web API</button>
                            <button class="filter-chip" data-filter="worker">Worker</button>
                            <button class="filter-chip" data-filter="batch">Batch</button>
                        </div>
                    </div>
                    
                    <div class="filter-group">
                        <label>Profile:</label>
                        <div class="filter-chips" id="profileFilters">
                            <button class="filter-chip active" data-filter="all">All</button>
                            <button class="filter-chip" data-filter="development">Development</button>
                            <button class="filter-chip" data-filter="staging">Staging</button>
                            <button class="filter-chip" data-filter="production">Production</button>
                        </div>
                    </div>
                </div>
            </section>

            <!-- Runs Table -->
            <section class="runs-section">
                <div class="section-header">
                    <h2>Recent Runs</h2>
                    <div class="section-actions">
                        <button id="refreshBtn" class="btn btn-secondary">
                            <i class="fas fa-sync-alt"></i> Refresh
                        </button>
                    </div>
                </div>
                
                <div class="runs-table-container">
                    <table class="runs-table" id="runsTable">
                        <thead>
                            <tr>
                                <th>Status</th>
                                <th>Run ID</th>
                                <th>Template</th>
                                <th>Profile</th>
                                <th>Duration</th>
                                <th>Coverage</th>
                                <th>PR</th>
                                <th>Created</th>
                                <th>Actions</th>
                            </tr>
                        </thead>
                        <tbody id="runsTableBody">
                            <!-- Runs will be populated by JavaScript -->
                        </tbody>
                    </table>
                </div>
                
                <div class="loading" id="runsLoading">
                    <i class="fas fa-spinner fa-spin"></i> Loading runs...
                </div>
                
                <div class="empty-state" id="runsEmpty" style="display: none;">
                    <i class="fas fa-inbox"></i>
                    <p>No runs found</p>
                    <button class="btn btn-primary" onclick="showNewRunDialog()">Create First Run</button>
                </div>
            </section>
        </main>

        <!-- New Run Dialog -->
        <div class="modal" id="newRunModal">
            <div class="modal-content">
                <div class="modal-header">
                    <h3>Create New Run</h3>
                    <button class="modal-close" onclick="hideNewRunDialog()">&times;</button>
                </div>
                <div class="modal-body">
                    <form id="newRunForm">
                        <div class="form-group">
                            <label for="promptInput">Prompt *</label>
                            <textarea id="promptInput" placeholder="Describe what you want to build..." required></textarea>
                        </div>
                        
                        <div class="form-row">
                            <div class="form-group">
                                <label for="templateSelect">Template</label>
                                <select id="templateSelect">
                                    <option value="">Auto-detect</option>
                                    <option value="cli">CLI Application</option>
                                    <option value="web-api">Web API</option>
                                    <option value="worker">Background Worker</option>
                                    <option value="batch">Batch Job</option>
                                </select>
                            </div>
                            
                            <div class="form-group">
                                <label for="profileSelect">Deploy Profile</label>
                                <select id="profileSelect">
                                    <option value="development">Development</option>
                                    <option value="staging">Staging</option>
                                    <option value="production">Production</option>
                                </select>
                            </div>
                        </div>
                        
                        <div class="form-group">
                            <label class="checkbox-label">
                                <input type="checkbox" id="secureModeCheck" checked>
                                Enable Secure Mode
                            </label>
                        </div>
                        
                        <div class="form-group">
                            <label for="seedInput">Seed (optional)</label>
                            <input type="text" id="seedInput" placeholder="Random seed for reproducibility">
                        </div>
                    </form>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" onclick="hideNewRunDialog()">Cancel</button>
                    <button type="submit" form="newRunForm" class="btn btn-primary">Create Run</button>
                </div>
            </div>
        </div>

        <!-- Run Details Modal -->
        <div class="modal" id="runDetailsModal">
            <div class="modal-content large">
                <div class="modal-header">
                    <h3 id="runDetailsTitle">Run Details</h3>
                    <button class="modal-close" onclick="hideRunDetailsDialog()">&times;</button>
                </div>
                <div class="modal-body">
                    <div class="run-details-content" id="runDetailsContent">
                        <!-- Content will be populated by JavaScript -->
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script src="/static/dashboard.js"></script>
</body>
</html>'''
    
    def generate_dashboard_css(self) -> str:
        """Generate dashboard CSS."""
        
        return '''/* CodePipeline Dashboard Styles */

:root {
    --primary-color: #2563eb;
    --primary-hover: #1d4ed8;
    --success-color: #10b981;
    --warning-color: #f59e0b;
    --danger-color: #ef4444;
    --secondary-color: #6b7280;
    --background-color: #f8fafc;
    --surface-color: #ffffff;
    --border-color: #e2e8f0;
    --text-primary: #1f2937;
    --text-secondary: #6b7280;
    --shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px 0 rgba(0, 0, 0, 0.06);
    --shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05);
}

* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background-color: var(--background-color);
    color: var(--text-primary);
    line-height: 1.6;
}

/* Header */
.header {
    background: var(--surface-color);
    border-bottom: 1px solid var(--border-color);
    box-shadow: var(--shadow);
    position: sticky;
    top: 0;
    z-index: 100;
}

.header-content {
    max-width: 1200px;
    margin: 0 auto;
    padding: 1rem 2rem;
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.header h1 {
    font-size: 1.5rem;
    font-weight: 600;
    color: var(--primary-color);
}

.header-actions {
    display: flex;
    align-items: center;
    gap: 1rem;
}

.connection-status {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.875rem;
    color: var(--text-secondary);
}

.connection-status.connected {
    color: var(--success-color);
}

.connection-status.disconnected {
    color: var(--danger-color);
}

/* Main Content */
.main-content {
    max-width: 1200px;
    margin: 0 auto;
    padding: 2rem;
}

/* Metrics Section */
.metrics-section {
    margin-bottom: 2rem;
}

.metrics-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
    gap: 1rem;
}

.metric-card {
    background: var(--surface-color);
    border-radius: 0.5rem;
    padding: 1.5rem;
    box-shadow: var(--shadow);
    display: flex;
    align-items: center;
    gap: 1rem;
}

.metric-icon {
    width: 3rem;
    height: 3rem;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1.25rem;
    background-color: var(--primary-color);
    color: white;
}

.metric-icon.success {
    background-color: var(--success-color);
}

.metric-icon.warning {
    background-color: var(--warning-color);
}

.metric-icon.danger {
    background-color: var(--danger-color);
}

.metric-value {
    font-size: 2rem;
    font-weight: 700;
    color: var(--text-primary);
}

.metric-label {
    font-size: 0.875rem;
    color: var(--text-secondary);
}

/* Filters Section */
.filters-section {
    margin-bottom: 2rem;
}

.filters-container {
    background: var(--surface-color);
    border-radius: 0.5rem;
    padding: 1.5rem;
    box-shadow: var(--shadow);
    display: flex;
    flex-wrap: wrap;
    gap: 2rem;
}

.filter-group {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
}

.filter-group label {
    font-size: 0.875rem;
    font-weight: 500;
    color: var(--text-secondary);
}

.filter-chips {
    display: flex;
    gap: 0.5rem;
    flex-wrap: wrap;
}

.filter-chip {
    padding: 0.5rem 1rem;
    border: 1px solid var(--border-color);
    border-radius: 1.5rem;
    background: var(--surface-color);
    color: var(--text-secondary);
    font-size: 0.875rem;
    cursor: pointer;
    transition: all 0.2s;
}

.filter-chip:hover {
    border-color: var(--primary-color);
    color: var(--primary-color);
}

.filter-chip.active {
    background: var(--primary-color);
    border-color: var(--primary-color);
    color: white;
}

/* Runs Section */
.runs-section {
    background: var(--surface-color);
    border-radius: 0.5rem;
    box-shadow: var(--shadow);
    overflow: hidden;
}

.section-header {
    padding: 1.5rem;
    border-bottom: 1px solid var(--border-color);
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.section-header h2 {
    font-size: 1.25rem;
    font-weight: 600;
}

.section-actions {
    display: flex;
    gap: 0.5rem;
}

.runs-table-container {
    overflow-x: auto;
}

.runs-table {
    width: 100%;
    border-collapse: collapse;
}

.runs-table th {
    background: var(--background-color);
    padding: 0.75rem 1rem;
    text-align: left;
    font-size: 0.875rem;
    font-weight: 500;
    color: var(--text-secondary);
    border-bottom: 1px solid var(--border-color);
}

.runs-table td {
    padding: 0.75rem 1rem;
    border-bottom: 1px solid var(--border-color);
    font-size: 0.875rem;
}

.runs-table tbody tr:hover {
    background-color: var(--background-color);
}

/* Status Indicators */
.status-badge {
    display: inline-flex;
    align-items: center;
    gap: 0.25rem;
    padding: 0.25rem 0.5rem;
    border-radius: 0.25rem;
    font-size: 0.75rem;
    font-weight: 500;
}

.status-badge.pending {
    background-color: #fef3c7;
    color: #92400e;
}

.status-badge.running {
    background-color: #dbeafe;
    color: #1e40af;
}

.status-badge.success {
    background-color: #d1fae5;
    color: #065f46;
}

.status-badge.failed {
    background-color: #fee2e2;
    color: #991b1b;
}

.status-badge.cancelled {
    background-color: #f3f4f6;
    color: #374151;
}

/* Buttons */
.btn {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.5rem 1rem;
    border: none;
    border-radius: 0.375rem;
    font-size: 0.875rem;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.2s;
    text-decoration: none;
}

.btn-primary {
    background-color: var(--primary-color);
    color: white;
}

.btn-primary:hover {
    background-color: var(--primary-hover);
}

.btn-secondary {
    background-color: var(--surface-color);
    color: var(--text-secondary);
    border: 1px solid var(--border-color);
}

.btn-secondary:hover {
    background-color: var(--background-color);
}

.btn-sm {
    padding: 0.25rem 0.5rem;
    font-size: 0.75rem;
}

/* Loading and Empty States */
.loading {
    text-align: center;
    padding: 3rem;
    color: var(--text-secondary);
}

.empty-state {
    text-align: center;
    padding: 3rem;
    color: var(--text-secondary);
}

.empty-state i {
    font-size: 3rem;
    margin-bottom: 1rem;
    opacity: 0.5;
}

/* Modal */
.modal {
    display: none;
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background-color: rgba(0, 0, 0, 0.5);
    z-index: 1000;
}

.modal.show {
    display: flex;
    align-items: center;
    justify-content: center;
}

.modal-content {
    background: var(--surface-color);
    border-radius: 0.5rem;
    box-shadow: var(--shadow-lg);
    width: 90%;
    max-width: 500px;
    max-height: 90vh;
    overflow-y: auto;
}

.modal-content.large {
    max-width: 800px;
}

.modal-header {
    padding: 1.5rem;
    border-bottom: 1px solid var(--border-color);
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.modal-header h3 {
    font-size: 1.25rem;
    font-weight: 600;
}

.modal-close {
    background: none;
    border: none;
    font-size: 1.5rem;
    cursor: pointer;
    color: var(--text-secondary);
}

.modal-body {
    padding: 1.5rem;
}

.modal-footer {
    padding: 1.5rem;
    border-top: 1px solid var(--border-color);
    display: flex;
    justify-content: flex-end;
    gap: 0.5rem;
}

/* Form */
.form-group {
    margin-bottom: 1rem;
}

.form-group label {
    display: block;
    margin-bottom: 0.5rem;
    font-size: 0.875rem;
    font-weight: 500;
    color: var(--text-primary);
}

.form-group input,
.form-group textarea,
.form-group select {
    width: 100%;
    padding: 0.5rem;
    border: 1px solid var(--border-color);
    border-radius: 0.375rem;
    font-size: 0.875rem;
}

.form-group textarea {
    resize: vertical;
    min-height: 100px;
}

.form-row {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 1rem;
}

.checkbox-label {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    cursor: pointer;
}

.checkbox-label input[type="checkbox"] {
    width: auto;
}

/* Responsive */
@media (max-width: 768px) {
    .header-content {
        padding: 1rem;
        flex-direction: column;
        gap: 1rem;
    }

    .main-content {
        padding: 1rem;
    }

    .filters-container {
        flex-direction: column;
        gap: 1rem;
    }

    .form-row {
        grid-template-columns: 1fr;
    }
}

/* Animations */
@keyframes spin {
    to {
        transform: rotate(360deg);
    }
}

.fa-spin {
    animation: spin 1s linear infinite;
}

/* Gate Status Lights */
.gate-lights {
    display: flex;
    gap: 0.25rem;
    align-items: center;
}

.gate-light {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background-color: var(--border-color);
}

.gate-light.passed {
    background-color: var(--success-color);
}

.gate-light.failed {
    background-color: var(--danger-color);
}

.gate-light.running {
    background-color: var(--warning-color);
    animation: pulse 1s infinite;
}

@keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.5; }
}'''
    
    def generate_dashboard_js(self) -> str:
        """Generate dashboard JavaScript."""
        
        return '''// CodePipeline Dashboard JavaScript

class DashboardApp {
    constructor() {
        this.apiBase = '/api';
        this.eventSource = null;
        this.runs = [];
        this.filters = {
            status: 'all',
            template: 'all',
            profile: 'all'
        };
        
        this.init();
    }
    
    async init() {
        console.log('Initializing Dashboard App');
        
        // Setup event listeners
        this.setupEventListeners();
        
        // Load initial data
        await this.loadMetrics();
        await this.loadRuns();
        
        // Setup live updates
        this.setupLiveUpdates();
        
        console.log('Dashboard App initialized');
    }
    
    setupEventListeners() {
        // New Run button
        document.getElementById('newRunBtn').addEventListener('click', () => {
            this.showNewRunDialog();
        });
        
        // Refresh button
        document.getElementById('refreshBtn').addEventListener('click', () => {
            this.loadRuns();
        });
        
        // Filter chips
        document.querySelectorAll('.filter-chip').forEach(chip => {
            chip.addEventListener('click', (e) => {
                this.handleFilterChange(e.target);
            });
        });
        
        // New run form
        document.getElementById('newRunForm').addEventListener('submit', (e) => {
            e.preventDefault();
            this.createNewRun();
        });
        
        // Modal close handlers
        document.querySelectorAll('.modal').forEach(modal => {
            modal.addEventListener('click', (e) => {
                if (e.target === modal) {
                    modal.classList.remove('show');
                }
            });
        });
    }
    
    async loadMetrics() {
        try {
            const response = await fetch(`${this.apiBase}/dashboard/metrics`);
            const metrics = await response.json();
            
            this.updateMetricsDisplay(metrics);
        } catch (error) {
            console.error('Failed to load metrics:', error);
        }
    }
    
    updateMetricsDisplay(metrics) {
        document.getElementById('totalRuns').textContent = metrics.total_runs || 0;
        document.getElementById('successRate').textContent = `${(metrics.success_rate * 100).toFixed(1)}%`;
        document.getElementById('coverageMedian').textContent = `${metrics.coverage_median.toFixed(1)}%`;
        document.getElementById('activeScanners').textContent = metrics.active_scanners || 0;
    }
    
    async loadRuns() {
        const loading = document.getElementById('runsLoading');
        const empty = document.getElementById('runsEmpty');
        const tableBody = document.getElementById('runsTableBody');
        
        loading.style.display = 'block';
        empty.style.display = 'none';
        
        try {
            const params = new URLSearchParams();
            if (this.filters.status !== 'all') params.append('status', this.filters.status);
            if (this.filters.template !== 'all') params.append('template_type', this.filters.template);
            if (this.filters.profile !== 'all') params.append('deploy_profile', this.filters.profile);
            
            const response = await fetch(`${this.apiBase}/runs?${params}`);
            const data = await response.json();
            
            this.runs = data.runs || [];
            this.updateRunsTable();
            
            if (this.runs.length === 0) {
                empty.style.display = 'block';
            }
            
        } catch (error) {
            console.error('Failed to load runs:', error);
        } finally {
            loading.style.display = 'none';
        }
    }
    
    updateRunsTable() {
        const tableBody = document.getElementById('runsTableBody');
        tableBody.innerHTML = '';
        
        this.runs.forEach(run => {
            const row = this.createRunRow(run);
            tableBody.appendChild(row);
        });
    }
    
    createRunRow(run) {
        const row = document.createElement('tr');
        row.innerHTML = `
            <td>
                <span class="status-badge ${run.status}">
                    ${this.getStatusIcon(run.status)} ${run.status}
                </span>
            </td>
            <td>
                <code>${run.run_id.substring(0, 8)}</code>
            </td>
            <td>${run.template_type || '-'}</td>
            <td>${run.deploy_profile || '-'}</td>
            <td>${this.formatDuration(run.duration_seconds)}</td>
            <td>${run.coverage_percentage ? run.coverage_percentage.toFixed(1) + '%' : '-'}</td>
            <td>
                ${run.pr_url ? `<a href="${run.pr_url}" target="_blank" class="btn btn-sm btn-secondary">
                    <i class="fas fa-external-link-alt"></i> PR
                </a>` : '-'}
            </td>
            <td>${this.formatDate(run.created_at)}</td>
            <td>
                <button class="btn btn-sm btn-secondary" onclick="app.showRunDetails('${run.run_id}')">
                    <i class="fas fa-eye"></i> Details
                </button>
            </td>
        `;
        
        return row;
    }
    
    getStatusIcon(status) {
        const icons = {
            pending: '<i class="fas fa-clock"></i>',
            running: '<i class="fas fa-spinner fa-spin"></i>',
            success: '<i class="fas fa-check"></i>',
            failed: '<i class="fas fa-times"></i>',
            cancelled: '<i class="fas fa-ban"></i>'
        };
        
        return icons[status] || '<i class="fas fa-question"></i>';
    }
    
    formatDuration(seconds) {
        if (!seconds) return '-';
        
        if (seconds < 60) {
            return `${seconds.toFixed(0)}s`;
        } else if (seconds < 3600) {
            return `${(seconds / 60).toFixed(1)}m`;
        } else {
            return `${(seconds / 3600).toFixed(1)}h`;
        }
    }
    
    formatDate(dateString) {
        const date = new Date(dateString);
        return date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
    }
    
    handleFilterChange(chip) {
        const filterGroup = chip.closest('.filter-chips');
        const filterType = filterGroup.id.replace('Filters', '').toLowerCase();
        const filterValue = chip.dataset.filter;
        
        // Update active chip
        filterGroup.querySelectorAll('.filter-chip').forEach(c => c.classList.remove('active'));
        chip.classList.add('active');
        
        // Update filter
        this.filters[filterType === 'status' ? 'status' : filterType === 'template' ? 'template' : 'profile'] = filterValue;
        
        // Reload runs
        this.loadRuns();
    }
    
    showNewRunDialog() {
        document.getElementById('newRunModal').classList.add('show');
        document.getElementById('promptInput').focus();
    }
    
    hideNewRunDialog() {
        document.getElementById('newRunModal').classList.remove('show');
        document.getElementById('newRunForm').reset();
    }
    
    async createNewRun() {
        const form = document.getElementById('newRunForm');
        const formData = new FormData(form);
        
        const spec = {
            prompt: document.getElementById('promptInput').value,
            template_type: document.getElementById('templateSelect').value || null,
            deploy_profile: document.getElementById('profileSelect').value,
            secure_mode: document.getElementById('secureModeCheck').checked,
            seed: document.getElementById('seedInput').value || null
        };
        
        try {
            const response = await fetch(`${this.apiBase}/runs`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(spec)
            });
            
            if (response.ok) {
                const result = await response.json();
                console.log('Run created:', result);
                
                this.hideNewRunDialog();
                this.loadRuns();
                this.loadMetrics();
                
                // Show success message
                this.showNotification('Run created successfully!', 'success');
            } else {
                throw new Error('Failed to create run');
            }
        } catch (error) {
            console.error('Failed to create run:', error);
            this.showNotification('Failed to create run', 'error');
        }
    }
    
    async showRunDetails(runId) {
        try {
            const response = await fetch(`${this.apiBase}/runs/${runId}`);
            const run = await response.json();
            
            this.renderRunDetails(run);
            document.getElementById('runDetailsModal').classList.add('show');
            
        } catch (error) {
            console.error('Failed to load run details:', error);
            this.showNotification('Failed to load run details', 'error');
        }
    }
    
    renderRunDetails(run) {
        const title = document.getElementById('runDetailsTitle');
        const content = document.getElementById('runDetailsContent');
        
        title.textContent = `Run ${run.run_id.substring(0, 8)}`;
        
        content.innerHTML = `
            <div class="run-details-grid">
                <div class="run-details-section">
                    <h4>Overview</h4>
                    <div class="detail-item">
                        <label>Status:</label>
                        <span class="status-badge ${run.status}">
                            ${this.getStatusIcon(run.status)} ${run.status}
                        </span>
                    </div>
                    <div class="detail-item">
                        <label>Template:</label>
                        <span>${run.template_type}</span>
                    </div>
                    <div class="detail-item">
                        <label>Profile:</label>
                        <span>${run.deploy_profile}</span>
                    </div>
                    <div class="detail-item">
                        <label>Duration:</label>
                        <span>${this.formatDuration(run.duration_seconds)}</span>
                    </div>
                    <div class="detail-item">
                        <label>Coverage:</label>
                        <span>${run.coverage_percentage ? run.coverage_percentage.toFixed(1) + '%' : '-'}</span>
                    </div>
                    <div class="detail-item">
                        <label>Scorecard:</label>
                        <span>${run.scorecard_score || '-'}</span>
                    </div>
                </div>
                
                <div class="run-details-section">
                    <h4>Gates</h4>
                    <div class="gates-list">
                        ${this.renderGates(run.gates)}
                    </div>
                </div>
                
                <div class="run-details-section">
                    <h4>Artifacts</h4>
                    <div class="artifacts-list">
                        ${this.renderArtifacts(run.run_id, run.artifacts)}
                    </div>
                </div>
            </div>
        `;
    }
    
    renderGates(gates) {
        if (!gates || Object.keys(gates).length === 0) {
            return '<p>No gates information available</p>';
        }
        
        return Object.values(gates).map(gate => `
            <div class="gate-item">
                <div class="gate-header">
                    <span class="gate-light ${gate.status}"></span>
                    <strong>${gate.gate_name}</strong>
                    <span class="gate-duration">${this.formatDuration(gate.duration_seconds)}</span>
                </div>
                ${gate.details ? `<div class="gate-details">${JSON.stringify(gate.details, null, 2)}</div>` : ''}
            </div>
        `).join('');
    }
    
    renderArtifacts(runId, artifacts) {
        if (!artifacts || Object.keys(artifacts).length === 0) {
            return '<p>No artifacts available</p>';
        }
        
        return Object.keys(artifacts).map(name => `
            <div class="artifact-item">
                <i class="fas fa-file-archive"></i>
                <span>${name}</span>
                <a href="${this.apiBase}/runs/${runId}/artifacts/${name}/download" 
                   class="btn btn-sm btn-secondary" download>
                    <i class="fas fa-download"></i> Download
                </a>
            </div>
        `).join('');
    }
    
    hideRunDetailsDialog() {
        document.getElementById('runDetailsModal').classList.remove('show');
    }
    
    setupLiveUpdates() {
        if (typeof EventSource !== 'undefined') {
            // Note: In real implementation, would connect to specific run
            // For demo, we'll simulate with periodic updates
            this.startPeriodicUpdates();
        } else {
            console.warn('EventSource not supported, falling back to periodic updates');
            this.startPeriodicUpdates();
        }
    }
    
    startPeriodicUpdates() {
        // Update every 5 seconds
        setInterval(() => {
            this.loadRuns();
            this.loadMetrics();
        }, 5000);
    }
    
    connectEventSource() {
        const status = document.getElementById('connectionStatus');
        
        try {
            this.eventSource = new EventSource(`${this.apiBase}/events`);
            
            this.eventSource.onopen = () => {
                status.className = 'connection-status connected';
                status.innerHTML = '<i class="fas fa-circle"></i> <span>Connected</span>';
            };
            
            this.eventSource.onmessage = (event) => {
                const data = JSON.parse(event.data);
                this.handleLiveEvent(data);
            };
            
            this.eventSource.onerror = () => {
                status.className = 'connection-status disconnected';
                status.innerHTML = '<i class="fas fa-circle"></i> <span>Disconnected</span>';
            };
            
        } catch (error) {
            console.error('Failed to setup EventSource:', error);
        }
    }
    
    handleLiveEvent(event) {
        console.log('Live event:', event);
        
        switch (event.event_type) {
            case 'run_created':
            case 'run_started':
            case 'run_completed':
            case 'run_failed':
                this.loadRuns();
                this.loadMetrics();
                break;
                
            case 'gate_updated':
                this.updateGateStatus(event.run_id, event.data);
                break;
                
            case 'log_entry':
                this.addLogEntry(event.run_id, event.data);
                break;
        }
    }
    
    updateGateStatus(runId, gateData) {
        // Update gate status in UI if run details are open
        const modal = document.getElementById('runDetailsModal');
        if (modal.classList.contains('show')) {
            // Reload run details to get updated gates
            this.showRunDetails(runId);
        }
    }
    
    addLogEntry(runId, logData) {
        // Add log entry to UI if logs are visible
        console.log('New log entry:', runId, logData);
    }
    
    showNotification(message, type = 'info') {
        // Simple notification system
        const notification = document.createElement('div');
        notification.className = `notification notification-${type}`;
        notification.textContent = message;
        
        document.body.appendChild(notification);
        
        setTimeout(() => {
            notification.remove();
        }, 3000);
    }
}

// Global functions for modal handling
function showNewRunDialog() {
    app.showNewRunDialog();
}

function hideNewRunDialog() {
    app.hideNewRunDialog();
}

function hideRunDetailsDialog() {
    app.hideRunDetailsDialog();
}

// Initialize app when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.app = new DashboardApp();
});'''
    
    def generate_static_files(self, output_dir: Path):
        """Generate static files for dashboard."""
        
        # Create directories
        templates_dir = output_dir / "templates"
        static_dir = output_dir / "static"
        
        templates_dir.mkdir(parents=True, exist_ok=True)
        static_dir.mkdir(parents=True, exist_ok=True)
        
        # Write files
        (templates_dir / "dashboard.html").write_text(self.generate_dashboard_html())
        (static_dir / "dashboard.css").write_text(self.generate_dashboard_css())
        (static_dir / "dashboard.js").write_text(self.generate_dashboard_js())
        
        logger.info(f"Generated dashboard files in {output_dir}")
        
        return {
            "html": templates_dir / "dashboard.html",
            "css": static_dir / "dashboard.css", 
            "js": static_dir / "dashboard.js"
        }


# === Convenience Functions ===

def generate_dashboard_files(output_dir: str = "gui_output") -> Dict[str, Path]:
    """Generate dashboard files."""
    generator = DashboardGenerator()
    return generator.generate_static_files(Path(output_dir))


if __name__ == "__main__":
    # Demo
    def demo_dashboard_generator():
        print("Dashboard Generator Demo:")
        
        # Generate files
        generator = DashboardGenerator()
        output_dir = Path("demo_dashboard")
        files = generator.generate_static_files(output_dir)
        
        print(f"Generated files:")
        for file_type, file_path in files.items():
            print(f"  {file_type}: {file_path} ({file_path.stat().st_size} bytes)")
        
        return len(files) == 3
    
    # Run demo
    result = demo_dashboard_generator()
    print(f"Demo completed: {result}")
