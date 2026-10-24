# Oscorp Capstone — Jiran Inventory Intelligence
# Jiran — AI-Assisted Inventory Optimization & Retailer Marketplace

> **Recovery status — 24 October 2026:** the original hosted Supabase hostname no longer resolves, so its historical rows could not be recovered. This repository now includes a local Supabase schema and a source-neutral ERP/CSV import path. AI data, evaluation metrics, and prediction claims remain explicitly `null` until a traceable dataset is supplied and evaluated. See [`data/data-status.json`](data/data-status.json), the [recovery decision](research/open-source-recovery-options.md), and the [ISDIA working draft](paper/ISDIA-paper-working-draft.md).

Jiran is a centralized, web-based platform designed for small and mid-sized retailers to manage inventory more effectively, reduce stock imbalances, and make better operational decisions using analytics and AI-assisted forecasting. The platform brings together inventory tracking, demand insights, alerts, and a retailer-to-retailer marketplace in one system.

Developed as a university capstone project by **Team OSCORP**, Jiran focuses on improving inventory visibility, enabling data-driven stock movement, and supporting retailers that often rely on disconnected tools such as spreadsheets, POS systems, and manual records.

---

## Product Overview

Many retailers operate with fragmented systems for stock monitoring, sales tracking, and replenishment planning. Jiran addresses this challenge by providing a single platform where retailers can:

- manage inventory across stores and locations,
- import or synchronize stock and sales data,
- monitor stock health and receive low-stock alerts,
- analyze sales and demand trends,
- identify slow-moving or dead stock, and
- redistribute excess inventory through a built-in marketplace.

The goal of Jiran is to reduce overstocking and stockouts, improve stock visibility, and help retailers make smarter operational decisions using AI-assisted insights.

---

## Key Features

- **Centralized Inventory Management** for adding, updating, importing, and monitoring stock.
- **AI-Assisted Analytics** for stock classification, demand forecasting, and recommendations.
- **Marketplace / Stock Exchange** for listing excess inventory and requesting stock from other retailers.
- **Low-Stock and Critical-Stock Alerts** to improve operational responsiveness.
- **POS and File Import Support** for integrating data from existing systems.
- **Retailer Dashboard** for operational insights, inventory summaries, and analytics views.

---

## Target Users

Jiran is designed primarily for:

- small and medium-sized retailers,
- businesses operating across multiple locations,
- retailers using systems such as spreadsheets and POS platforms, and
- stores that need better visibility into stock movement and excess inventory.

---

## Tech Stack

### Frontend

- **React + Vite**

### Backend / ML Service

- **Python + FastAPI**

### Database / Authentication / Realtime

- **Supabase** (PostgreSQL + Authentication + Realtime)

### Machine Learning

- **Prophet**
- **XGBoost**
- **Gradient Boosting**
- **Random Forest**

---

## Recovered local development path

The least-disruptive open-source recovery keeps the application's existing Supabase API contract:

```bash
# Docker Desktop must be running
npx supabase start
python3 scripts/configure_local_supabase.py

# frontend
cd frontend
npm ci
npm run dev
```

Local Supabase applies `supabase/migrations/202610240001_local_recovery.sql`. Generated credentials are written only to ignored owner-only local environment files. Do not commit them.

For factual ERP inventory ingestion without Square:

```bash
python3 tools/resource_import.py --source erpnext --input export.csv --output data/normalized/inventory.csv
# or: --source odoo
```

The adapter does not generate AI predictions. The Python ML service is a separate legacy component and should be treated as unverified until a traceable dataset and evaluation are restored.

The recovery and paper dashboard is available by serving the repository root:

```bash
python3 -m http.server 4174
# open http://127.0.0.1:4174/dashboard/
```

---

## Prerequisites

Before running the project, ensure the following are installed:

- **Python 3.9+** — https://python.org
- **Node.js 18+** — https://nodejs.org

---

## Getting Started

### 1. Clone the repository

```bash
git clone https://github.com/harklook/Jiran.git
cd Jiran
```

### 2. Start the project

```bash
./start.sh
```

The startup script will:

- install Python and Node dependencies on first run,
- start the ML backend on **http://localhost:8001**, and
- start the frontend on **http://localhost:5173**.

Press `Ctrl+C` to stop both services.

