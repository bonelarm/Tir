import sqlite3
from pathlib import Path
from fastapi import FastAPI, Request, Form, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import shutil

app = FastAPI()

BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "tir.db"
STATIC_DIR = BASE_DIR / "static"
IMAGES_DIR = STATIC_DIR / "images"

STATIC_DIR.mkdir(exist_ok=True)
IMAGES_DIR.mkdir(exist_ok=True)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.mount("/css", StaticFiles(directory="css"), name="css")
app.mount("/js", StaticFiles(directory="js"), name="js")

templates = Jinja2Templates(directory="templates")


def get_db_status():
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT status, timestamp FROM status_log ORDER BY id DESC LIMIT 1")
        result = cursor.fetchone()
        cursor.execute("SELECT COUNT(*) FROM customers")
        customer_count = cursor.fetchone()[0]
        conn.close()
        if result:
            return {"status": result[0], "timestamp": result[1], "customer_count": customer_count}
        return {"status": "unknown", "customer_count": customer_count}
    except:
        return {"status": "error", "customer_count": 0}


def get_customers():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM customers ORDER BY id DESC")
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


@app.get("/", response_class=HTMLResponse)
def root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/status", response_class=HTMLResponse)
def status(request: Request):
    return templates.TemplateResponse("status.html", {"request": request})


@app.get("/customers", response_class=HTMLResponse)
def customers(request: Request):
    customer_list = get_customers()
    return templates.TemplateResponse("customers.html", {"request": request, "customers": customer_list})


@app.get("/customers/{customer_id}", response_class=HTMLResponse)
def customer_detail(customer_id: int, request: Request):
    customer = get_customer(customer_id)
    if not customer:
        return RedirectResponse(url="/customers", status_code=303)
    contacts = get_contacts(customer_id)
    return templates.TemplateResponse("customer_detail.html", {"request": request, "customer": customer, "contacts": contacts})


@app.get("/customers/edit/{customer_id}", response_class=HTMLResponse)
def edit_customer(customer_id: int, request: Request):
    customer = get_customer(customer_id)
    if not customer:
        return RedirectResponse(url="/customers", status_code=303)
    return templates.TemplateResponse("customer_edit.html", {"request": request, "customer": customer})


@app.post("/customers/edit/{customer_id}")
async def update_customer(customer_id: int, name: str = Form(...), description: str = Form(""), image: UploadFile = File(None)):
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
    cursor.execute("UPDATE customers SET name = ?, description = ?, image = ? WHERE id = ?",
                   (name, description, image_path, customer_id))
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
    cursor.execute("DELETE FROM customers WHERE id = ?", (customer_id,))
    conn.commit()
    conn.close()

    return RedirectResponse(url="/customers", status_code=303)


@app.post("/customers/{customer_id}/contact/add")
def add_contact(customer_id: int, contact_name: str = Form(...), phone: str = Form(...)):
    customer = get_customer(customer_id)
    if not customer:
        return RedirectResponse(url="/customers", status_code=303)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO contacts (customer_id, name, phone) VALUES (?, ?, ?)",
                   (customer_id, contact_name, phone))
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
def edit_contact(customer_id: int, contact_id: int, contact_name: str = Form(...), phone: str = Form(...)):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE contacts SET name = ?, phone = ? WHERE id = ? AND customer_id = ?",
                   (contact_name, phone, contact_id, customer_id))
    conn.commit()
    conn.close()
    return RedirectResponse(url=f"/customers/{customer_id}", status_code=303)


@app.post("/customers/add")
async def add_customer(name: str = Form(...), description: str = Form(""), image: UploadFile = File(None)):
    image_path = None
    if image and image.filename:
        safe_filename = f"{Path(image.filename).stem[:50]}{Path(image.filename).suffix}"
        image_path = f"images/{safe_filename}"
        file_path = STATIC_DIR / image_path
        with open(file_path, "wb") as f:
            shutil.copyfileobj(image.file, f)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO customers (name, image, description) VALUES (?, ?, ?)",
                   (name, image_path, description))
    conn.commit()
    conn.close()

    return RedirectResponse(url="/customers", status_code=303)


@app.get("/health")
def health():
    return get_db_status()