#!/usr/bin/env python3
"""
MVP-012: Minimal-GUI zum Steuern
Leichte lokale Oberfläche für Bedienung ohne Konsole.
"""

import sys
import json
import threading
import subprocess
import webbrowser
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


class PipelineGUI:
    """MVP GUI für Pipeline-Steuerung"""
    
    def __init__(self, project_root: Optional[Path] = None):
        if not GUI_AVAILABLE:
            raise ImportError("tkinter not available")
        
        self.project_root = project_root or Path.cwd()
        self.reports_dir = self.project_root / "reports"
        
        # GUI-Komponenten
        self.root = None
        self.spec_path_var = None
        self.target_branch_var = None
        self.secure_mode_var = None
        self.log_text = None
        self.status_frame = None
        self.progress_var = None
        
        # Pipeline-Status
        self.current_run_id = None
        self.pipeline_running = False
        self.gate_results = {}
        
        self.setup_gui()
    
    def setup_gui(self):
        """Erstelle GUI-Layout"""
        self.root = tk.Tk()
        self.root.title("MVP Pipeline Controller")
        self.root.geometry("900x700")
        self.root.resizable(True, True)
        
        # Variables
        self.spec_path_var = tk.StringVar(value="test_spec_mvp.yaml")
        self.target_branch_var = tk.StringVar(value="feature/mvp-012")
        self.secure_mode_var = tk.BooleanVar(value=True)
        self.progress_var = tk.StringVar(value="Ready")
        
        self.create_widgets()
    
    def create_widgets(self):
        """Erstelle GUI-Widgets"""
        
        # Header
        header_frame = ttk.Frame(self.root)
        header_frame.pack(fill=tk.X, padx=10, pady=5)
        
        title_label = ttk.Label(header_frame, text="🎯 MVP Pipeline Controller", font=("Arial", 16, "bold"))
        title_label.pack()
        
        subtitle_label = ttk.Label(header_frame, text="Bedienung ohne Konsole", font=("Arial", 10))
        subtitle_label.pack()
        
        # Separator
        ttk.Separator(self.root, orient='horizontal').pack(fill=tk.X, padx=10, pady=5)
        
        # Input-Frame
        input_frame = ttk.LabelFrame(self.root, text="⚙️ Pipeline Configuration", padding=10)
        input_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # Spec-Pfad
        spec_frame = ttk.Frame(input_frame)
        spec_frame.pack(fill=tk.X, pady=2)
        
        ttk.Label(spec_frame, text="Feature Spec:").pack(side=tk.LEFT)
        spec_entry = ttk.Entry(spec_frame, textvariable=self.spec_path_var, width=40)
        spec_entry.pack(side=tk.LEFT, padx=(10, 5), fill=tk.X, expand=True)
        
        spec_browse_btn = ttk.Button(spec_frame, text="Browse", command=self.browse_spec_file)
        spec_browse_btn.pack(side=tk.RIGHT)
        
        # Target-Branch
        branch_frame = ttk.Frame(input_frame)
        branch_frame.pack(fill=tk.X, pady=2)
        
        ttk.Label(branch_frame, text="Target Branch:").pack(side=tk.LEFT)
        branch_entry = ttk.Entry(branch_frame, textvariable=self.target_branch_var, width=30)
        branch_entry.pack(side=tk.LEFT, padx=(10, 5), fill=tk.X, expand=True)
        
        # Secure Mode Checkbox
        secure_frame = ttk.Frame(input_frame)
        secure_frame.pack(fill=tk.X, pady=2)
        
        secure_check = ttk.Checkbutton(secure_frame, text="🔒 Secure Mode", variable=self.secure_mode_var)
        secure_check.pack(side=tk.LEFT)
        
        # Control-Buttons
        control_frame = ttk.LabelFrame(self.root, text="🚀 Pipeline Controls", padding=10)
        control_frame.pack(fill=tk.X, padx=10, pady=5)
        
        buttons_frame = ttk.Frame(control_frame)
        buttons_frame.pack(fill=tk.X)
        
        # Dry-Run Button
        self.dry_run_btn = ttk.Button(buttons_frame, text="📋 Dry Run", 
                                     command=self.start_dry_run, style="Accent.TButton")
        self.dry_run_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        # Secure-Run Button
        self.secure_run_btn = ttk.Button(buttons_frame, text="🔒 Secure Run", 
                                        command=self.start_secure_run, style="Accent.TButton")
        self.secure_run_btn.pack(side=tk.LEFT, padx=5)
        
        # Stop Button
        self.stop_btn = ttk.Button(buttons_frame, text="⏹️ Stop", 
                                  command=self.stop_pipeline, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=5)
        
        # Refresh Button
        self.refresh_btn = ttk.Button(buttons_frame, text="🔄 Refresh", 
                                     command=self.refresh_status)
        self.refresh_btn.pack(side=tk.RIGHT)
        
        # Progress
        progress_frame = ttk.Frame(control_frame)
        progress_frame.pack(fill=tk.X, pady=(10, 0))
        
        ttk.Label(progress_frame, text="Status:").pack(side=tk.LEFT)
        self.progress_label = ttk.Label(progress_frame, textvariable=self.progress_var)
        self.progress_label.pack(side=tk.LEFT, padx=(10, 0))
        
        # Gate-Results Frame
        self.status_frame = ttk.LabelFrame(self.root, text="🚦 Gate Results", padding=10)
        self.status_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.create_gate_widgets()
        
        # Artifacts Frame
        artifacts_frame = ttk.LabelFrame(self.root, text="📁 Generated Artifacts", padding=10)
        artifacts_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.artifacts_listbox = tk.Listbox(artifacts_frame, height=4)
        self.artifacts_listbox.pack(fill=tk.X)
        self.artifacts_listbox.bind('<Double-1>', self.open_artifact)
        
        # Log-Frame
        log_frame = ttk.LabelFrame(self.root, text="📜 Live Log View", padding=10)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, height=12, state=tk.DISABLED)
        self.log_text.pack(fill=tk.BOTH, expand=True)
        
        # Initial status refresh
        self.refresh_status()
    
    def create_gate_widgets(self):
        """Erstelle Gate-Status-Widgets"""
        
        # Gate-Labels
        self.gate_labels = {}
        gates = ["Coverage", "Security", "License", "Branch Protection", "Scorecard"]
        
        for i, gate in enumerate(gates):
            frame = ttk.Frame(self.status_frame)
            frame.grid(row=i//3, column=i%3, sticky="w", padx=5, pady=2)
            
            status_label = ttk.Label(frame, text="❓", font=("Arial", 12))
            status_label.pack(side=tk.LEFT)
            
            name_label = ttk.Label(frame, text=gate)
            name_label.pack(side=tk.LEFT, padx=(5, 0))
            
            self.gate_labels[gate.lower().replace(" ", "_")] = status_label
    
    def browse_spec_file(self):
        """Durchsuche Spec-Datei"""
        filename = filedialog.askopenfilename(
            title="Select Feature Spec",
            initialdir=self.project_root,
            filetypes=[
                ("YAML files", "*.yaml *.yml"),
                ("JSON files", "*.json"),
                ("All files", "*.*")
            ]
        )
        
        if filename:
            # Mache Pfad relativ falls möglich
            try:
                rel_path = Path(filename).relative_to(self.project_root)
                self.spec_path_var.set(str(rel_path))
            except ValueError:
                self.spec_path_var.set(filename)
    
    def log_message(self, message: str):
        """Füge Nachricht zum Log hinzu"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {message}\n"
        
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, formatted_message)
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)
        
        # Update GUI
        self.root.update_idletasks()
    
    def update_progress(self, status: str):
        """Update Progress-Status"""
        self.progress_var.set(status)
        self.root.update_idletasks()
    
    def start_dry_run(self):
        """Starte Dry-Run"""
        self.start_pipeline(dry_run=True)
    
    def start_secure_run(self):
        """Starte Secure-Run"""
        self.start_pipeline(dry_run=False)
    
    def start_pipeline(self, dry_run: bool = True):
        """Starte Pipeline in separatem Thread"""
        if self.pipeline_running:
            messagebox.showwarning("Pipeline Running", "Pipeline is already running!")
            return
        
        # Validiere Eingaben
        spec_path = self.spec_path_var.get().strip()
        if not spec_path:
            messagebox.showerror("Invalid Input", "Please specify a feature spec file!")
            return
        
        target_branch = self.target_branch_var.get().strip()
        if not target_branch:
            messagebox.showerror("Invalid Input", "Please specify a target branch!")
            return
        
        # Starte Pipeline in Thread
        self.pipeline_running = True
        self.update_buttons_state()
        
        thread = threading.Thread(
            target=self.run_pipeline_thread,
            args=(spec_path, target_branch, dry_run),
            daemon=True
        )
        thread.start()
    
    def run_pipeline_thread(self, spec_path: str, target_branch: str, dry_run: bool):
        """Führe Pipeline in separatem Thread aus"""
        try:
            run_type = "Dry Run" if dry_run else "Secure Run"
            secure_mode = self.secure_mode_var.get()
            
            self.log_message(f"🚀 Starting {run_type}")
            self.log_message(f"   Spec: {spec_path}")
            self.log_message(f"   Branch: {target_branch}")
            self.log_message(f"   Secure: {secure_mode}")
            
            self.update_progress(f"Running {run_type}...")
            
            # 1. Branch Protection Preflight
            self.log_message("🛡️ Running Branch Protection Preflight...")
            self.run_branch_protection(target_branch)
            
            # 2. Feature-Run CLI
            self.log_message("🎯 Running Feature Pipeline...")
            self.run_feature_pipeline(spec_path, target_branch, dry_run, secure_mode)
            
            # 3. Evidence Collection
            self.log_message("📋 Collecting Run Evidence...")
            self.run_evidence_collection()
            
            # 4. Refresh Status
            self.refresh_status()
            
            self.log_message("✅ Pipeline completed!")
            self.update_progress("Completed")
            
        except Exception as e:
            self.log_message(f"❌ Pipeline error: {e}")
            self.update_progress("Error")
        
        finally:
            self.pipeline_running = False
            self.root.after(0, self.update_buttons_state)
    
    def run_branch_protection(self, target_branch: str):
        """Führe Branch Protection Preflight durch"""
        try:
            cmd = [
                sys.executable, 
                str(self.project_root / "codepipeline" / "branch_protection_mvp.py"),
                "--target-branch", target_branch
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=self.project_root,
                timeout=30
            )
            
            if result.returncode == 0:
                self.log_message("   ✅ Branch protection: PASS")
            else:
                self.log_message("   ❌ Branch protection: FAIL")
                
        except Exception as e:
            self.log_message(f"   ⚠️ Branch protection error: {e}")
    
    def run_feature_pipeline(self, spec_path: str, target_branch: str, dry_run: bool, secure_mode: bool):
        """Führe Feature-Pipeline durch"""
        try:
            cmd = [
                sys.executable,
                str(self.project_root / "codepipeline" / "cli_mvp.py"),
                "feature-run",
                "--spec-path", spec_path,
                "--branch-name", target_branch
            ]
            
            if dry_run:
                cmd.append("--dry-run")
            
            if secure_mode:
                cmd.append("--secure")
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=self.project_root,
                timeout=300
            )
            
            # Log output
            if result.stdout:
                for line in result.stdout.split('\n'):
                    if line.strip():
                        self.log_message(f"   {line}")
            
            if result.returncode == 0:
                self.log_message("   ✅ Feature pipeline: SUCCESS")
            else:
                self.log_message(f"   ❌ Feature pipeline: FAILED (exit {result.returncode})")
                
        except Exception as e:
            self.log_message(f"   ⚠️ Feature pipeline error: {e}")
    
    def run_evidence_collection(self):
        """Führe Evidence Collection durch"""
        try:
            cmd = [
                sys.executable,
                str(self.project_root / "codepipeline" / "run_evidence_mvp.py")
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=self.project_root,
                timeout=60
            )
            
            if result.returncode == 0:
                self.log_message("   ✅ Evidence collection: SUCCESS")
            else:
                self.log_message("   ❌ Evidence collection: FAILED")
                
        except Exception as e:
            self.log_message(f"   ⚠️ Evidence collection error: {e}")
    
    def stop_pipeline(self):
        """Stoppe Pipeline (placeholder)"""
        messagebox.showinfo("Stop Pipeline", "Pipeline stop is not implemented yet")
    
    def update_buttons_state(self):
        """Update Button-Zustände"""
        if self.pipeline_running:
            self.dry_run_btn.config(state=tk.DISABLED)
            self.secure_run_btn.config(state=tk.DISABLED)
            self.stop_btn.config(state=tk.NORMAL)
        else:
            self.dry_run_btn.config(state=tk.NORMAL)
            self.secure_run_btn.config(state=tk.NORMAL)
            self.stop_btn.config(state=tk.DISABLED)
    
    def refresh_status(self):
        """Aktualisiere Gate-Status und Artefakte"""
        self.log_message("🔄 Refreshing status...")
        
        # Lade Gate-Ergebnisse
        self.load_gate_results()
        
        # Lade Artefakte
        self.load_artifacts()
        
        self.log_message("   ✅ Status refreshed")
    
    def load_gate_results(self):
        """Lade Gate-Ergebnisse aus Reports"""
        
        # Reset alle Gates
        for gate_label in self.gate_labels.values():
            gate_label.config(text="❓", foreground="gray")
        
        # Coverage
        if (self.project_root / "coverage.xml").exists():
            self.gate_labels["coverage"].config(text="✅", foreground="green")
        
        # Security
        security_file = self.reports_dir / "security_gate_report.json"
        if security_file.exists():
            try:
                with open(security_file, 'r') as f:
                    report = json.load(f)
                status = report.get("security_gate", {}).get("status", "unknown")
                if status == "ok":
                    self.gate_labels["security"].config(text="✅", foreground="green")
                else:
                    self.gate_labels["security"].config(text="❌", foreground="red")
            except:
                self.gate_labels["security"].config(text="⚠️", foreground="orange")
        
        # License
        license_file = self.reports_dir / "sbom_license_report.json"
        if license_file.exists():
            try:
                with open(license_file, 'r') as f:
                    report = json.load(f)
                violations = report.get("sbom_license_gate", {}).get("license_violations", 999)
                if violations == 0:
                    self.gate_labels["license"].config(text="✅", foreground="green")
                else:
                    self.gate_labels["license"].config(text="❌", foreground="red")
            except:
                self.gate_labels["license"].config(text="⚠️", foreground="orange")
        
        # Branch Protection
        branch_file = self.reports_dir / "branch_protection_preflight.json"
        if branch_file.exists():
            try:
                with open(branch_file, 'r') as f:
                    report = json.load(f)
                status = report.get("branch_protection_preflight", {}).get("status", "unknown")
                if status == "PASS":
                    self.gate_labels["branch_protection"].config(text="✅", foreground="green")
                else:
                    self.gate_labels["branch_protection"].config(text="❌", foreground="red")
            except:
                self.gate_labels["branch_protection"].config(text="⚠️", foreground="orange")
        
        # Scorecard
        scorecard_file = self.reports_dir / "scorecard.json"
        if scorecard_file.exists():
            try:
                with open(scorecard_file, 'r') as f:
                    report = json.load(f)
                overall_passing = report.get("scorecard", {}).get("overall_passing", False)
                if overall_passing:
                    self.gate_labels["scorecard"].config(text="✅", foreground="green")
                else:
                    self.gate_labels["scorecard"].config(text="❌", foreground="red")
            except:
                self.gate_labels["scorecard"].config(text="⚠️", foreground="orange")
    
    def load_artifacts(self):
        """Lade Artefakte-Liste"""
        self.artifacts_listbox.delete(0, tk.END)
        
        if not self.reports_dir.exists():
            return
        
        # Sammle alle Report-Dateien
        artifacts = []
        for file_path in self.reports_dir.glob("*"):
            if file_path.is_file():
                artifacts.append(file_path)
        
        # Sortiere nach Änderungszeit (neueste zuerst)
        artifacts.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        
        # Füge zu Listbox hinzu
        for artifact in artifacts[:20]:  # Zeige nur die neuesten 20
            display_name = f"📄 {artifact.name}"
            self.artifacts_listbox.insert(tk.END, display_name)
            
        # Store file paths for opening
        self.artifact_paths = artifacts[:20]
    
    def open_artifact(self, event):
        """Öffne ausgewähltes Artefakt"""
        selection = self.artifacts_listbox.curselection()
        if not selection:
            return
        
        index = selection[0]
        if index < len(self.artifact_paths):
            file_path = self.artifact_paths[index]
            
            try:
                # Öffne mit Standard-Programm
                if sys.platform.startswith('win'):
                    subprocess.run(['start', str(file_path)], shell=True)  # nosec B602
                elif sys.platform.startswith('darwin'):
                    subprocess.run(['open', str(file_path)])
                else:
                    subprocess.run(['xdg-open', str(file_path)])
                    
                self.log_message(f"📂 Opened: {file_path.name}")
                
            except Exception as e:
                self.log_message(f"❌ Error opening {file_path.name}: {e}")
    
    def run(self):
        """Starte GUI"""
        if not GUI_AVAILABLE:
            print("❌ GUI not available - tkinter not installed")
            return 1
        
        try:
            self.log_message("🎯 MVP-012 Minimal-GUI started")
            self.log_message(f"📁 Project: {self.project_root}")
            self.root.mainloop()
            return 0
        except Exception as e:
            print(f"❌ GUI error: {e}")
            return 1


def main():
    """Main function für GUI MVP"""
    print("🎯 MVP-012: Minimal-GUI zum Steuern")
    
    if not GUI_AVAILABLE:
        print("❌ tkinter not available - cannot start GUI")
        print("   Install tkinter: apt-get install python3-tk (Linux)")
        print("   Or use python from python.org (includes tkinter)")
        return 1
    
    try:
        gui = PipelineGUI()
        return gui.run()
    except Exception as e:
        print(f"💥 GUI startup error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
