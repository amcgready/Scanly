import os
import sqlite3

SCAN_HISTORY_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'src', 'scan_history.txt')
SCAN_HISTORY_DB = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'src', 'scan_history.db')

def _init_scan_history_db():
    """Ensure the scan history DB exists."""
    conn = sqlite3.connect(SCAN_HISTORY_DB)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS archived_scan_history (
            path TEXT PRIMARY KEY,
            archived_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def is_path_in_scan_history(path):
    """Return True if path is in scan_history.txt or archived DB."""
    # Check txt
    if os.path.exists(SCAN_HISTORY_FILE):
        with open(SCAN_HISTORY_FILE, 'r', encoding='utf-8') as f:
            if path in (line.strip() for line in f):
                return True
    # Check DB
    _init_scan_history_db()
    conn = sqlite3.connect(SCAN_HISTORY_DB)
    c = conn.cursor()
    c.execute('SELECT 1 FROM archived_scan_history WHERE path=?', (path,))
    result = c.fetchone()
    conn.close()
    return result is not None