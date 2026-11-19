import sqlite3
import os

db_path = os.path.join(os.getcwd(), 'backend', 'postflow.db')
if not os.path.exists(db_path):
    print(f"DB not found at: {db_path}")
else:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id, title, platform, status, created_at FROM posts ORDER BY created_at DESC LIMIT 5")
        rows = cursor.fetchall()
        for row in rows:
            print(f"ID: {row[0]} | Title: {row[1]} | Platform: {row[2]} | Status: {row[3]} | Created: {row[4]}")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()
