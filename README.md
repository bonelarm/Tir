# TIR - Task and Inventory Management System

A lightweight FastAPI-based task and inventory management system with a clean dark-themed UI.

## Features

- **Task Management** - Kanban-style board with custom columns, drag-and-drop support
- **Customer Management** - Store customer details, contacts, and notes
- **Inventory Tracking** - Manage items with quantities, costs, and images
- **Dashboard Infographics** - Visual charts showing task status, completion rates, and inventory overview
- **Image Uploads** - Support for task and item images
- **CSV Import/Export** - Import and export customer data via CSV
- **Search & Sort** - Filter items and customers with search and sorting options

## Tech Stack

- **Backend:** FastAPI (Python)
- **Frontend:** Jinja2 templates, vanilla JavaScript
- **Database:** SQLite
- **Styling:** Custom "Graphite" dark theme CSS
- **Charts:** Chart.js (loaded via CDN)

## Installation

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd Tir
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Initialize the database:
   ```bash
   python init_db.py
   ```

4. Run the application:
   ```bash
   python -m uvicorn main:app --reload
   ```

5. Open your browser and navigate to `http://127.0.0.1:8000`

## Project Structure

```
Tir/
├── main.py              # FastAPI application and routes
├── init_db.py          # Database initialization script
├── requirements.txt    # Python dependencies
├── tir.db              # SQLite database (created after init)
├── templates/         # Jinja2 HTML templates
│   ├── base.html
│   ├── index.html     # Dashboard with infographics
│   ├── tasks.html     # Kanban task board
│   ├── customers.html # Customer list
│   ├── customer_detail.html
│   ├── customer_edit.html
│   ├── items.html     # Inventory management
│   └── item_edit.html
├── css/
│   └── style.css      # Graphite dark theme
├── static/
│   └── images/       # Uploaded images
└── js/                # JavaScript (currently empty, using inline scripts)
```

## Database Schema

### Tables

- **customers** - id, name, image, description, email, address, website, company
- **contacts** - id, customer_id, name, phone, email
- **customer_notes** - id, customer_id, note, created_at
- **tasks** - id, title, description, completed, created_at, image, column_name, position, customer_id, item_id
- **task_columns** - id, name, position
- **task_customers** - id, task_id, customer_id (junction table)
- **task_items** - id, task_id, item_id, quantity (junction table)
- **items** - id, name, description, quantity, price, cost, created_at, image
- **status_log** - id, status, timestamp

## Usage

### Dashboard
The index page (`/`) displays:
- **Stat Cards** - Count-up animated numbers for customers, items, tasks, and completed tasks
- **Task Status Chart** - Doughnut chart showing tasks by column (with CSS bar chart fallback)
- **Completion Rate** - SVG circular progress indicator
- **Recent Activity Feed** - Latest 5 tasks with status indicators
- **Inventory Overview** - Total value and low-stock alerts

### Tasks
- Navigate to `/tasks` to access the Kanban board
- Add custom columns (e.g., "To Do", "In Progress", "Done")
- Drag and drop tasks between columns
- Link tasks to customers and items
- Upload task images

### Customers
- Add customers with contact information
- Store multiple contacts per customer
- Add notes to customer records
- Link customers to tasks
- Import/export customer data via CSV

### Items
- Track inventory with quantities and costs
- Upload item images
- Link items to tasks
- View items used in tasks
- Sort by name, quantity, or cost

## Configuration

The application uses the following default settings:
- **Database:** `tir.db` (SQLite)
- **Static files:** `static/` directory
- **Images:** `static/images/` directory
- **Host:** 127.0.0.1
- **Port:** 8000

## Development

To run in development mode with auto-reload:
```bash
python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

## License

MIT License

## Screenshots

### Dashboard
- Animated stat cards with count-up effect
- Task status doughnut chart (Chart.js)
- Completion rate circular progress
- Recent activity feed
- Inventory bar chart with low-stock alerts

### Task Board
- Kanban-style columns
- Drag-and-drop task management
- Task cards with images and linked customers/items

### Dark Theme
- Custom "Graphite" color palette
- Accent color: Indigo (#6366f1)
- Full dark mode support throughout
