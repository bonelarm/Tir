import sqlite3
import csv
import io
import json
import time
from pathlib import Path
from fastapi import FastAPI, Request, Form, UploadFile, File, Query
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import shutil

START_TIME = time.time()

app = FastAPI()

BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "tir.db"
STATIC_DIR = BASE_DIR / "static"
IMAGES_DIR = STATIC_DIR / "images"

STATIC_DIR.mkdir(exist_ok=True)
IMAGES_DIR.mkdir(exist_ok=True)

def ensure_items_schema():
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("PRAGMA table_info(items)")
        cols = [r[1] for r in cur.fetchall()]
        if 'year_made' not in cols:
            cur.execute("ALTER TABLE items ADD COLUMN year_made INTEGER")
        if 'made_in' not in cols:
            cur.execute("ALTER TABLE items ADD COLUMN made_in TEXT")
        if 'status' not in cols:
            cur.execute("ALTER TABLE items ADD COLUMN status INTEGER DEFAULT 0")
        if 'class_id' not in cols:
            cur.execute("ALTER TABLE items ADD COLUMN class_id INTEGER")
        # Ensure classes table exists
        cur.execute("CREATE TABLE IF NOT EXISTS classes (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL, position INTEGER DEFAULT 0)")
        conn.commit()
        conn.close()
    except Exception:
        # If DB not ready or table missing, ignore here; could be created later by migrations
        pass

ensure_items_schema()

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.mount("/css", StaticFiles(directory="css"), name="css")
app.mount("/js", StaticFiles(directory="js"), name="js")

templates = Jinja2Templates(directory="templates")

# Add json filter to Jinja2
def tojson_filter(obj):
    return json.dumps(obj)

templates.env.filters['tojson'] = tojson_filter


def get_db_status():
    try:
        start = time.time()
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT status, timestamp FROM status_log ORDER BY id DESC LIMIT 1")
        result = cursor.fetchone()
        cursor.execute("SELECT COUNT(*) FROM customers")
        customer_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM tasks")
        task_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM items")
        item_count = cursor.fetchone()[0]
        conn.close()
        response_time = round((time.time() - start) * 1000, 2)
        db_size = round(DB_PATH.stat().st_size / 1024, 2) if DB_PATH.exists() else 0
        uptime_seconds = int(time.time() - START_TIME)
        uptime_str = f"{uptime_seconds // 3600}h {(uptime_seconds % 3600) // 60}m {uptime_seconds % 60}s"
        if result:
            return {"status": result[0], "timestamp": result[1], "customer_count": customer_count,
                    "task_count": task_count, "item_count": item_count, "db_size_kb": db_size,
                    "uptime": uptime_str, "response_time_ms": response_time}
        return {"status": "unknown", "customer_count": customer_count, "task_count": task_count,
                "item_count": item_count, "db_size_kb": db_size, "uptime": uptime_str,
                "response_time_ms": response_time}
    except Exception as e:
        return {"status": "error", "customer_count": 0, "task_count": 0, "item_count": 0,
                "db_size_kb": 0, "uptime": "0s", "response_time_ms": 0}


@app.get("/set_language/{lang}")
async def set_language(lang: str, request: Request):
    # Minimal i18n switch: supports English ('en') and Armenian ('hy')
    if lang not in ("en", "hy"):
        lang = "en"
    referer = request.headers.get("referer") or "/"
    response = RedirectResponse(url=referer, status_code=303)
    # Persist preference for a year
    response.set_cookie(key="lang", value=lang, max_age=60 * 60 * 24 * 365)
    return response


def get_items(search: str = "", sort: str = "name_asc"):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    query = "SELECT i.*, c.name as class_name FROM items i LEFT JOIN classes c ON i.class_id = c.id WHERE 1=1"
    params = []
    
    if search:
        search_term = f"%{search}%"
        query += " AND (i.name LIKE ? OR i.description LIKE ?)"
        params.extend([search_term, search_term])
    
    if sort == "name_asc":
        query += " ORDER BY i.name ASC"
    elif sort == "name_desc":
        query += " ORDER BY i.name DESC"
    elif sort == "quantity_asc":
        query += " ORDER BY i.quantity ASC"
    elif sort == "quantity_desc":
        query += " ORDER BY i.quantity DESC"
    elif sort == "cost_asc":
        query += " ORDER BY i.cost ASC"
    elif sort == "cost_desc":
        query += " ORDER BY i.cost DESC"
    else:
        query += " ORDER BY i.name ASC"
    
    cursor.execute(query, params)
    items = cursor.fetchall()
    conn.close()
    return [dict(row) for row in items]


