"""
Module: codepipeline.datastore
Beschreibung: CRUD-API für Iterations-Daten mit CSV/JSON-Export.
"""

import csv
import json
import sqlite3

DB_SCHEMA = """
CREATE TABLE IF NOT EXISTS iterations (
    id INTEGER PRIMARY KEY,
    timestamp DATETIME NOT NULL,
    patch TEXT NOT NULL,
    score REAL NOT NULL,
    coverage_delta REAL DEFAULT 0.0,
    performance REAL DEFAULT 0.0,
    cost REAL DEFAULT 0.0,
    status TEXT NOT NULL
);
"""

class DataStore:
    def __init__(self, db_path):
        self.db_path = db_path
        self._initialize()

    def _initialize(self):
        """Initialisiert die Datenbank und das Schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(DB_SCHEMA)

    def create_iteration(self, timestamp, patch, score, status, coverage_delta=0.0, performance=0.0, cost=0.0):
        """Legt einen neuen Iterationseintrag an."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "INSERT INTO iterations (timestamp, patch, score, status, coverage_delta, performance, cost) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (timestamp, patch, score, status, coverage_delta, performance, cost)
            )
            return cursor.lastrowid

    def get_iteration(self, iteration_id):
        """Gibt einen Iterationsdatensatz anhand der ID zurück."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT id, timestamp, patch, score, status, coverage_delta, performance, cost FROM iterations WHERE id = ?",
                (iteration_id,)
            )
            row = cursor.fetchone()
            return dict(zip([column[0] for column in cursor.description], row, strict=False)) if row else None

    def list_iterations(self):
        """Listet alle Iterationsdatensätze."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT id, timestamp, patch, score, status, coverage_delta, performance, cost FROM iterations ORDER BY id"
            )
            columns = [col[0] for col in cursor.description]
            return [dict(zip(columns, row, strict=False)) for row in cursor.fetchall()]

    def update_iteration(self, iteration_id, **fields):
        """Aktualisiert ein Iterationsdatensatz. Felder: timestamp, patch, score, status, coverage_delta, performance, cost."""
        if not fields:
            return False
        keys = ", ".join(f"{k}=?" for k in fields)
        values = list(fields.values()) + [iteration_id]
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                f"UPDATE iterations SET {keys} WHERE id = ?",
                values
            )
            return cursor.rowcount > 0

    def delete_iteration(self, iteration_id):
        """Löscht einen Iterationsdatensatz anhand der ID."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "DELETE FROM iterations WHERE id = ?",
                (iteration_id,)
            )
            return cursor.rowcount > 0

    def export_to_csv(self, csv_path):
        """Exportiert alle Iterationsdatensätze nach CSV."""
        rows = self.list_iterations()
        if not rows:
            return False
        with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)
        return True

    def export_to_json(self, json_path):
        """Exportiert alle Iterationsdatensätze nach JSON."""
        rows = self.list_iterations()
        with open(json_path, 'w', encoding='utf-8') as jsonfile:
            json.dump(rows, jsonfile, ensure_ascii=False, indent=2)
        return True
