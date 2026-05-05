# VPEI Setup

## 1. Python environment
- Recommended: Python 3.11
- Compatible: Python 3.10+ (project has fallback for `StrEnum`)

```bash
conda create -n thesis python=3.11 -y
conda activate thesis
pip install -r requirements.txt
```
## 2. Run server
```bash
python run.py or docker-compose up -d --build
```