def get_classes():
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT id, name FROM classes ORDER BY name ASC")
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    except Exception:
        return []


def get_item(item_id):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT i.*, c.name as class_name FROM items i LEFT JOIN classes c ON i.class_id = c.id WHERE i.id = ?", (item_id,))
    item = cursor.fetchone()
    conn.close()
    return dict(item) if item else None


def get_customers(search: str = "", sort: str = "name_asc"):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    query = "SELECT * FROM customers WHERE 1=1"
    params = []
    
    if search:
        search_term = f"%{search}%"
        query += " AND (name LIKE ? OR email LIKE ? OR description LIKE ? OR company LIKE ?)"
        params.extend([search_term, search_term, search_term, search_term])
    
    if sort == "name_asc":
        query += " ORDER BY name ASC"
    elif sort == "name_desc":
        query += " ORDER BY name DESC"
    elif sort == "date_asc":
        query += " ORDER BY id ASC"
    elif sort == "date_desc":
        query += " ORDER BY id DESC"
    else:
        query += " ORDER BY name ASC"
    
    cursor.execute(query, params)
    customers = cursor.fetchall()
    conn.close()
    return [dict(row) for row in customers]


def get_customer(customer_id):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM customers WHERE id = ?", (customer_id,))
    customer = cursor.fetchone()
    conn.close()
    return dict(customer) if customer else None


def get_contacts(customer_id):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM contacts WHERE customer_id = ? ORDER BY id DESC", (customer_id,))
    contacts = cursor.fetchall()
    conn.close()
    return [dict(row) for row in contacts]


def get_notes(customer_id):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM customer_notes WHERE customer_id = ? ORDER BY created_at DESC", (customer_id,))
    notes = cursor.fetchall()
    conn.close()
    return [dict(row) for row in notes]


def get_tasks():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("""
        SELECT t.*,
            GROUP_CONCAT(DISTINCT c.id) as customer_ids,
            GROUP_CONCAT(DISTINCT c.name) as customer_names,
            GROUP_CONCAT(DISTINCT i.id) as item_ids,
            GROUP_CONCAT(DISTINCT i.name) as item_names
        FROM tasks t
        LEFT JOIN task_customers tc ON t.id = tc.task_id
        LEFT JOIN customers c ON tc.customer_id = c.id
        LEFT JOIN task_items ti ON t.id = ti.task_id
        LEFT JOIN items i ON ti.item_id = i.id
        GROUP BY t.id
        ORDER BY t.position ASC, t.created_at DESC
    """)
    tasks = cursor.fetchall()
    conn.close()
    return [dict(row) for row in tasks]


def get_items_list():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT id, name FROM items ORDER BY name ASC")
    items = cursor.fetchall()
    conn.close()
    return [dict(row) for row in items]


def get_customers_list():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT id, name FROM customers ORDER BY name ASC")
    customers = cursor.fetchall()
    conn.close()
    return [dict(row) for row in customers]


def get_task_columns():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM task_columns ORDER BY position ASC")
    columns = cursor.fetchall()
    conn.close()
    return [dict(row) for row in columns]


