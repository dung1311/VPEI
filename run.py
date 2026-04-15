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
    try:
        uvicorn.run("main:app", host="127.0.0.1", port=8000)
    except KeyboardInterrupt:
        print("Đã đóng web")
