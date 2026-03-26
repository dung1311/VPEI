# services/scope1.py
from schemas.device import  ActivityDataEntry, DeviceCreate, DeviceDisplay

# Helper format số
def fmt(value) -> str:
    try:
        return f"{int(value):,}"
    except (ValueError, TypeError):
        return str(value)

# TODO: Đổi thành query DB thay vì mảng tĩnh sau khi nối DB thành công
SAMPLE_DEVICES = [
    {"id": "RS-01", "fuel_type": "Dầu DO", "consumption": 145000, "co2e": 1285, "percentage": 12.08},
    {"id": "RS-02", "fuel_type": "Dầu DO", "consumption": 145000, "co2e":  285, "percentage": 10.00},
    {"id": "RS-03", "fuel_type": "Dầu FO", "consumption":  85000, "co2e":  285, "percentage":  9.83},
    {"id": "RS-01", "fuel_type": "Dầu DO", "consumption": 145000, "co2e": 1285, "percentage": 12.08},
    {"id": "RS-02", "fuel_type": "Dầu DO", "consumption": 145000, "co2e":  285, "percentage": 10.00},
    {"id": "RS-03", "fuel_type": "Dầu FO", "consumption":  85000, "co2e":  285, "percentage":  9.83},
    {"id": "RS-04", "fuel_type": "Dầu DO", "consumption":  72000, "co2e":  242, "percentage":  8.45},
    {"id": "RS-05", "fuel_type": "Dầu DO", "consumption":  58000, "co2e":  196, "percentage":  7.20},
    {"id": "RS-06", "fuel_type": "Dầu DO", "consumption":  48000, "co2e":  162, "percentage":  5.90},
    {"id": "RS-07", "fuel_type": "Dầu DO", "consumption":  42000, "co2e":  141, "percentage":  5.10},
    {"id": "RS-08", "fuel_type": "Dầu DO", "consumption":  30000, "co2e":   98, "percentage":  3.62},
]

class Scope1Service:
    @staticmethod
    def get_dashboard_data(year: int, month: int):
        """Lấy và tính toán toàn bộ KPI cho màn hình Dashboard"""
        raw_devices = SAMPLE_DEVICES # Thay bằng db.query() sau
        
        total_fuel = sum(d["consumption"] for d in raw_devices)
        total_co2e = sum(d["co2e"]        for d in raw_devices)
        top_device = max(raw_devices, key=lambda d: d["co2e"]) if raw_devices else {}

        devices_fmt = [
            {
                "id":          d["id"],
                "fuel_type":   d["fuel_type"],
                "consumption": fmt(d["consumption"]),
                "co2e":        fmt(d["co2e"]),
                "percentage":  d["percentage"],
            }
            for d in raw_devices
        ]

        return {
            "total_fuel": fmt(total_fuel),
            "total_co2e": fmt(total_co2e),
            "top_device_name": top_device.get("id", "-"),
            "top_device_co2e": fmt(top_device.get("co2e", 0)),
            "change_percent": 6.5,
            "change_is_increase": True,
            "devices": devices_fmt,
            "raw_devices": raw_devices
        }

    @staticmethod
    def calculate_emission(data: ActivityDataEntry) -> float:
        """Logic tính toán phát thải (giả lập hệ số DO)"""
        ef_co2, ef_ch4, ef_n2o = 2.68, 0.005, 0.005
        gwp_ch4, gwp_n2o = 28, 265
        
        co2 = data.fuel_quantity * ef_co2
        ch4 = data.fuel_quantity * ef_ch4 * gwp_ch4
        n2o = data.fuel_quantity * ef_n2o * gwp_n2o
        
        return (co2 + ch4 + n2o) / 1000  # Quy đổi ra tCO2e