@app.get("/", response_class=HTMLResponse)
def root(request: Request):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) as count FROM customers")
    customer_count = cursor.fetchone()["count"]

    cursor.execute("SELECT COUNT(*) as count FROM items")
    item_count = cursor.fetchone()["count"]

    cursor.execute("SELECT COUNT(*) as count FROM tasks")
    task_count = cursor.fetchone()["count"]

    cursor.execute("SELECT COUNT(*) as count FROM tasks WHERE column_name = 'Done'")
    done_count = cursor.fetchone()["count"]

    # Tasks by column for chart
    cursor.execute("SELECT column_name, COUNT(*) as count FROM tasks GROUP BY column_name ORDER BY COUNT(*) DESC")
    tasks_by_column = [{"name": row["column_name"], "count": row["count"]} for row in cursor.fetchall()]

    # Recent tasks for activity feed
    cursor.execute("""
        SELECT t.title, t.column_name, t.created_at,
               GROUP_CONCAT(DISTINCT c.name) as customer_names
        FROM tasks t
        LEFT JOIN task_customers tc ON t.id = tc.task_id
        LEFT JOIN customers c ON tc.customer_id = c.id
        GROUP BY t.id
        ORDER BY t.created_at DESC LIMIT 5
    """)
    recent_tasks = [dict(row) for row in cursor.fetchall()]

    # All items for price dashboard (use cost as price if price is 0)
    cursor.execute("SELECT id, name, CASE WHEN price > 0 THEN price ELSE cost END as price, quantity FROM items ORDER BY name ASC")
    all_items = [dict(row) for row in cursor.fetchall()]

    conn.close()

    completion_rate = round((done_count / task_count * 100) if task_count > 0 else 0, 1)

    return templates.TemplateResponse("index.html", {
        "request": request,
        "customer_count": customer_count,
        "item_count": item_count,
        "task_count": task_count,
        "done_count": done_count,
        "tasks_by_column": tasks_by_column,
        "recent_tasks": recent_tasks,
        "completion_rate": completion_rate,
        "all_items": all_items
    })


@app.get("/cs", response_class=HTMLResponse)
def cs(request: Request):
    return templates.TemplateResponse("cs.html", {"request": request})

@app.get("/status", response_class=HTMLResponse)
def status(request: Request):
    return templates.TemplateResponse("status.html", {"request": request})


@app.get("/customers", response_class=HTMLResponse)
def customers(request: Request, search: str = "", sort: str = "name_asc"):
    customer_list = get_customers(search, sort)
    return templates.TemplateResponse("customers.html", {
        "request": request,
        "customers": customer_list,
        "search": search,
        "sort": sort
    })


@app.get("/customers/export")
def export_customers():
    customers = get_customers()
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Name", "Email", "Phone", "Description", "Address", "Company", "Website"])
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    for customer in customers:
        cursor.execute("SELECT name, phone FROM contacts WHERE customer_id = ? LIMIT 1", (customer["id"],))
        contact = cursor.fetchone()
        phones = contact["phone"] if contact else ""
        writer.writerow([
            customer["name"],
            customer["email"] or "",
            phones,
            customer["description"] or "",
            customer["address"] or "",
            customer["company"] or "",
            customer["website"] or ""
        ])
    conn.close()
    
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=customers.csv"}
    )


