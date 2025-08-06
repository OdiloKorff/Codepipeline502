import queue
import threading
import tkinter as tk

from codepipeline.parallel_generator import generate_parallel


def main():
    """
    Launch the CodePipeline GUI with thread-safe background tasks.
    """
    root = tk.Tk()
    root.title("CodePipeline GUI")

    q = queue.Queue()

    # Label to display status
    label = tk.Label(root, text="Initializing...")
    label.pack(padx=10, pady=10)

    def worker():
        # Placeholder background work
        results = generate_parallel([lambda: "Task Result"], max_workers=1)
        for res in results:
            q.put(res)

    def poll_queue():
        try:
            msg = q.get_nowait()
            label.config(text=msg)
        except queue.Empty:
            pass
        root.after(100, poll_queue)

    # Start background thread
    threading.Thread(target=worker, daemon=True).start()
    # Start polling the queue
    root.after(100, poll_queue)
    root.mainloop()

if __name__ == "__main__":
    main()
