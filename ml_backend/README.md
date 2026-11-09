# Jiran — Inventory Intelligence System

> **Real-data bridge:** see [JIRAN_ML_INTEGRATION.md](JIRAN_ML_INTEGRATION.md)
> for importing the private `jiran-ml` Square exports, retraining local model
> artifacts, and connecting the Supabase watcher.

Jiran is a capstone project that combines a React frontend with a Python ML backend to predict stock status and generate transfer/restock recommendations across multiple store locations.

---

## Project Structure

```
cap1/
├── MLLLL-copy/                  ← ML Backend (this repo)
│   ├── app.py                   ← FastAPI server (port 8001)
│   ├── supabase_watcher.py      ← Background Supabase trigger watcher
│   ├── train.py                 ← Model training script
│   ├── predictor.py             ← Prediction utilities
│   ├── saved_models/            ← Pre-trained model artifacts
│   ├── requirements.txt
│   └── start.sh                 ← One-command startup script
│
└── Jiran@capstone/
    └── JiranDuplicate6/         ← React Frontend (Vite)
        ├── src/
        ├── package.json
        └── .env                 ← You must create this (see below)
```

---

## Prerequisites

| Tool | Version | Install |
|------|---------|---------|
| Python | 3.9+ | https://python.org |
| Node.js | 18+ | https://nodejs.org |
| npm | 9+ | comes with Node.js |

---

## Quick Start

### Step 1 — Clone / Download

If running on **macOS**, the `@` in the folder name can cause permission issues. Copy the frontend to a clean path:

```bash
cp -r "~/Downloads/cap1/Jiran@capstone/JiranDuplicate6" ~/Desktop/JiranDuplicate6
```

### Step 2 — Set up the Frontend

```bash
cd ~/Desktop/JiranDuplicate6

# Remove macOS quarantine flags (required on Mac)
xattr -cr .

# Create your .env file
cp .env.example .env
# then edit .env and fill in your Supabase keys

npm install
npm run dev
```

Frontend runs at **http://localhost:5173**

### Step 3 — Set up the ML Backend

```bash
cd ~/Downloads/cap1/MLLLL-copy

# Install Python dependencies
pip install -r requirements.txt

# Start the ML server + Supabase watcher
./start.sh
```

ML API runs at **http://localhost:8001**

> Models are pre-trained. If `saved_models/` is missing or you need to retrain:
> ```bash
> python3 train.py
> ```

---

## Environment Variables

### Frontend (`~/Desktop/JiranDuplicate6/.env`)

```env
VITE_SUPABASE_URL=https://your-project.supabase.co
VITE_SUPABASE_ANON_KEY=your_anon_key_here
VITE_ML_API_URL=http://localhost:8001
```

### ML Backend (optional — defaults are already set in code)

```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your_service_role_key_here
ML_API_URL=http://localhost:8001
OUTPUT_DIR=./ml_outputs
POLL_INTERVAL=10
```

---

## ML API Endpoints

Base URL: `http://localhost:8001`

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | Health check |
| `POST` | `/predict-stock` | Predict stock status for a list of products |
| `POST` | `/recommend` | Predictions + transfer & restock recommendations |
| `GET` | `/feature-importance` | Top features from the trained model |

### Stock Status Labels

| Label | Meaning |
|-------|---------|
| `Low` | Running low — needs restocking or transfer |
| `Optimum` | Healthy stock level |
| `Excess` | Overstocked — can donate to Low stores |
| `Slow` | Moving slowly — candidate for transfer |
| `Dead` | No sales activity — surplus stock available |

### Example `/predict-stock` request

```json
{
  "products": [
    {
      "store_id": "store_1",
      "product_id": "prod_42",
      "category": "dairy",
      "stock_qty": 15,
      "retail_price": 3.50,
      "recent_qty": 40,
      "recent_txns": 12
    }
  ]
}
```

---

## Supabase Watcher

The watcher polls the `ml_triggers` table every 10 seconds. To trigger a prediction run from the Supabase SQL editor:

```sql
INSERT INTO ml_triggers (status, trigger_type)
VALUES ('pending', 'recommend');
```

Results are written to `./ml_outputs/` as CSV and JSON files.

### Required Supabase Tables

**`ml_triggers`**
```sql
CREATE TABLE ml_triggers (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  status       text,           -- 'pending' | 'running' | 'done' | 'error'
  trigger_type text,           -- 'recommend' | 'predict-stock'
  filter_store   text,
  filter_product text,
  created_at   timestamptz DEFAULT now(),
  completed_at timestamptz,
  error_msg    text,
  result_file  text
);
```

**`ml_inventory`** — see `supabase_watcher.py` for full column list.

---

## Troubleshooting

**`Permission denied` or `Operation not permitted` on Mac**
```bash
xattr -cr <project-folder>
chmod -R +x node_modules/.bin
```

**`Missing artifact` error on ML server start**
```bash
python3 train.py
```

**Frontend can't reach the ML API**
- Make sure the ML server is running on port 8001
- Check `VITE_ML_API_URL` in your `.env`

**`npm install` fails with EACCES**
```bash
xattr -cr .
rm -rf node_modules
npm install
```