> **Important:** The application must be running on **http://localhost:5173** for users to access and test the system.

---

## Test Access & Demo Data

Jiran can be tested using either an existing account or a newly created account.

Create a new local account after starting the self-hosted Supabase stack. Historical hosted demo credentials have been removed and must not be reused.

Alternatively, users can create a new account through the application's sign-up flow and use it to test the platform features.

---

## Testing Inventory and Orders Import

To test the manual import functionality, two sample CSV files are provided:

- **Inventory CSV** — contains **85 items**
- **Orders CSV** — contains **702 orders**

These files can be used to test:

- manual inventory import,
- order import,
- stock updates,
- analytics generation, and
- forecasting-related workflows.

---

## Testing Square Integration

Users can also test the Square integration using the provided demo credentials:

```text
Email: yaasirwheelie2024@gmail.com
Password: -:5UyfdBeJb!@P9
```

> **Note:** The Square demo account currently contains:
>
> - **2 items**
> - **0 orders**

This option is useful for testing the integration flow, but the available dataset is limited compared to the provided CSV files.

---

## Recommended Testing Flow

For the most complete testing experience:

1. Start the application using `./start.sh`
2. Open the frontend at **http://localhost:5173**
3. Log in using the demo account **or** create a new account
4. Import the provided CSV files to populate inventory and order data
5. Explore the following features:
   - inventory management,
   - stock alerts,
   - analytics dashboards,
   - AI-assisted recommendations, and
   - marketplace workflows

---

## Project Structure

```text
Jiran/
├── start.sh
├── README.md
├── frontend/                  # React + Vite frontend (port 5173)
│   ├── src/
│   ├── package.json
│   └── .env
└── ml_backend/                # FastAPI ML service (port 8001)
    ├── app.py
    ├── supabase_watcher.py
    ├── train.py
    ├── saved_models/
    ├── requirements.txt
    └── .env
```

---

## Core Workflows

Jiran supports the following business workflows:

1. **Authentication and onboarding** using secure retailer accounts.
2. **Inventory management** through manual updates, file imports, or POS synchronization.
3. **Stock monitoring** with low-stock, excess-stock, slow-moving, and dead-stock visibility.
4. **Demand forecasting** using historical sales and inventory data.
5. **Marketplace exchange** where retailers can list surplus stock and request needed inventory.
6. **Notifications and alerts** for stock issues and operational updates.

---

## ML API Reference

**Base URL:** `http://localhost:8001`  
**Interactive Docs:** `http://localhost:8001/docs`

### Endpoints

- `GET /` — Health check
- `POST /predict-stock` — Predict stock status for products
- `POST /recommend` — Generate predictions and transfer/restock recommendations
- `GET /feature-importance` — Return top model features

---

## Stock Labels

### Low

**Meaning:** Running low  
**Suggested Action:** Receive transfers or restock

### Optimum

**Meaning:** Healthy stock level  
**Suggested Action:** No action needed

### Excess

**Meaning:** Overstocked  
**Suggested Action:** Move stock to stores with lower availability

### Slow

**Meaning:** Slow-moving  
**Suggested Action:** Transfer to higher-demand stores

### Dead

**Meaning:** No recent sales  
**Suggested Action:** Clear or redistribute surplus stock

---

## Data and Integration Notes

Jiran supports both manual inventory imports and POS integration workflows. The AI-assisted features rely on structured historical sales and inventory records to generate useful predictions, stock classifications, and recommendations.

---

## Troubleshooting

### ML models missing

```bash
cd ml_backend && python3 train.py
```

### Port already in use

```bash
lsof -ti:8001 | xargs kill -9
lsof -ti:5173 | xargs kill -9
```

### `npm install` fails (macOS)

```bash
xattr -cr frontend/
rm -rf frontend/node_modules
cd frontend && npm install
```

---

## Notes

- Jiran is an **academic capstone project** focused on inventory optimization, forecasting, and retailer collaboration.
- The current scope emphasizes **inventory operations**, **AI-assisted recommendations**, and **stock exchange workflows**, rather than full ERP replacement.

---

## License / Usage Notice

This project is presented as an academic and demonstration system. If you plan to reuse, modify, or distribute it, ensure the repository owner’s licensing terms and permissions are followed.
