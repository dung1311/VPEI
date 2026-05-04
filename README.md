# VPEI Setup

## 1. Python environment
- Recommended: Python 3.11
- Compatible: Python 3.10+ (project has fallback for `StrEnum`)

```bash
conda create -n thesis python=3.11 -y
conda activate thesis
pip install -r requirements.txt
```

## 2. Database migration (team-safe)

### Option A (recommended)
Run app entrypoint once, it will auto-init and auto-migrate missing columns/indexes:

```bash
python run.py
```

### Option B (manual SQL)
For shared DB rollout, run SQL migration directly:

```bash
sqlite3 vpei.db < migrations/20260504_ship_voyages.sql
```

## 3. Run server
```bash
python run.py
```