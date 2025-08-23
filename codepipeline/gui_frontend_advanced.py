"""
Advanced GUI Frontend Components.

Implementiert:
- ID 415: GUI Frontend – Neuer-Run-Wizard
- ID 416: GUI Frontend – Run-Detail & Gate-Timeline
- ID 417: GUI – Settings & Secure Defaults
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
import logging


logger = logging.getLogger(__name__)


# === ID 415: GUI Frontend – Neuer-Run-Wizard ===

class RunWizardGenerator:
    """Generator for new run wizard."""
    
    def generate_wizard_html(self) -> str:
        """Generate run wizard HTML."""
        
        return '''<!-- New Run Wizard -->
<div class="wizard-container" id="runWizard">
    <div class="wizard-header">
        <h2><i class="fas fa-magic"></i> New Pipeline Run</h2>
        <div class="wizard-steps">
            <div class="step active" data-step="1">
                <div class="step-number">1</div>
                <div class="step-label">Specification</div>
            </div>
            <div class="step" data-step="2">
                <div class="step-number">2</div>
                <div class="step-label">Configuration</div>
            </div>
            <div class="step" data-step="3">
                <div class="step-number">3</div>
                <div class="step-label">Review</div>
            </div>
        </div>
    </div>
    
    <div class="wizard-content">
        <!-- Step 1: Specification -->
        <div class="wizard-step active" data-step="1">
            <h3>Pipeline Specification</h3>
            
            <div class="spec-editor-container">
                <div class="editor-toolbar">
                    <div class="editor-tabs">
                        <button class="tab-btn active" data-format="prompt">Prompt</button>
                        <button class="tab-btn" data-format="yaml">YAML</button>
                        <button class="tab-btn" data-format="json">JSON</button>
                    </div>
                    <div class="editor-actions">
                        <button class="btn btn-sm btn-secondary" id="validateSpec">
                            <i class="fas fa-check"></i> Validate
                        </button>
                        <button class="btn btn-sm btn-secondary" id="loadTemplate">
                            <i class="fas fa-file-import"></i> Load Template
                        </button>
                    </div>
                </div>
                
                <!-- Prompt Editor -->
                <div class="editor-panel active" data-format="prompt">
                    <div class="form-group">
                        <label for="promptEditor">Describe what you want to build</label>
                        <textarea id="promptEditor" class="spec-editor" rows="8" 
                                placeholder="Create a REST API for user management with authentication..."></textarea>
                    </div>
                    <div class="prompt-suggestions">
                        <h4>Suggestions</h4>
                        <div class="suggestion-chips">
                            <button class="suggestion-chip" data-prompt="Create a REST API with authentication">REST API</button>
                            <button class="suggestion-chip" data-prompt="Build a CLI tool for file processing">CLI Tool</button>
                            <button class="suggestion-chip" data-prompt="Develop a background worker for data processing">Worker</button>
                            <button class="suggestion-chip" data-prompt="Create a batch job for ETL pipeline">Batch Job</button>
                        </div>
                    </div>
                </div>
                
                <!-- YAML Editor -->
                <div class="editor-panel" data-format="yaml">
                    <textarea id="yamlEditor" class="spec-editor code-editor" rows="15" 
                            placeholder="prompt: 'Create a REST API...'
template_type: web-api
deploy_profile: development
secure_mode: true
features:
  - authentication
  - database
  - api_docs"></textarea>
                </div>
                
                <!-- JSON Editor -->
                <div class="editor-panel" data-format="json">
                    <textarea id="jsonEditor" class="spec-editor code-editor" rows="15" 
                            placeholder='{
  "prompt": "Create a REST API...",
  "template_type": "web-api",
  "deploy_profile": "development",
  "secure_mode": true,
  "features": ["authentication", "database", "api_docs"]
}'></textarea>
                </div>
            </div>
            
            <div class="validation-panel" id="validationPanel">
                <div class="validation-results" id="validationResults"></div>
            </div>
        </div>
        
        <!-- Step 2: Configuration -->
        <div class="wizard-step" data-step="2">
            <h3>Run Configuration</h3>
            
            <div class="config-grid">
                <div class="config-section">
                    <h4>Template & Profile</h4>
                    <div class="form-group">
                        <label for="templateType">Template Type</label>
                        <select id="templateType" class="form-control">
                            <option value="">Auto-detect</option>
                            <option value="cli">CLI Application</option>
                            <option value="web-api">Web API</option>
                            <option value="worker">Background Worker</option>
                            <option value="batch">Batch Job</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label for="deployProfile">Deploy Profile</label>
                        <select id="deployProfile" class="form-control">
                            <option value="development">Development</option>
                            <option value="staging">Staging</option>
                            <option value="production">Production</option>
                        </select>
                    </div>
                </div>
                
                <div class="config-section">
                    <h4>Security & Options</h4>
                    <div class="form-group">
                        <label class="checkbox-label">
                            <input type="checkbox" id="secureMode" checked>
                            <span class="checkmark"></span>
                            Enable Secure Mode
                        </label>
                        <small class="form-hint">Enforces strict security policies and gates</small>
                    </div>
                    <div class="form-group">
                        <label class="checkbox-label">
                            <input type="checkbox" id="dryRun">
                            <span class="checkmark"></span>
                            Dry Run
                        </label>
                        <small class="form-hint">Validate without executing deployment</small>
                    </div>
                </div>
                
                <div class="config-section">
                    <h4>Git & Branch</h4>
                    <div class="form-group">
                        <label for="branchName">Branch Name</label>
                        <input type="text" id="branchName" class="form-control" 
                               placeholder="feature/new-api" value="">
                        <small class="form-hint">Leave empty to auto-generate</small>
                    </div>
                    <div class="form-group">
                        <label for="seedValue">Reproducibility Seed</label>
                        <input type="text" id="seedValue" class="form-control" 
                               placeholder="Optional seed for deterministic builds">
                    </div>
                </div>
            </div>
        </div>
        
        <!-- Step 3: Review -->
        <div class="wizard-step" data-step="3">
            <h3>Review & Start</h3>
            
            <div class="review-sections">
                <div class="review-section">
                    <h4>Specification</h4>
                    <div class="review-content" id="reviewSpec">
                        <!-- Will be populated by JS -->
                    </div>
                </div>
                
                <div class="review-section">
                    <h4>Configuration</h4>
                    <div class="review-content" id="reviewConfig">
                        <!-- Will be populated by JS -->
                    </div>
                </div>
                
                <div class="review-section">
                    <h4>Estimated Resources</h4>
                    <div class="resource-estimates">
                        <div class="resource-item">
                            <span class="resource-label">Duration:</span>
                            <span class="resource-value">~5-10 minutes</span>
                        </div>
                        <div class="resource-item">
                            <span class="resource-label">Gates:</span>
                            <span class="resource-value">8 security checks</span>
                        </div>
                        <div class="resource-item">
                            <span class="resource-label">Artifacts:</span>
                            <span class="resource-value">Build, SBOM, Security reports</span>
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="start-panel">
                <button class="btn btn-primary btn-lg" id="startRun">
                    <i class="fas fa-play"></i> Start Pipeline Run
                </button>
            </div>
        </div>
    </div>
    
    <div class="wizard-footer">
        <button class="btn btn-secondary" id="wizardPrev" disabled>
            <i class="fas fa-arrow-left"></i> Previous
        </button>
        <button class="btn btn-primary" id="wizardNext">
            Next <i class="fas fa-arrow-right"></i>
        </button>
        <button class="btn btn-secondary" id="wizardCancel">Cancel</button>
    </div>
</div>'''
    
    def generate_wizard_css(self) -> str:
        """Generate wizard CSS."""
        
        return '''/* Run Wizard Styles */

.wizard-container {
    max-width: 900px;
    margin: 2rem auto;
    background: var(--surface-color);
    border-radius: 0.5rem;
    box-shadow: var(--shadow-lg);
    overflow: hidden;
}

.wizard-header {
    background: linear-gradient(135deg, var(--primary-color), var(--primary-hover));
    color: white;
    padding: 2rem;
}

.wizard-header h2 {
    margin: 0 0 1rem 0;
    font-size: 1.5rem;
    font-weight: 600;
}

.wizard-steps {
    display: flex;
    gap: 2rem;
}

.step {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    opacity: 0.6;
    transition: opacity 0.3s;
}

.step.active {
    opacity: 1;
}

.step-number {
    width: 2rem;
    height: 2rem;
    border-radius: 50%;
    background: rgba(255, 255, 255, 0.2);
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: 600;
}

.step.active .step-number {
    background: white;
    color: var(--primary-color);
}

.step-label {
    font-size: 0.875rem;
    font-weight: 500;
}

.wizard-content {
    padding: 2rem;
    min-height: 500px;
}

.wizard-step {
    display: none;
}

.wizard-step.active {
    display: block;
}

.wizard-step h3 {
    margin: 0 0 1.5rem 0;
    font-size: 1.25rem;
    font-weight: 600;
    color: var(--text-primary);
}

/* Spec Editor */
.spec-editor-container {
    border: 1px solid var(--border-color);
    border-radius: 0.375rem;
    overflow: hidden;
}

.editor-toolbar {
    background: var(--background-color);
    border-bottom: 1px solid var(--border-color);
    padding: 0.75rem;
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.editor-tabs {
    display: flex;
    gap: 0.25rem;
}

.tab-btn {
    padding: 0.5rem 1rem;
    border: none;
    background: transparent;
    color: var(--text-secondary);
    border-radius: 0.25rem;
    cursor: pointer;
    transition: all 0.2s;
}

.tab-btn.active {
    background: var(--primary-color);
    color: white;
}

.editor-actions {
    display: flex;
    gap: 0.5rem;
}

.editor-panel {
    display: none;
    padding: 1rem;
}

.editor-panel.active {
    display: block;
}

.spec-editor {
    width: 100%;
    border: none;
    outline: none;
    resize: vertical;
    font-family: 'Monaco', 'Menlo', monospace;
    font-size: 0.875rem;
    line-height: 1.5;
}

.code-editor {
    background: #1e1e1e;
    color: #d4d4d4;
    border-radius: 0.25rem;
    padding: 1rem;
}

.prompt-suggestions {
    margin-top: 1rem;
}

.prompt-suggestions h4 {
    margin: 0 0 0.5rem 0;
    font-size: 0.875rem;
    font-weight: 500;
    color: var(--text-secondary);
}

.suggestion-chips {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
}

.suggestion-chip {
    padding: 0.25rem 0.75rem;
    border: 1px solid var(--border-color);
    border-radius: 1rem;
    background: var(--surface-color);
    color: var(--text-secondary);
    font-size: 0.75rem;
    cursor: pointer;
    transition: all 0.2s;
}

.suggestion-chip:hover {
    border-color: var(--primary-color);
    color: var(--primary-color);
}

/* Validation Panel */
.validation-panel {
    margin-top: 1rem;
    display: none;
}

.validation-panel.show {
    display: block;
}

.validation-results {
    padding: 1rem;
    border-radius: 0.375rem;
    border: 1px solid var(--border-color);
}

.validation-results.success {
    background: #f0fdf4;
    border-color: var(--success-color);
    color: #166534;
}

.validation-results.error {
    background: #fef2f2;
    border-color: var(--danger-color);
    color: #991b1b;
}

/* Configuration */
.config-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
    gap: 2rem;
}

.config-section {
    background: var(--background-color);
    padding: 1.5rem;
    border-radius: 0.375rem;
}

.config-section h4 {
    margin: 0 0 1rem 0;
    font-size: 1rem;
    font-weight: 600;
    color: var(--text-primary);
}

.checkbox-label {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    cursor: pointer;
    margin-bottom: 0.5rem;
}

.checkmark {
    width: 1.25rem;
    height: 1.25rem;
    border: 2px solid var(--border-color);
    border-radius: 0.25rem;
    position: relative;
    transition: all 0.2s;
}

.checkbox-label input:checked + .checkmark {
    background: var(--primary-color);
    border-color: var(--primary-color);
}

.checkbox-label input:checked + .checkmark::after {
    content: '✓';
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    color: white;
    font-size: 0.875rem;
    font-weight: 600;
}

.form-hint {
    display: block;
    color: var(--text-secondary);
    font-size: 0.75rem;
    margin-top: 0.25rem;
}

/* Review */
.review-sections {
    display: flex;
    flex-direction: column;
    gap: 1.5rem;
}

.review-section {
    background: var(--background-color);
    padding: 1.5rem;
    border-radius: 0.375rem;
}

.review-section h4 {
    margin: 0 0 1rem 0;
    font-size: 1rem;
    font-weight: 600;
    color: var(--text-primary);
}

.review-content {
    font-family: 'Monaco', 'Menlo', monospace;
    font-size: 0.875rem;
    background: var(--surface-color);
    padding: 1rem;
    border-radius: 0.25rem;
    border: 1px solid var(--border-color);
}

.resource-estimates {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
}

.resource-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.resource-label {
    color: var(--text-secondary);
    font-size: 0.875rem;
}

.resource-value {
    font-weight: 500;
    color: var(--text-primary);
}

.start-panel {
    text-align: center;
    margin-top: 2rem;
    padding: 2rem;
    background: var(--background-color);
    border-radius: 0.375rem;
}

/* Footer */
.wizard-footer {
    background: var(--background-color);
    border-top: 1px solid var(--border-color);
    padding: 1.5rem 2rem;
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.btn-lg {
    padding: 0.75rem 2rem;
    font-size: 1rem;
}

/* Responsive */
@media (max-width: 768px) {
    .wizard-container {
        margin: 1rem;
    }
    
    .wizard-steps {
        flex-direction: column;
        gap: 1rem;
    }
    
    .config-grid {
        grid-template-columns: 1fr;
    }
    
    .wizard-footer {
        flex-direction: column;
        gap: 1rem;
    }
}'''
    
    def generate_wizard_js(self) -> str:
        """Generate wizard JavaScript."""
        
        return '''// Run Wizard JavaScript

class RunWizard {
    constructor() {
        this.currentStep = 1;
        this.maxSteps = 3;
        this.spec = {};
        this.config = {};
        
        this.init();
    }
    
    init() {
        this.setupEventListeners();
        this.updateStepVisibility();
    }
    
    setupEventListeners() {
        // Step navigation
        document.getElementById('wizardNext').addEventListener('click', () => {
            this.nextStep();
        });
        
        document.getElementById('wizardPrev').addEventListener('click', () => {
            this.prevStep();
        });
        
        document.getElementById('wizardCancel').addEventListener('click', () => {
            this.cancel();
        });
        
        // Editor tabs
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                this.switchEditorTab(e.target.dataset.format);
            });
        });
        
        // Suggestion chips
        document.querySelectorAll('.suggestion-chip').forEach(chip => {
            chip.addEventListener('click', (e) => {
                this.applySuggestion(e.target.dataset.prompt);
            });
        });
        
        // Validation
        document.getElementById('validateSpec').addEventListener('click', () => {
            this.validateSpec();
        });
        
        // Start run
        document.getElementById('startRun').addEventListener('click', () => {
            this.startRun();
        });
        
        // Auto-validation on input
        ['promptEditor', 'yamlEditor', 'jsonEditor'].forEach(id => {
            const editor = document.getElementById(id);
            if (editor) {
                editor.addEventListener('input', () => {
                    this.autoValidate();
                });
            }
        });
    }
    
    nextStep() {
        if (this.currentStep < this.maxSteps) {
            if (this.validateCurrentStep()) {
                this.currentStep++;
                this.updateStepVisibility();
                
                if (this.currentStep === 3) {
                    this.updateReview();
                }
            }
        }
    }
    
    prevStep() {
        if (this.currentStep > 1) {
            this.currentStep--;
            this.updateStepVisibility();
        }
    }
    
    updateStepVisibility() {
        // Update step indicators
        document.querySelectorAll('.step').forEach(step => {
            const stepNum = parseInt(step.dataset.step);
            step.classList.toggle('active', stepNum === this.currentStep);
        });
        
        // Update step content
        document.querySelectorAll('.wizard-step').forEach(step => {
            const stepNum = parseInt(step.dataset.step);
            step.classList.toggle('active', stepNum === this.currentStep);
        });
        
        // Update navigation buttons
        const prevBtn = document.getElementById('wizardPrev');
        const nextBtn = document.getElementById('wizardNext');
        
        prevBtn.disabled = this.currentStep === 1;
        
        if (this.currentStep === this.maxSteps) {
            nextBtn.style.display = 'none';
        } else {
            nextBtn.style.display = 'inline-flex';
        }
    }
    
    validateCurrentStep() {
        switch (this.currentStep) {
            case 1:
                return this.validateSpec();
            case 2:
                return this.validateConfig();
            default:
                return true;
        }
    }
    
    switchEditorTab(format) {
        // Update tab buttons
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.format === format);
        });
        
        // Update editor panels
        document.querySelectorAll('.editor-panel').forEach(panel => {
            panel.classList.toggle('active', panel.dataset.format === format);
        });
    }
    
    applySuggestion(prompt) {
        document.getElementById('promptEditor').value = prompt;
        this.autoValidate();
    }
    
    async validateSpec() {
        const activeTab = document.querySelector('.tab-btn.active').dataset.format;
        let spec = {};
        
        try {
            switch (activeTab) {
                case 'prompt':
                    const prompt = document.getElementById('promptEditor').value;
                    if (!prompt.trim()) {
                        throw new Error('Prompt cannot be empty');
                    }
                    spec = { prompt: prompt.trim() };
                    break;
                    
                case 'yaml':
                    const yamlContent = document.getElementById('yamlEditor').value;
                    // In real implementation, would use YAML parser
                    spec = this.parseYAML(yamlContent);
                    break;
                    
                case 'json':
                    const jsonContent = document.getElementById('jsonEditor').value;
                    spec = JSON.parse(jsonContent);
                    break;
            }
            
            // Validate via API
            const response = await fetch('/api/spec/validate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(spec)
            });
            
            const result = await response.json();
            this.showValidationResults(result);
            
            if (result.valid) {
                this.spec = spec;
                return true;
            } else {
                return false;
            }
            
        } catch (error) {
            this.showValidationResults({
                valid: false,
                errors: [error.message],
                warnings: []
            });
            return false;
        }
    }
    
    parseYAML(content) {
        // Simplified YAML parser for demo
        const lines = content.split('\\n');
        const result = {};
        
        lines.forEach(line => {
            const match = line.match(/^([^:]+):\\s*(.+)$/);
            if (match) {
                const key = match[1].trim();
                let value = match[2].trim();
                
                // Handle quotes
                if (value.startsWith('"') && value.endsWith('"')) {
                    value = value.slice(1, -1);
                } else if (value.startsWith("'") && value.endsWith("'")) {
                    value = value.slice(1, -1);
                }
                
                // Handle booleans
                if (value === 'true') value = true;
                if (value === 'false') value = false;
                
                result[key] = value;
            }
        });
        
        return result;
    }
    
    showValidationResults(result) {
        const panel = document.getElementById('validationPanel');
        const results = document.getElementById('validationResults');
        
        panel.classList.add('show');
        
        if (result.valid) {
            results.className = 'validation-results success';
            results.innerHTML = '<i class="fas fa-check"></i> Specification is valid';
        } else {
            results.className = 'validation-results error';
            let html = '<i class="fas fa-times"></i> Validation failed:<ul>';
            
            result.errors.forEach(error => {
                html += `<li>${error}</li>`;
            });
            
            if (result.warnings && result.warnings.length > 0) {
                html += '</ul><strong>Warnings:</strong><ul>';
                result.warnings.forEach(warning => {
                    html += `<li>${warning}</li>`;
                });
            }
            
            html += '</ul>';
            results.innerHTML = html;
        }
    }
    
    autoValidate() {
        // Debounced validation
        clearTimeout(this.validateTimeout);
        this.validateTimeout = setTimeout(() => {
            this.validateSpec();
        }, 1000);
    }
    
    validateConfig() {
        // Collect configuration
        this.config = {
            template_type: document.getElementById('templateType').value,
            deploy_profile: document.getElementById('deployProfile').value,
            secure_mode: document.getElementById('secureMode').checked,
            dry_run: document.getElementById('dryRun').checked,
            branch_name: document.getElementById('branchName').value,
            seed: document.getElementById('seedValue').value
        };
        
        return true; // Config is always valid for now
    }
    
    updateReview() {
        // Update spec review
        const specReview = document.getElementById('reviewSpec');
        specReview.textContent = JSON.stringify(this.spec, null, 2);
        
        // Update config review
        const configReview = document.getElementById('reviewConfig');
        configReview.textContent = JSON.stringify(this.config, null, 2);
    }
    
    async startRun() {
        const startBtn = document.getElementById('startRun');
        const originalText = startBtn.innerHTML;
        
        startBtn.disabled = true;
        startBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Starting...';
        
        try {
            const runSpec = { ...this.spec, ...this.config };
            
            const response = await fetch('/api/runs', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(runSpec)
            });
            
            if (response.ok) {
                const result = await response.json();
                
                // Redirect to run detail
                window.location.href = `#/runs/${result.run_id}`;
                
                // Close wizard
                this.cancel();
                
            } else {
                throw new Error('Failed to start run');
            }
            
        } catch (error) {
            console.error('Failed to start run:', error);
            alert('Failed to start run: ' + error.message);
            
        } finally {
            startBtn.disabled = false;
            startBtn.innerHTML = originalText;
        }
    }
    
    cancel() {
        // Close wizard and return to dashboard
        document.getElementById('runWizard').style.display = 'none';
        window.location.href = '#/dashboard';
    }
}

// Initialize wizard when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    if (document.getElementById('runWizard')) {
        window.runWizard = new RunWizard();
    }
});'''


# === ID 416: GUI Frontend – Run-Detail & Gate-Timeline ===

class RunDetailGenerator:
    """Generator for run detail view."""
    
    def generate_detail_html(self) -> str:
        """Generate run detail HTML."""
        
        return '''<!-- Run Detail View -->
<div class="run-detail-container" id="runDetail">
    <div class="run-detail-header">
        <div class="run-header-info">
            <h1>
                <i class="fas fa-code-branch"></i>
                Run <span id="runIdDisplay">Loading...</span>
            </h1>
            <div class="run-status-badge" id="runStatusBadge">
                <i class="fas fa-spinner fa-spin"></i> Loading
            </div>
        </div>
        <div class="run-header-actions">
            <button class="btn btn-secondary" id="cancelRunBtn" style="display: none;">
                <i class="fas fa-stop"></i> Cancel Run
            </button>
            <a class="btn btn-secondary" id="prLinkBtn" target="_blank" style="display: none;">
                <i class="fas fa-external-link-alt"></i> View PR
            </a>
            <button class="btn btn-secondary" onclick="history.back()">
                <i class="fas fa-arrow-left"></i> Back
            </button>
        </div>
    </div>
    
    <div class="run-detail-content">
        <div class="detail-main">
            <!-- Gate Timeline -->
            <section class="timeline-section">
                <h2><i class="fas fa-stream"></i> Pipeline Timeline</h2>
                <div class="gate-timeline" id="gateTimeline">
                    <!-- Gates will be populated by JavaScript -->
                </div>
            </section>
            
            <!-- Live Logs -->
            <section class="logs-section">
                <div class="logs-header">
                    <h2><i class="fas fa-terminal"></i> Live Logs</h2>
                    <div class="logs-actions">
                        <button class="btn btn-sm btn-secondary" id="clearLogsBtn">
                            <i class="fas fa-trash"></i> Clear
                        </button>
                        <button class="btn btn-sm btn-secondary" id="downloadLogsBtn">
                            <i class="fas fa-download"></i> Download
                        </button>
                        <label class="checkbox-label">
                            <input type="checkbox" id="autoScrollLogs" checked>
                            <span class="checkmark"></span>
                            Auto-scroll
                        </label>
                    </div>
                </div>
                <div class="logs-container">
                    <div class="logs-content" id="logsContent">
                        <!-- Logs will be populated by JavaScript -->
                    </div>
                </div>
            </section>
        </div>
        
        <div class="detail-sidebar">
            <!-- Run Info -->
            <section class="info-section">
                <h3><i class="fas fa-info-circle"></i> Run Information</h3>
                <div class="info-grid" id="runInfo">
                    <!-- Info will be populated by JavaScript -->
                </div>
            </section>
            
            <!-- Artifact Cards -->
            <section class="artifacts-section">
                <h3><i class="fas fa-archive"></i> Artifacts</h3>
                <div class="artifact-cards" id="artifactCards">
                    <!-- Artifacts will be populated by JavaScript -->
                </div>
            </section>
            
            <!-- Metrics -->
            <section class="metrics-section">
                <h3><i class="fas fa-chart-bar"></i> Metrics</h3>
                <div class="metrics-grid" id="metricsGrid">
                    <!-- Metrics will be populated by JavaScript -->
                </div>
            </section>
        </div>
    </div>
</div>'''
    
    def generate_detail_css(self) -> str:
        """Generate run detail CSS."""
        
        return '''/* Run Detail Styles */

.run-detail-container {
    max-width: 1400px;
    margin: 0 auto;
    padding: 2rem;
}

.run-detail-header {
    background: var(--surface-color);
    border-radius: 0.5rem;
    padding: 2rem;
    box-shadow: var(--shadow);
    margin-bottom: 2rem;
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.run-header-info h1 {
    margin: 0 0 0.5rem 0;
    font-size: 1.5rem;
    font-weight: 600;
    color: var(--text-primary);
}

.run-status-badge {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.5rem 1rem;
    border-radius: 0.375rem;
    font-size: 0.875rem;
    font-weight: 500;
}

.run-header-actions {
    display: flex;
    gap: 0.5rem;
}

.run-detail-content {
    display: grid;
    grid-template-columns: 1fr 350px;
    gap: 2rem;
}

/* Timeline Section */
.timeline-section {
    background: var(--surface-color);
    border-radius: 0.5rem;
    padding: 2rem;
    box-shadow: var(--shadow);
    margin-bottom: 2rem;
}

.timeline-section h2 {
    margin: 0 0 1.5rem 0;
    font-size: 1.25rem;
    font-weight: 600;
    color: var(--text-primary);
}

.gate-timeline {
    position: relative;
}

.gate-timeline::before {
    content: '';
    position: absolute;
    left: 1.5rem;
    top: 0;
    bottom: 0;
    width: 2px;
    background: var(--border-color);
}

.gate-item {
    position: relative;
    padding-left: 4rem;
    margin-bottom: 2rem;
}

.gate-item::before {
    content: '';
    position: absolute;
    left: 0.75rem;
    top: 0.75rem;
    width: 1.5rem;
    height: 1.5rem;
    border-radius: 50%;
    background: var(--border-color);
    border: 3px solid var(--surface-color);
    z-index: 1;
}

.gate-item.pending::before {
    background: var(--secondary-color);
}

.gate-item.running::before {
    background: var(--warning-color);
    animation: pulse 1s infinite;
}

.gate-item.passed::before {
    background: var(--success-color);
}

.gate-item.failed::before {
    background: var(--danger-color);
}

.gate-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 0.5rem;
}

.gate-name {
    font-size: 1rem;
    font-weight: 600;
    color: var(--text-primary);
}

.gate-duration {
    font-size: 0.875rem;
    color: var(--text-secondary);
}

.gate-description {
    font-size: 0.875rem;
    color: var(--text-secondary);
    margin-bottom: 0.5rem;
}

.gate-details {
    background: var(--background-color);
    border-radius: 0.25rem;
    padding: 0.75rem;
    font-size: 0.75rem;
    font-family: 'Monaco', 'Menlo', monospace;
}

/* Logs Section */
.logs-section {
    background: var(--surface-color);
    border-radius: 0.5rem;
    box-shadow: var(--shadow);
    overflow: hidden;
}

.logs-header {
    background: var(--background-color);
    border-bottom: 1px solid var(--border-color);
    padding: 1.5rem;
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.logs-header h2 {
    margin: 0;
    font-size: 1.25rem;
    font-weight: 600;
    color: var(--text-primary);
}

.logs-actions {
    display: flex;
    gap: 1rem;
    align-items: center;
}

.logs-container {
    height: 400px;
    overflow-y: auto;
    background: #1e1e1e;
}

.logs-content {
    padding: 1rem;
    font-family: 'Monaco', 'Menlo', monospace;
    font-size: 0.75rem;
    line-height: 1.4;
    color: #d4d4d4;
}

.log-entry {
    margin-bottom: 0.25rem;
    white-space: pre-wrap;
}

.log-entry.info {
    color: #4fc3f7;
}

.log-entry.warning {
    color: #ffb74d;
}

.log-entry.error {
    color: #f48fb1;
}

.log-entry.success {
    color: #81c784;
}

/* Sidebar */
.detail-sidebar {
    display: flex;
    flex-direction: column;
    gap: 2rem;
}

.info-section,
.artifacts-section,
.metrics-section {
    background: var(--surface-color);
    border-radius: 0.5rem;
    padding: 1.5rem;
    box-shadow: var(--shadow);
}

.info-section h3,
.artifacts-section h3,
.metrics-section h3 {
    margin: 0 0 1rem 0;
    font-size: 1rem;
    font-weight: 600;
    color: var(--text-primary);
}

.info-grid {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
}

.info-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0.5rem 0;
    border-bottom: 1px solid var(--border-color);
}

.info-item:last-child {
    border-bottom: none;
}

.info-label {
    font-size: 0.875rem;
    color: var(--text-secondary);
}

.info-value {
    font-size: 0.875rem;
    font-weight: 500;
    color: var(--text-primary);
}

/* Artifact Cards */
.artifact-cards {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
}

.artifact-card {
    border: 1px solid var(--border-color);
    border-radius: 0.375rem;
    padding: 1rem;
    transition: all 0.2s;
}

.artifact-card:hover {
    border-color: var(--primary-color);
    box-shadow: var(--shadow);
}

.artifact-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 0.5rem;
}

.artifact-name {
    font-size: 0.875rem;
    font-weight: 600;
    color: var(--text-primary);
}

.artifact-size {
    font-size: 0.75rem;
    color: var(--text-secondary);
}

.artifact-type {
    font-size: 0.75rem;
    color: var(--text-secondary);
    margin-bottom: 0.5rem;
}

.artifact-actions {
    display: flex;
    gap: 0.5rem;
}

/* Metrics Grid */
.metrics-grid {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
}

.metric-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0.75rem;
    background: var(--background-color);
    border-radius: 0.375rem;
}

.metric-label {
    font-size: 0.875rem;
    color: var(--text-secondary);
}

.metric-value {
    font-size: 1.125rem;
    font-weight: 600;
    color: var(--text-primary);
}

.metric-value.success {
    color: var(--success-color);
}

.metric-value.warning {
    color: var(--warning-color);
}

.metric-value.danger {
    color: var(--danger-color);
}

/* Responsive */
@media (max-width: 1024px) {
    .run-detail-content {
        grid-template-columns: 1fr;
    }
    
    .run-detail-header {
        flex-direction: column;
        gap: 1rem;
        text-align: center;
    }
    
    .logs-header {
        flex-direction: column;
        gap: 1rem;
        align-items: stretch;
    }
    
    .logs-actions {
        justify-content: center;
    }
}

@media (max-width: 768px) {
    .run-detail-container {
        padding: 1rem;
    }
    
    .logs-container {
        height: 300px;
    }
}'''


# === ID 417: GUI – Settings & Secure Defaults ===

class SettingsGenerator:
    """Generator for settings view."""
    
    def generate_settings_html(self) -> str:
        """Generate settings HTML."""
        
        return '''<!-- Settings View -->
<div class="settings-container" id="settingsView">
    <div class="settings-header">
        <h1><i class="fas fa-cog"></i> Settings</h1>
        <p>Configure CodePipeline defaults and security policies</p>
    </div>
    
    <div class="settings-content">
        <div class="settings-main">
            <!-- Security Settings -->
            <section class="settings-section">
                <h2><i class="fas fa-shield-alt"></i> Security Defaults</h2>
                <div class="setting-items">
                    <div class="setting-item">
                        <div class="setting-info">
                            <label class="setting-label">Secure Mode Default</label>
                            <p class="setting-description">
                                Enable secure mode by default for all new runs. This enforces
                                strict security policies and gates.
                            </p>
                        </div>
                        <div class="setting-control">
                            <label class="toggle-switch">
                                <input type="checkbox" id="secureModeDefault" checked>
                                <span class="toggle-slider"></span>
                            </label>
                        </div>
                    </div>
                    
                    <div class="setting-item">
                        <div class="setting-info">
                            <label class="setting-label">Policy Version</label>
                            <p class="setting-description">
                                Active security and quality policy version
                            </p>
                        </div>
                        <div class="setting-control">
                            <select id="policyVersion" class="form-control">
                                <option value="v1.2.0" selected>v1.2.0 (Current)</option>
                                <option value="v1.1.0">v1.1.0</option>
                                <option value="v1.0.0">v1.0.0</option>
                            </select>
                        </div>
                    </div>
                    
                    <div class="setting-item">
                        <div class="setting-info">
                            <label class="setting-label">Minimum Coverage</label>
                            <p class="setting-description">
                                Minimum code coverage percentage required for passing
                            </p>
                        </div>
                        <div class="setting-control">
                            <div class="input-with-unit">
                                <input type="number" id="minCoverage" class="form-control" 
                                       value="85" min="0" max="100">
                                <span class="input-unit">%</span>
                            </div>
                        </div>
                    </div>
                    
                    <div class="setting-item">
                        <div class="setting-info">
                            <label class="setting-label">Minimum Scorecard Score</label>
                            <p class="setting-description">
                                Minimum security scorecard score required for passing
                            </p>
                        </div>
                        <div class="setting-control">
                            <input type="number" id="minScorecard" class="form-control" 
                                   value="85" min="0" max="100">
                        </div>
                    </div>
                </div>
            </section>
            
            <!-- Scanner Configuration -->
            <section class="settings-section">
                <h2><i class="fas fa-search"></i> Security Scanners</h2>
                <div class="scanner-grid">
                    <div class="scanner-card">
                        <div class="scanner-header">
                            <h3>Trivy</h3>
                            <label class="toggle-switch">
                                <input type="checkbox" id="scannerTrivy" checked>
                                <span class="toggle-slider"></span>
                            </label>
                        </div>
                        <p class="scanner-description">
                            Container vulnerability scanner
                        </p>
                        <div class="scanner-status">
                            <span class="status-indicator success"></span>
                            <span>Installed v0.45.0</span>
                        </div>
                    </div>
                    
                    <div class="scanner-card">
                        <div class="scanner-header">
                            <h3>Grype</h3>
                            <label class="toggle-switch">
                                <input type="checkbox" id="scannerGrype" checked>
                                <span class="toggle-slider"></span>
                            </label>
                        </div>
                        <p class="scanner-description">
                            Application vulnerability scanner
                        </p>
                        <div class="scanner-status">
                            <span class="status-indicator success"></span>
                            <span>Installed v0.65.0</span>
                        </div>
                    </div>
                    
                    <div class="scanner-card">
                        <div class="scanner-header">
                            <h3>Bandit</h3>
                            <label class="toggle-switch">
                                <input type="checkbox" id="scannerBandit" checked>
                                <span class="toggle-slider"></span>
                            </label>
                        </div>
                        <p class="scanner-description">
                            Python security linter
                        </p>
                        <div class="scanner-status">
                            <span class="status-indicator success"></span>
                            <span>Installed v1.7.5</span>
                        </div>
                    </div>
                    
                    <div class="scanner-card">
                        <div class="scanner-header">
                            <h3>Semgrep</h3>
                            <label class="toggle-switch">
                                <input type="checkbox" id="scannerSemgrep" checked>
                                <span class="toggle-slider"></span>
                            </label>
                        </div>
                        <p class="scanner-description">
                            Static analysis security scanner
                        </p>
                        <div class="scanner-status">
                            <span class="status-indicator success"></span>
                            <span>Installed v1.45.0</span>
                        </div>
                    </div>
                </div>
            </section>
            
            <!-- Token Configuration -->
            <section class="settings-section">
                <h2><i class="fas fa-key"></i> Token Configuration</h2>
                <div class="setting-items">
                    <div class="setting-item">
                        <div class="setting-info">
                            <label class="setting-label">GitHub Token</label>
                            <p class="setting-description">
                                Personal access token for GitHub integration
                            </p>
                        </div>
                        <div class="setting-control">
                            <div class="token-input">
                                <input type="password" id="githubToken" class="form-control" 
                                       placeholder="ghp_xxxxxxxxxxxxxxxxxxxx">
                                <button class="btn btn-sm btn-secondary" onclick="toggleTokenVisibility('githubToken')">
                                    <i class="fas fa-eye"></i>
                                </button>
                            </div>
                        </div>
                    </div>
                    
                    <div class="setting-item">
                        <div class="setting-info">
                            <label class="setting-label">Container Registry Token</label>
                            <p class="setting-description">
                                Token for container registry authentication
                            </p>
                        </div>
                        <div class="setting-control">
                            <div class="token-input">
                                <input type="password" id="registryToken" class="form-control" 
                                       placeholder="Registry token">
                                <button class="btn btn-sm btn-secondary" onclick="toggleTokenVisibility('registryToken')">
                                    <i class="fas fa-eye"></i>
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            </section>
        </div>
        
        <div class="settings-sidebar">
            <!-- Audit Log -->
            <section class="audit-section">
                <h3><i class="fas fa-history"></i> Recent Changes</h3>
                <div class="audit-log" id="auditLog">
                    <!-- Audit entries will be populated by JavaScript -->
                </div>
            </section>
            
            <!-- System Info -->
            <section class="system-info-section">
                <h3><i class="fas fa-info-circle"></i> System Information</h3>
                <div class="system-info" id="systemInfo">
                    <div class="info-item">
                        <span class="info-label">Version:</span>
                        <span class="info-value">v2.1.0</span>
                    </div>
                    <div class="info-item">
                        <span class="info-label">Build:</span>
                        <span class="info-value">2024.01.15</span>
                    </div>
                    <div class="info-item">
                        <span class="info-label">Node:</span>
                        <span class="info-value">pipeline-01</span>
                    </div>
                </div>
            </section>
        </div>
    </div>
    
    <div class="settings-footer">
        <button class="btn btn-secondary" onclick="resetSettings()">
            <i class="fas fa-undo"></i> Reset to Defaults
        </button>
        <button class="btn btn-primary" id="saveSettings">
            <i class="fas fa-save"></i> Save Changes
        </button>
    </div>
</div>'''


# === Convenience Functions ===

def generate_advanced_gui_files(output_dir: str = "gui_advanced") -> Dict[str, Path]:
    """Generate advanced GUI files."""
    
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Generate components
    wizard_gen = RunWizardGenerator()
    detail_gen = RunDetailGenerator()
    settings_gen = SettingsGenerator()
    
    files = {}
    
    # Write wizard files
    (output_path / "wizard.html").write_text(wizard_gen.generate_wizard_html(), encoding='utf-8')
    (output_path / "wizard.css").write_text(wizard_gen.generate_wizard_css(), encoding='utf-8')
    (output_path / "wizard.js").write_text(wizard_gen.generate_wizard_js(), encoding='utf-8')
    
    # Write detail files
    (output_path / "detail.html").write_text(detail_gen.generate_detail_html(), encoding='utf-8')
    (output_path / "detail.css").write_text(detail_gen.generate_detail_css(), encoding='utf-8')
    
    # Write settings files
    (output_path / "settings.html").write_text(settings_gen.generate_settings_html(), encoding='utf-8')
    
    files = {
        "wizard_html": output_path / "wizard.html",
        "wizard_css": output_path / "wizard.css",
        "wizard_js": output_path / "wizard.js",
        "detail_html": output_path / "detail.html",
        "detail_css": output_path / "detail.css",
        "settings_html": output_path / "settings.html"
    }
    
    logger.info(f"Generated advanced GUI files in {output_path}")
    
    return files


if __name__ == "__main__":
    # Demo
    def demo_advanced_gui():
        print("Advanced GUI Components Demo:")
        
        # Generate files
        files = generate_advanced_gui_files("demo_advanced_gui")
        
        print(f"Generated files:")
        for file_type, file_path in files.items():
            print(f"  {file_type}: {file_path} ({file_path.stat().st_size} bytes)")
        
        return len(files) == 6
    
    # Run demo
    result = demo_advanced_gui()
    print(f"Demo completed: {result}")