@app.post("/customers/import")
async def import_customers(file: UploadFile = File(...)):
    if not file.filename.endswith('.csv'):
        return RedirectResponse(url="/customers", status_code=303)
    
    content = await file.read()
    try:
        reader = csv.DictReader(io.StringIO(content.decode('utf-8')))
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        for row in reader:
            name = row.get("Name", "").strip()
            if name:
                cursor.execute("""
                    INSERT INTO customers (name, email, description, address, company, website)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    name,
                    row.get("Email", "").strip(),
                    row.get("Description", "").strip(),
                    row.get("Address", "").strip(),
                    row.get("Company", "").strip(),
                    row.get("Website", "").strip()
                ))
                
                customer_id = cursor.lastrowid
                phone = row.get("Phone", "").strip()
                if phone:
                    cursor.execute("INSERT INTO contacts (customer_id, name, phone) VALUES (?, ?, ?)",
                                   (customer_id, name, phone))
        
        conn.commit()
        conn.close()
    except:
        pass
    
    return RedirectResponse(url="/customers", status_code=303)


@app.get("/customers/{customer_id}", response_class=HTMLResponse)
def customer_detail(customer_id: int, request: Request):
    customer = get_customer(customer_id)
    if not customer:
        return RedirectResponse(url="/customers", status_code=303)
    contacts = get_contacts(customer_id)
    notes = get_notes(customer_id)
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get tasks linked via task_customers junction table
    cursor.execute("""
        SELECT t.* FROM tasks t
        INNER JOIN task_customers tc ON t.id = tc.task_id
        WHERE tc.customer_id = ?
        ORDER BY t.position ASC, t.created_at DESC
    """, (customer_id,))
    customer_tasks = cursor.fetchall()
    conn.close()
    
    return templates.TemplateResponse("customer_detail.html", {
        "request": request,
        "customer": customer,
        "contacts": contacts,
        "notes": notes,
        "tasks": [dict(row) for row in customer_tasks]
    })


@app.get("/customers/edit/{customer_id}", response_class=HTMLResponse)
def edit_customer(customer_id: int, request: Request):
    customer = get_customer(customer_id)
    if not customer:
        return RedirectResponse(url="/customers", status_code=303)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get tasks linked via task_customers junction table
    cursor.execute("""
        SELECT t.id, t.title, t.column_name, t.completed FROM tasks t
        INNER JOIN task_customers tc ON t.id = tc.task_id
        WHERE tc.customer_id = ?
        ORDER BY t.created_at DESC
    """, (customer_id,))
    tasks = cursor.fetchall()
    conn.close()

    return templates.TemplateResponse("customer_edit.html", {
        "request": request,
        "customer": customer,
        "tasks": [dict(row) for row in tasks]
    })


@app.post("/customers/edit/{customer_id}")
async def update_customer(customer_id: int, name: str = Form(...), email: str = Form(""),
                          company: str = Form(""), website: str = Form(""), address: str = Form(""),
                          description: str = Form(""), image: UploadFile = File(None)):
    customer = get_customer(customer_id)
    if not customer:
        return RedirectResponse(url="/customers", status_code=303)

    image_path = customer["image"]
    if image and image.filename:
        if customer["image"]:
            old_file = STATIC_DIR / customer["image"]
            if old_file.exists():
                old_file.unlink()
        safe_filename = f"{Path(image.filename).stem[:50]}{Path(image.filename).suffix}"
        image_path = f"images/{safe_filename}"
        file_path = STATIC_DIR / image_path
        with open(file_path, "wb") as f:
            shutil.copyfileobj(image.file, f)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE customers SET name = ?, description = ?, email = ?, address = ?, company = ?, website = ?, image = ?
        WHERE id = ?
    """, (name, description, email, address, company, website, image_path, customer_id))
    conn.commit()
    conn.close()

    return RedirectResponse(url="/customers", status_code=303)


@app.post("/customers/delete/{customer_id}")
def delete_customer(customer_id: int):
    customer = get_customer(customer_id)
    if customer and customer["image"]:
        old_file = STATIC_DIR / customer["image"]
        if old_file.exists():
            old_file.unlink()

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM contacts WHERE customer_id = ?", (customer_id,))
    cursor.execute("DELETE FROM customer_notes WHERE customer_id = ?", (customer_id,))
    cursor.execute("DELETE FROM customers WHERE id = ?", (customer_id,))
    conn.commit()
    conn.close()

    return RedirectResponse(url="/customers", status_code=303)


@app.post("/customers/{customer_id}/contact/add")
def add_contact(customer_id: int, contact_name: str = Form(...), phone: str = Form(...), email: str = Form("")):
    customer = get_customer(customer_id)
    if not customer:
        return RedirectResponse(url="/customers", status_code=303)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO contacts (customer_id, name, phone, email) VALUES (?, ?, ?, ?)",
                   (customer_id, contact_name, phone, email))
    conn.commit()
    conn.close()

    return RedirectResponse(url=f"/customers/{customer_id}", status_code=303)


@app.post("/customers/{customer_id}/contact/delete/{contact_id}")
def delete_contact(customer_id: int, contact_id: int):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM contacts WHERE id = ? AND customer_id = ?", (contact_id, customer_id))
    conn.commit()
    conn.close()
    return RedirectResponse(url=f"/customers/{customer_id}", status_code=303)


@app.post("/customers/{customer_id}/contact/edit/{contact_id}")
def edit_contact(customer_id: int, contact_id: int, contact_name: str = Form(...), phone: str = Form(...), email: str = Form("")):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE contacts SET name = ?, phone = ?, email = ? WHERE id = ? AND customer_id = ?",
                   (contact_name, phone, email, contact_id, customer_id))
    conn.commit()
    conn.close()
    return RedirectResponse(url=f"/customers/{customer_id}", status_code=303)


