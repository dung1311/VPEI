from core.database import SessionLocal
from services import scope1 as scope1_services

db = SessionLocal()
devices = scope1_services.DeviceService.get_all(db)
activities = scope1_services.ActivityDataService.get_by_record_time(db, 2026, [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12])

print(f"Devices: {len(devices)}")
print(f"Activities: {len(activities)}")
