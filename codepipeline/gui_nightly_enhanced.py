#!/usr/bin/env python3
"""
MVP-FIX-008: GUI Nightly Sichtbarkeit
Bedienbarkeit ohne Konsole mit Nightly-Status, Reports und Dry-Run-Button.
"""

import sys
import json
import threading
import subprocess
import webbrowser
import os
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

try:
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox, scrolledtext
    GUI_AVAILABLE = True
except ImportError:
    print("⚠️  tkinter not available - GUI disabled")
    GUI_AVAILABLE = False


class NightlyEnhancedGUI:
    """Enhanced GUI mit Nightly-Sichtbarkeit"""
    
    def __init__(self, project_root: Optional[Path] = None):
        if not GUI_AVAILABLE:
            raise ImportError("tkinter not available")
        
        self.project_root = project_root or Path.cwd()
        self.reports_dir = self.project_root / "reports"
        self.trends_dir = self.reports_dir / "trends"
        
        # GUI-Komponenten
        self.root = None
        self.nightly_status_var = None
        self.nightly_reason_var = None
        self.trend_status_var = None
        
        # Nightly-Status
        self.last_nightly_status = "unknown"
        self.last_nightly_data = {}
        
        self.setup_enhanced_gui()
    
    def setup_enhanced_gui(self):
        """Setup Enhanced GUI mit Nightly-Features"""
        
        self.root = tk.Tk()
        self.root.title("🚀 CodePipeline MVP - Enhanced with Nightly")
        self.root.geometry("900x700")
        self.root.configure(bg='#f0f0f0')
        
        # Haupt-Container
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Titel
        title_label = ttk.Label(main_frame, text="🚀 CodePipeline MVP - Enhanced GUI", 
                               font=("Arial", 16, "bold"))
        title_label.pack(pady=(0, 20))
        
        # Nightly Dashboard (MVP-FIX-008)
        self.create_nightly_dashboard(main_frame)
        
        # Control Panel
        self.create_control_panel(main_frame)
        
        # Reports Panel
        self.create_reports_panel(main_frame)
        
        # Log Panel
        self.create_log_panel(main_frame)
        
        # Initial Load
        self.load_nightly_status()
        
        # Auto-Refresh Timer
        self.setup_auto_refresh()
    
    def create_nightly_dashboard(self, parent):
        """Erstelle Nightly Dashboard mit Status-Kacheln"""
        
        nightly_frame = ttk.LabelFrame(parent, text="🌙 Nightly Dashboard", padding="10")
        nightly_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Status-Kacheln-Container
        status_container = ttk.Frame(nightly_frame)
        status_container.pack(fill=tk.X, pady=(0, 10))
        
        # Kachel 1: Letzter Nightly Status
        status_kachel = ttk.LabelFrame(status_container, text="📊 Last Nightly Status", padding="10")
        status_kachel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        
        self.nightly_status_var = tk.StringVar(value="🔍 Loading...")
        status_label = ttk.Label(status_kachel, textvariable=self.nightly_status_var, 
                                font=("Arial", 12, "bold"))
        status_label.pack()
        
        self.nightly_reason_var = tk.StringVar(value="Checking nightly status...")
        reason_label = ttk.Label(status_kachel, textvariable=self.nightly_reason_var, 
                                font=("Arial", 9))
        reason_label.pack(pady=(5, 0))
        
        # Kachel 2: Trend Status
        trend_kachel = ttk.LabelFrame(status_container, text="📈 Trend Status", padding="10")
        trend_kachel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(5, 0))
        
        self.trend_status_var = tk.StringVar(value="🔍 Loading...")
        trend_label = ttk.Label(trend_kachel, textvariable=self.trend_status_var, 
                               font=("Arial", 12, "bold"))
        trend_label.pack()
        
        # Nightly Actions
        actions_frame = ttk.Frame(nightly_frame)
        actions_frame.pack(fill=tk.X, pady=(10, 0))
        
        # Button: Nightly Smoke Start (MVP-FIX-008)
        self.nightly_button = ttk.Button(actions_frame, text="🌙 Start Nightly Smoke (Dry Run)", 
                                        command=self.start_nightly_smoke)
        self.nightly_button.pack(side=tk.LEFT, padx=(0, 10))
        
        # Button: Refresh Status
        refresh_button = ttk.Button(actions_frame, text="🔄 Refresh Status", 
                                   command=self.load_nightly_status)
        refresh_button.pack(side=tk.LEFT, padx=(0, 10))
        
        # Status: Auto-Refresh
        self.auto_refresh_var = tk.StringVar(value="Auto-refresh: ON")
        auto_label = ttk.Label(actions_frame, textvariable=self.auto_refresh_var, 
                              font=("Arial", 8))
        auto_label.pack(side=tk.RIGHT)
    
    def create_control_panel(self, parent):
        """Erstelle Standard-Control-Panel"""
        
        control_frame = ttk.LabelFrame(parent, text="🎮 Pipeline Control", padding="10")
        control_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Eingabe-Grid
        input_frame = ttk.Frame(control_frame)
        input_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Spec Path
        ttk.Label(input_frame, text="Feature Spec:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        self.spec_path_var = tk.StringVar(value="templates/example_feature.yaml")
        spec_entry = ttk.Entry(input_frame, textvariable=self.spec_path_var, width=40)
        spec_entry.grid(row=0, column=1, sticky=tk.W, padx=(0, 10))
        
        spec_browse_btn = ttk.Button(input_frame, text="📁", width=3, 
                                    command=self.browse_spec_file)
        spec_browse_btn.grid(row=0, column=2, sticky=tk.W)
        
        # Target Branch
        ttk.Label(input_frame, text="Target Branch:").grid(row=1, column=0, sticky=tk.W, padx=(0, 10), pady=(5, 0))
        self.target_branch_var = tk.StringVar(value="feature/mvp-demo")
        branch_entry = ttk.Entry(input_frame, textvariable=self.target_branch_var, width=40)
        branch_entry.grid(row=1, column=1, sticky=tk.W, padx=(0, 10), pady=(5, 0))
        
        # Secure Mode
        self.secure_mode_var = tk.BooleanVar(value=False)
        secure_check = ttk.Checkbutton(input_frame, text="🔒 Secure Mode", 
                                      variable=self.secure_mode_var)
        secure_check.grid(row=2, column=0, columnspan=2, sticky=tk.W, pady=(10, 0))
        
        # Action Buttons
        buttons_frame = ttk.Frame(control_frame)
        buttons_frame.pack(fill=tk.X)
        
        # Dry Run Button
        dry_run_btn = ttk.Button(buttons_frame, text="🧪 Dry Run", 
                                command=self.start_dry_run)
        dry_run_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        # Secure Run Button
        secure_run_btn = ttk.Button(buttons_frame, text="🔒 Secure Run", 
                                   command=self.start_secure_run)
        secure_run_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        # Stop Button
        self.stop_btn = ttk.Button(buttons_frame, text="⏹️ Stop", 
                                  command=self.stop_pipeline, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT)
    
    def create_reports_panel(self, parent):
        """Erstelle Reports Panel mit Links"""
        
        reports_frame = ttk.LabelFrame(parent, text="📄 Reports & Artifacts", padding="10")
        reports_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Reports-Grid
        reports_grid = ttk.Frame(reports_frame)
        reports_grid.pack(fill=tk.X)
        
        # Zeile 1: Nightly Reports
        row = 0
        ttk.Label(reports_grid, text="🌙 Nightly Reports:", font=("Arial", 10, "bold")).grid(
            row=row, column=0, sticky=tk.W, columnspan=4, pady=(0, 5))
        
        row += 1
        ttk.Button(reports_grid, text="📊 KPI Report", width=15,
                  command=lambda: self.open_report("nightly_fail_closed_report.json")).grid(
            row=row, column=0, sticky=tk.W, padx=(0, 5))
        
        ttk.Button(reports_grid, text="📈 Trend Report", width=15,
                  command=lambda: self.open_report("trends/latest_trend.md")).grid(
            row=row, column=1, sticky=tk.W, padx=(5, 5))
        
        ttk.Button(reports_grid, text="📊 Scorecard", width=15,
                  command=lambda: self.open_report("scorecard_smoke.json")).grid(
            row=row, column=2, sticky=tk.W, padx=(5, 5))
        
        ttk.Button(reports_grid, text="🔒 Security", width=15,
                  command=lambda: self.open_report("security_consolidated_report.json")).grid(
            row=row, column=3, sticky=tk.W, padx=(5, 0))
        
        # Zeile 2: Standard Reports
        row += 1
        ttk.Label(reports_grid, text="📋 Standard Reports:", font=("Arial", 10, "bold")).grid(
            row=row, column=0, sticky=tk.W, columnspan=4, pady=(10, 5))
        
        row += 1
        ttk.Button(reports_grid, text="📈 Coverage", width=15,
                  command=lambda: self.open_report("focused_coverage_report.json")).grid(
            row=row, column=0, sticky=tk.W, padx=(0, 5))
        
        ttk.Button(reports_grid, text="📝 License", width=15,
                  command=lambda: self.open_report("license_gate_allowlist_report.json")).grid(
            row=row, column=1, sticky=tk.W, padx=(5, 5))
        
        ttk.Button(reports_grid, text="📦 SBOM", width=15,
                  command=lambda: self.open_report("sbom.json")).grid(
            row=row, column=2, sticky=tk.W, padx=(5, 5))
        
        ttk.Button(reports_grid, text="📁 All Reports", width=15,
                  command=self.open_reports_folder).grid(
            row=row, column=3, sticky=tk.W, padx=(5, 0))
    
    def create_log_panel(self, parent):
        """Erstelle Log Panel"""
        
        log_frame = ttk.LabelFrame(parent, text="📝 Pipeline Log", padding="10")
        log_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 0))
        
        # Log Text mit Scrollbar
        log_container = ttk.Frame(log_frame)
        log_container.pack(fill=tk.BOTH, expand=True)
        
        self.log_text = scrolledtext.ScrolledText(log_container, height=8, 
                                                 font=("Consolas", 9))
        self.log_text.pack(fill=tk.BOTH, expand=True)
        
        # Initial Log
        self.log_message("🚀 Enhanced GUI initialized")
        self.log_message("💡 Use Nightly Dashboard to monitor pipeline health")
    
    def load_nightly_status(self):
        """Lade Nightly Status aus Reports"""
        
        try:
            # 1. Lade Fail-Closed-Report
            fail_closed_file = self.reports_dir / "nightly_fail_closed_report.json"
            if fail_closed_file.exists():
                with open(fail_closed_file, 'r', encoding='utf-8') as f:
                    fail_closed_data = json.load(f)
                
                nightly_data = fail_closed_data.get("nightly_fail_closed", {})
                overall_status = nightly_data.get("overall_status", "unknown")
                reason_summary = nightly_data.get("reason_summary", "No details available")
                
                # Status-Ampel
                if overall_status == "pass":
                    status_text = "✅ PASS"
                    status_color = "green"
                elif overall_status == "fail":
                    status_text = "❌ FAIL"
                    status_color = "red"
                elif overall_status == "warn":
                    status_text = "⚠️ WARN"
                    status_color = "orange"
                else:
                    status_text = "❓ UNKNOWN"
                    status_color = "gray"
                
                self.nightly_status_var.set(status_text)
                self.nightly_reason_var.set(reason_summary[:60] + "..." if len(reason_summary) > 60 else reason_summary)
                
                self.last_nightly_status = overall_status
                self.last_nightly_data = nightly_data
                
                self.log_message(f"🌙 Nightly status loaded: {status_text}")
            
            else:
                self.nightly_status_var.set("❓ No Data")
                self.nightly_reason_var.set("No nightly report found")
                self.log_message("⚠️ No nightly fail-closed report found")
            
            # 2. Lade Trend-Status
            trend_file = self.trends_dir / "latest_trend.json"
            if trend_file.exists():
                with open(trend_file, 'r', encoding='utf-8') as f:
                    trend_data = json.load(f)
                
                stable_trend = trend_data.get("stable_trend", {})
                if stable_trend.get("status") == "available":
                    metrics = stable_trend.get("metrics", {})
                    trend_status = metrics.get("trend_status", "unknown")
                    success_rate = metrics.get("success_rate", 0)
                    
                    # Trend-Ampel
                    if trend_status == "green":
                        trend_text = f"🟢 HEALTHY ({success_rate}%)"
                    elif trend_status == "yellow":
                        trend_text = f"🟡 WARNING ({success_rate}%)"
                    elif trend_status == "red":
                        trend_text = f"🔴 CRITICAL ({success_rate}%)"
                    else:
                        trend_text = f"❓ UNKNOWN ({success_rate}%)"
                    
                    self.trend_status_var.set(trend_text)
                    self.log_message(f"📈 Trend status loaded: {trend_text}")
                
                else:
                    self.trend_status_var.set("❓ No Trend Data")
                    self.log_message("⚠️ No valid trend data found")
            
            else:
                self.trend_status_var.set("❓ No Trend")
                self.log_message("⚠️ No trend report found")
        
        except Exception as e:
            self.nightly_status_var.set("❌ ERROR")
            self.nightly_reason_var.set(f"Load error: {str(e)[:40]}...")
            self.trend_status_var.set("❌ ERROR")
            self.log_message(f"❌ Error loading nightly status: {e}")
    
    def start_nightly_smoke(self):
        """Starte Nightly Smoke im Dry Run (MVP-FIX-008)"""
        
        def run_nightly():
            try:
                self.nightly_button.configure(state=tk.DISABLED)
                self.log_message("🌙 Starting Nightly Smoke in Dry Run mode...")
                
                # Führe Nightly Smoke aus
                cmd = [
                    sys.executable,
                    str(self.project_root / "codepipeline" / "nightly_smoke_mvp.py"),
                    "--run",
                    "--dry-run"  # Explizit Dry Run
                ]
                
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    cwd=self.project_root,
                    timeout=300  # 5 Minuten Timeout
                )
                
                if result.returncode == 0:
                    self.log_message("✅ Nightly Smoke completed successfully!")
                    self.log_message("📊 Check reports for detailed results")
                else:
                    self.log_message(f"⚠️ Nightly Smoke completed with issues (exit: {result.returncode})")
                    self.log_message("📋 Check reports for details")
                
                # Output-Preview
                if result.stdout:
                    preview = result.stdout[:300] + "..." if len(result.stdout) > 300 else result.stdout
                    self.log_message(f"📝 Output preview: {preview}")
                
                # Auto-refresh nach Nightly Run
                self.root.after(2000, self.load_nightly_status)
                
            except subprocess.TimeoutExpired:
                self.log_message("❌ Nightly Smoke timed out after 5 minutes")
            except Exception as e:
                self.log_message(f"❌ Nightly Smoke error: {e}")
            finally:
                self.nightly_button.configure(state=tk.NORMAL)
        
        # Führe in separatem Thread aus
        threading.Thread(target=run_nightly, daemon=True).start()
    
    def start_dry_run(self):
        """Starte Standard Dry Run"""
        self.log_message("🧪 Starting Dry Run...")
        # TODO: Implementiere Standard-Pipeline-Aufruf
        messagebox.showinfo("Dry Run", "Dry Run would be started here")
    
    def start_secure_run(self):
        """Starte Secure Run"""
        self.log_message("🔒 Starting Secure Run...")
        # TODO: Implementiere Secure-Pipeline-Aufruf
        messagebox.showinfo("Secure Run", "Secure Run would be started here")
    
    def stop_pipeline(self):
        """Stoppe Pipeline"""
        self.log_message("⏹️ Stopping pipeline...")
        messagebox.showinfo("Stop", "Pipeline would be stopped here")
    
    def browse_spec_file(self):
        """Browse für Spec-Datei"""
        filename = filedialog.askopenfilename(
            title="Select Feature Spec",
            filetypes=[("YAML files", "*.yaml *.yml"), ("All files", "*.*")],
            initialdir=self.project_root / "templates"
        )
        if filename:
            # Relative zum Projekt-Root
            try:
                rel_path = Path(filename).relative_to(self.project_root)
                self.spec_path_var.set(str(rel_path))
            except ValueError:
                self.spec_path_var.set(filename)
    
    def open_report(self, report_path: str):
        """Öffne Report-Datei"""
        
        try:
            full_path = self.reports_dir / report_path
            
            if not full_path.exists():
                messagebox.showwarning("Report Not Found", f"Report not found: {report_path}")
                self.log_message(f"⚠️ Report not found: {report_path}")
                return
            
            # Öffne im Standard-Editor/Browser
            if sys.platform == "win32":
                os.startfile(str(full_path))
            elif sys.platform == "darwin":
                subprocess.run(["open", str(full_path)])
            else:
                subprocess.run(["xdg-open", str(full_path)])
            
            self.log_message(f"📂 Opened report: {report_path}")
            
        except Exception as e:
            messagebox.showerror("Error", f"Could not open report: {e}")
            self.log_message(f"❌ Error opening report {report_path}: {e}")
    
    def open_reports_folder(self):
        """Öffne Reports-Ordner"""
        
        try:
            if sys.platform == "win32":
                os.startfile(str(self.reports_dir))
            elif sys.platform == "darwin":
                subprocess.run(["open", str(self.reports_dir)])
            else:
                subprocess.run(["xdg-open", str(self.reports_dir)])
            
            self.log_message(f"📁 Opened reports folder: {self.reports_dir}")
            
        except Exception as e:
            messagebox.showerror("Error", f"Could not open reports folder: {e}")
            self.log_message(f"❌ Error opening reports folder: {e}")
    
    def setup_auto_refresh(self):
        """Setup Auto-Refresh Timer"""
        
        def auto_refresh():
            self.load_nightly_status()
            # Refresh alle 30 Sekunden
            self.root.after(30000, auto_refresh)
        
        # Erstes Refresh nach 5 Sekunden
        self.root.after(5000, auto_refresh)
    
    def log_message(self, message: str):
        """Schreibe Nachricht ins Log"""
        
        if self.log_text:
            timestamp = datetime.now().strftime("%H:%M:%S")
            log_entry = f"[{timestamp}] {message}\\n"
            
            self.log_text.insert(tk.END, log_entry)
            self.log_text.see(tk.END)
    
    def run(self):
        """Starte GUI"""
        
        try:
            self.log_message("🚀 Enhanced GUI with Nightly Dashboard ready!")
            self.root.mainloop()
        except KeyboardInterrupt:
            print("\\n🛑 GUI interrupted")
        except Exception as e:
            print(f"💥 GUI error: {e}")


def main():
    """Main function für Enhanced GUI"""
    print("🎯 MVP-FIX-008: GUI Nightly Sichtbarkeit")
    
    if not GUI_AVAILABLE:
        print("❌ tkinter not available - cannot start GUI")
        return 1
    
    try:
        # Erstelle Enhanced GUI
        gui = NightlyEnhancedGUI()
        
        print("🖥️ Starting Enhanced GUI with Nightly Dashboard...")
        print("💡 Features:")
        print("   • Nightly Status Dashboard with Traffic Light")
        print("   • Trend Analysis with Success Rate")
        print("   • One-Click Report Access (KPI, Trend, Scorecard, Security)")
        print("   • Nightly Smoke Dry Run Button")
        print("   • Auto-Refresh every 30 seconds")
        
        # Starte GUI
        gui.run()
        
        print("✅ Enhanced GUI closed")
        return 0
        
    except Exception as e:
        print(f"💥 Enhanced GUI error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