@app.post("/customers/{customer_id}/note/add")
def add_note(customer_id: int, note: str = Form(...)):
    customer = get_customer(customer_id)
    if not customer:
        return RedirectResponse(url="/customers", status_code=303)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO customer_notes (customer_id, note) VALUES (?, ?)",
                   (customer_id, note))
    conn.commit()
    conn.close()

    return RedirectResponse(url=f"/customers/{customer_id}", status_code=303)


@app.post("/customers/{customer_id}/note/delete/{note_id}")
def delete_note(customer_id: int, note_id: int):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM customer_notes WHERE id = ? AND customer_id = ?", (note_id, customer_id))
    conn.commit()
    conn.close()
    return RedirectResponse(url=f"/customers/{customer_id}", status_code=303)


@app.post("/customers/add")
async def add_customer(name: str = Form(...), description: str = Form(""), email: str = Form(""),
                       address: str = Form(""), company: str = Form(""), website: str = Form(""),
                       image: UploadFile = File(None)):
    image_path = ""
    if image and image.filename:
        safe_filename = f"{Path(image.filename).stem[:50]}{Path(image.filename).suffix}"
        image_path = f"images/{safe_filename}"
        file_path = STATIC_DIR / image_path
        with open(file_path, "wb") as f:
            shutil.copyfileobj(image.file, f)

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO customers (name, image, description, email, address, company, website)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (name, image_path, description, email, address, company, website))
        conn.commit()
        conn.close()
    except Exception as e:
        # In case of DB errors (eg. NOT NULL constraints), gracefully continue by not blocking the request
        print("Error adding customer:", e)

    return RedirectResponse(url="/customers", status_code=303)


@app.get("/tasks", response_class=HTMLResponse)
def tasks(request: Request):
    task_list = get_tasks()
    columns = get_task_columns()
    customers = get_customers_list()
    items = get_items_list()
    return templates.TemplateResponse("tasks.html", {"request": request, "tasks": task_list, "columns": columns, "customers": customers, "items": items})


@app.post("/tasks/add")
async def add_task(title: str = Form(...), description: str = Form(""), column_name: str = Form("To Do"), customer_ids: list[str] = Form([]), item_ids: list[str] = Form([]), image: UploadFile = File(None)):
    image_path = ""
    if image and image.filename:
        safe_filename = f"{Path(image.filename).stem[:50]}{Path(image.filename).suffix}"
        image_path = f"images/{safe_filename}"
        file_path = STATIC_DIR / image_path
        with open(file_path, "wb") as f:
            shutil.copyfileobj(image.file, f)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT COALESCE(MAX(position), 0) + 1 as pos FROM tasks WHERE column_name = ?", (column_name,))
    pos = cursor.fetchone()[0]
    cursor.execute("INSERT INTO tasks (title, description, image, column_name, position) VALUES (?, ?, ?, ?, ?)", (title, description, image_path, column_name, pos))
    task_id = cursor.lastrowid

    for cid in customer_ids:
        if cid.isdigit():
            cursor.execute("INSERT OR IGNORE INTO task_customers (task_id, customer_id) VALUES (?, ?)", (task_id, int(cid)))
    for iid in item_ids:
        if iid.isdigit():
            cursor.execute("INSERT OR IGNORE INTO task_items (task_id, item_id) VALUES (?, ?)", (task_id, int(iid)))

    conn.commit()
    conn.close()
    return RedirectResponse(url="/tasks", status_code=303)


@app.post("/tasks/move/{task_id}")
def move_task(task_id: int, column_name: str = Form(...)):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT COALESCE(MAX(position), 0) + 1 as pos FROM tasks WHERE column_name = ?", (column_name,))
    pos = cursor.fetchone()[0]
    cursor.execute("UPDATE tasks SET column_name = ?, position = ? WHERE id = ?", (column_name, pos, task_id))
    conn.commit()
    conn.close()
    return RedirectResponse(url="/tasks", status_code=303)


@app.post("/tasks/toggle/{task_id}")
def toggle_task(task_id: int):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE tasks SET completed = NOT completed WHERE id = ?", (task_id,))
    conn.commit()
    conn.close()
    return RedirectResponse(url="/tasks", status_code=303)


