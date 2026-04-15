import os
import sys

# Thêm đường dẫn app vào sys.path để có thể import
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy.orm import Session
from sqlalchemy import text
from core.database import engine, SessionLocal
from models.ship import Ship
from services.ship_service import calculate_ship_co2

def backfill():
    # 1. Thêm cột total_co2
    with engine.connect() as conn:
        try:
            conn.execute(text('ALTER TABLE ships ADD COLUMN total_co2 FLOAT DEFAULT 0.0;'))
            conn.commit()
            print("Đã thêm cột total_co2.")
        except Exception as e:
            if "duplicate column name" in str(e).lower() or "already exists" in str(e).lower():
                print("Cột total_co2 đã tồn tại.")
            else:
                print("Lỗi khi thêm cột:", e)

    # 2. Backfill dữ liệu
    db: Session = SessionLocal()
    try:
        ships = db.query(Ship).all()
        count = 0
        for ship in ships:
            # Luôn tính lại cho chắc chắn nếu chênh lệch (hoặc 0.0)
            new_val = calculate_ship_co2(ship)
            # if ship.total_co2 != new_val:  # Cannot safely check float equality
            ship.total_co2 = new_val
            count += 1
        db.commit()
        print(f"Thành công: Đã backfill total_co2 cho {count} tàu.")
    except Exception as e:
        print(f"Lỗi: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    backfill()
