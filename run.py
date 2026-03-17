"""
Entry point.
  python run.py
"""
from core.database import init_db
import uvicorn

if __name__ == "__main__":
    print("🔧 Initialising database …")
    init_db()
    print("🚀 Starting VPEI on http://0.0.0.0:8000")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)