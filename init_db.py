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
        item_id INTEGER,
        column_name TEXT DEFAULT 'To Do',
        position INTEGER DEFAULT 0,
        completed BOOLEAN DEFAULT 0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (customer_id) REFERENCES customers(id),
        FOREIGN KEY (item_id) REFERENCES items(id)
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
        price REAL DEFAULT 0,
        cost REAL DEFAULT 0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
''')

cursor.execute('''
    CREATE TABLE IF NOT EXISTS task_customers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        task_id INTEGER NOT NULL,
        customer_id INTEGER NOT NULL,
        FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE,
        FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE,
        UNIQUE(task_id, customer_id)
    )
''')

cursor.execute('''
    CREATE TABLE IF NOT EXISTS task_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        task_id INTEGER NOT NULL,
        item_id INTEGER NOT NULL,
        quantity INTEGER DEFAULT 1,
        FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE,
        FOREIGN KEY (item_id) REFERENCES items(id) ON DELETE CASCADE,
        UNIQUE(task_id, item_id)
    )
''')

cursor.execute("INSERT INTO status_log (status) VALUES ('healthy')")
conn.commit()
conn.close()

print("Database created: tir.db")