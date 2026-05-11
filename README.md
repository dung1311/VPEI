# VPEI Setup

## 1. Python environment
- Recommended: Python 3.11
```bash
conda create -n vpei python=3.11 -y
conda activate vpei
pip install -r requirements.txt
```
## 2. Run server
```bash
python run.py #or docker compose up -d --build
```
