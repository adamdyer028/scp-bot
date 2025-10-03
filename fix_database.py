# fix_database.py
import sqlite3

conn = sqlite3.connect('library_content.db')
cursor = conn.cursor()

try:
    cursor.execute('ALTER TABLE library_content ADD COLUMN description TEXT')
    conn.commit()
    print("✅ Added description column to database")
except Exception as e:
    print(f"Column might already exist: {e}")

conn.close()