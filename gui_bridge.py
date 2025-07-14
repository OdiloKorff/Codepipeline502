"""
GUI ↔ Orchestrator Bridge
"""

import threading
import tkinter as tk
from codepipeline.orchestrator import Orchestrator
from codepipeline.task_queue import TaskQueue

class GUIBridge:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.orchestrator = Orchestrator()
        self.task_queue = TaskQueue()
        self._running = True

    def start_background_worker(self):
        def worker():
            while self._running:
                task = self.task_queue.fetch_next()
                if not task:
                    import time; time.sleep(0.5)
                    continue
                try:
                    # Map tasks to orchestrator methods
                    if task['type'] == 'run_pipeline':
                        self.orchestrator.run()
                    # mark success after execution
                    self.task_queue.mark_success(task['id'])
                except Exception as exc:  # pylint: disable=broad-except
                    # Mark task as failed and persist the exception type
                    self.task_queue.mark_failed(task['id'], type(exc).__name__)
                    import logging, traceback
                    logging.error('Task %s failed: %s', task['id'], traceback.format_exc())

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()

    def setup_events(self):
        self.root.protocol("WM_DELETE_WINDOW", self.shutdown)
        # Example button event mapping
        run_button = tk.Button(self.root, text="Run Pipeline", command=lambda: self.task_queue.enqueue("run_pipeline", {}))
        run_button.pack()

    def shutdown(self):
        self._running = False
        self.root.quit()