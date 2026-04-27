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

cursor.execute('''
    CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        description TEXT,
        image TEXT,
        customer_id INTEGER,
        column_name TEXT DEFAULT 'To Do',
        position INTEGER DEFAULT 0,
        completed BOOLEAN DEFAULT 0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (customer_id) REFERENCES customers(id)
    )
''')

cursor.execute('''
    CREATE TABLE IF NOT EXISTS task_columns (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        position INTEGER DEFAULT 0
    )
''')

cursor.execute("INSERT INTO task_columns (name, position) VALUES ('To Do', 0)")
cursor.execute("INSERT INTO task_columns (name, position) VALUES ('In Progress', 1)")
cursor.execute("INSERT INTO task_columns (name, position) VALUES ('Done', 2)")

cursor.execute('''
    CREATE TABLE IF NOT EXISTS items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        description TEXT,
        image TEXT,
        quantity INTEGER DEFAULT 0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
''')

cursor.execute("INSERT INTO status_log (status) VALUES ('healthy')")
conn.commit()
conn.close()

print("Database created: tir.db")