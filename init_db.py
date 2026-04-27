import sqlite3

conn = sqlite3.connect('tir.db')
cursor = conn.cursor()

cursor.execute('''
    CREATE TABLE IF NOT EXISTS status_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        status TEXT NOT NULL,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )
''')

cursor.execute("INSERT INTO status_log (status) VALUES ('healthy')")
conn.commit()
conn.close()

print("Database created: tir.db")