@app.post("/tasks/edit/{task_id}")
async def edit_task(task_id: int, title: str = Form(...), description: str = Form(""), customer_ids: list[str] = Form([]), item_ids: list[str] = Form([]), image: UploadFile = File(None)):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT image FROM tasks WHERE id = ?", (task_id,))
    existing = cursor.fetchone()
    image_path = existing["image"] if existing else ""

    if image and image.filename:
        if existing and existing["image"]:
            old_file = STATIC_DIR / existing["image"]
            if old_file.exists():
                old_file.unlink()
        safe_filename = f"{Path(image.filename).stem[:50]}{Path(image.filename).suffix}"
        image_path = f"images/{safe_filename}"
        file_path = STATIC_DIR / image_path
        with open(file_path, "wb") as f:
            shutil.copyfileobj(image.file, f)

    cursor.execute("UPDATE tasks SET title = ?, description = ?, image = ? WHERE id = ?", (title, description, image_path, task_id))

    cursor.execute("DELETE FROM task_customers WHERE task_id = ?", (task_id,))
    cursor.execute("DELETE FROM task_items WHERE task_id = ?", (task_id,))
    for cid in customer_ids:
        if cid.isdigit():
            cursor.execute("INSERT OR IGNORE INTO task_customers (task_id, customer_id) VALUES (?, ?)", (task_id, int(cid)))
    for iid in item_ids:
        if iid.isdigit():
            cursor.execute("INSERT OR IGNORE INTO task_items (task_id, item_id) VALUES (?, ?)", (task_id, int(iid)))

    conn.commit()
    conn.close()
    return RedirectResponse(url="/tasks", status_code=303)


@app.post("/tasks/delete/{task_id}")
def delete_task(task_id: int):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    conn.commit()
    conn.close()
    return RedirectResponse(url="/tasks", status_code=303)


@app.post("/tasks/columns/add")
def add_column(name: str = Form(...)):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT COALESCE(MAX(position), 0) + 1 as pos FROM task_columns")
    pos = cursor.fetchone()[0]
    cursor.execute("INSERT INTO task_columns (name, position) VALUES (?, ?)", (name, pos))
    conn.commit()
    conn.close()
    return RedirectResponse(url="/tasks", status_code=303)


@app.post("/tasks/columns/edit/{column_id}")
def edit_column(column_id: int, name: str = Form(...)):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE task_columns SET name = ? WHERE id = ?", (name, column_id))
    conn.commit()
    conn.close()
    return RedirectResponse(url="/tasks", status_code=303)


@app.post("/tasks/columns/delete/{column_id}")
def delete_column(column_id: int):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM task_columns WHERE id = ?", (column_id,))
    col = cursor.fetchone()
    if col:
        cursor.execute("DELETE FROM tasks WHERE column_name = ?", (col[0],))
        cursor.execute("DELETE FROM task_columns WHERE id = ?", (column_id,))
    conn.commit()
    conn.close()
    return RedirectResponse(url="/tasks", status_code=303)


@app.get("/health")
def health():
    response = get_db_status()
    from fastapi.responses import JSONResponse
    return JSONResponse(
        content=response,
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0"
        }
    )


@app.get("/status/export-db")
def export_db():
    from fastapi.responses import FileResponse
    if not DB_PATH.exists():
        return RedirectResponse(url="/status", status_code=303)
    return FileResponse(
        path=str(DB_PATH),
        media_type="application/octet-stream",
        headers={"Content-Disposition": "attachment; filename=tir.db"}
    )


@app.post("/status/import-db")
async def import_db(file: UploadFile = File(...)):
    if not file.filename.endswith('.db'):
        return RedirectResponse(url="/status", status_code=303)
    content = await file.read()
    DB_PATH.write_bytes(content)
    return RedirectResponse(url="/status", status_code=303)


@app.get("/items", response_class=HTMLResponse)
def items(request: Request, search: str = "", sort: str = "name_asc"):
    item_list = get_items(search, sort)
    classes = get_classes()
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    for item in item_list:
        cursor.execute("""
            SELECT t.id, t.title, t.column_name, t.completed
            FROM tasks t
            INNER JOIN task_items ti ON t.id = ti.task_id
            WHERE ti.item_id = ?
            ORDER BY t.created_at DESC
            LIMIT 5
        """, (item["id"],))
        item["tasks"] = [dict(row) for row in cursor.fetchall()]

    conn.close()

    return templates.TemplateResponse("items.html", {
        "request": request,
        "items": item_list,
        "search": search,
        "sort": sort,
        "classes": classes
    })


@app.post("/items/add")
async def add_item(name: str = Form(...), description: str = Form(""), quantity: int = Form(0), cost: float = Form(0.0), image: UploadFile = File(None), year_made: int | None = Form(None), made_in: str | None = Form(None), class_id: int | None = Form(None), new_class: str | None = Form(None)):
    image_path = ""
    if image and image.filename:
        safe_filename = f"{Path(image.filename).stem[:50]}{Path(image.filename).suffix}"
        image_path = f"images/{safe_filename}"
        file_path = STATIC_DIR / image_path
        with open(file_path, "wb") as f:
            shutil.copyfileobj(image.file, f)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # Resolve class_id from new_class or existing class_id
    class_id_final = None
    if new_class and new_class.strip():
        cursor.execute("SELECT id FROM classes WHERE name = ?", (new_class.strip(),))
        row = cursor.fetchone()
        if row:
            class_id_final = row[0]
        else:
            cursor.execute("INSERT INTO classes (name) VALUES (?)", (new_class.strip(),))
            class_id_final = cursor.lastrowid
    elif class_id:
        try:
            class_id_final = int(class_id)
        except Exception:
            class_id_final = None
    cursor.execute("INSERT INTO items (name, description, image, quantity, cost, year_made, made_in, class_id, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (name, description, image_path, quantity, cost, year_made, made_in, class_id_final, 0))
    conn.commit()
    conn.close()
    return RedirectResponse(url="/items", status_code=303)


@app.get("/items/edit/{item_id}", response_class=HTMLResponse)
def edit_item(item_id: int, request: Request):
    item = get_item(item_id)
    if not item:
        return RedirectResponse(url="/items", status_code=303)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("""
        SELECT t.id, t.title, t.column_name, t.completed
        FROM tasks t
        INNER JOIN task_items ti ON t.id = ti.task_id
        WHERE ti.item_id = ?
        ORDER BY t.created_at DESC
    """, (item_id,))
    tasks = cursor.fetchall()
    conn.close()

    classes = get_classes()
    return templates.TemplateResponse("item_edit.html", {
        "request": request,
        "item": item,
        "tasks": [dict(row) for row in tasks]
        , "classes": classes
    })


@app.post("/items/edit/{item_id}")
async def update_item(item_id: int, name: str = Form(...), description: str = Form(""), quantity: int = Form(0), cost: float = Form(0.0), image: UploadFile = File(None), year_made: int | None = Form(None), made_in: str | None = Form(None), class_id: int | None = Form(None), new_class: str | None = Form(None)):
    item = get_item(item_id)
    if not item:
        return RedirectResponse(url="/items", status_code=303)

    image_path = item["image"]
    if image and image.filename:
        if item["image"]:
            old_file = STATIC_DIR / item["image"]
            if old_file.exists():
                old_file.unlink()
        safe_filename = f"{Path(image.filename).stem[:50]}{Path(image.filename).suffix}"
        image_path = f"images/{safe_filename}"
        file_path = STATIC_DIR / image_path
        with open(file_path, "wb") as f:
            shutil.copyfileobj(image.file, f)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # Resolve class_id_final from new_class or existing class_id
    class_id_final = None
    if new_class and new_class.strip():
        cursor.execute("SELECT id FROM classes WHERE name = ?", (new_class.strip(),))
        row = cursor.fetchone()
        if row:
            class_id_final = row[0]
        else:
            cursor.execute("INSERT INTO classes (name) VALUES (?)", (new_class.strip(),))
            class_id_final = cursor.lastrowid
    elif class_id:
        try:
            class_id_final = int(class_id)
        except Exception:
            class_id_final = None
    cursor.execute("UPDATE items SET name = ?, description = ?, image = ?, quantity = ?, cost = ?, year_made = ?, made_in = ?, class_id = ? WHERE id = ?", (name, description, image_path, quantity, cost, year_made, made_in, class_id_final, item_id))
    conn.commit()
    conn.close()
    return RedirectResponse(url="/items", status_code=303)


@app.post("/items/delete/{item_id}")
def delete_item(item_id: int):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM items WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()
    return RedirectResponse(url="/items", status_code=303)
