# services/ship_service.py
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from models.ship import Ship
from schemas.ship import ShipCreate, ShipUpdate
import services.emission_ship as compute

def calculate_ship_co2(ship: Ship) -> float:
    """
    Tính toán tổng phát thải CO2 cho một Tàu biển (đơn vị: Tấn).
    Sử dụng các công thức từ module services.emission_ship.
    """
    try:
        # 1. Ép kiểu an toàn tất cả các biến đầu vào
        v_trip = float(ship.v_trip)
        v_maneuver = float(ship.v_maneuver)
        v_max = float(ship.v_max)
        time_in_port = float(ship.time_in_port)
        buoy = int(ship.buoy)
        p_main = float(ship.P_main)
        p_aux = float(ship.P_aux)
        year_built = int(ship.year_built)
        rpm = float(ship.rpm)
        is_man = bool(ship.is_man)

        ship_type_str = ship.ship_type.value if hasattr(ship.ship_type, 'value') else str(ship.ship_type)
        valve_type_str = ship.valve_type.value if hasattr(ship.valve_type, 'value') else str(ship.valve_type)

        # 2. Phân rã thời gian
        val_trip = compute.compute_A(v_trip, buoy=buoy, status='trip')
        val_maneuver = compute.compute_A(v_maneuver, buoy=buoy, status='maneuver')
        
        t_trip = float(val_trip) if val_trip is not None else 0.0
        t_maneuver = float(val_maneuver) if val_maneuver is not None else 0.0
        t_anchor = max(time_in_port - t_trip - t_maneuver, 0.0)

        # 3. Tính hệ số tải (Load Factor)
        lf_m_t = compute.compute_lf(v_trip, v_max, engine='main', type=ship_type_str, status='trip')
        lf_m_m = compute.compute_lf(v_maneuver, v_max, engine='main', type=ship_type_str, status='maneuver')
        lf_a_t = compute.compute_lf(v_trip, v_max, engine='auxiliary', type=ship_type_str, status='trip')
        lf_a_m = compute.compute_lf(v_maneuver, v_max, engine='auxiliary', type=ship_type_str, status='maneuver')
        lf_a_a = compute.compute_lf(0, v_max, engine='auxiliary', type=ship_type_str, status='mooring')

        # 4. Lấy Hệ số phát thải (Real EF)
        pollutants = ['CO2']
        kw_main = {'year': year_built, 'rpm': rpm, 'valve_type': valve_type_str}
        kw_aux = {'year': year_built, 'rpm': rpm}

        if is_man:
            ef_m_t_r = compute.compute_real_ef_man(pollutants, lf=lf_m_t, engine='main', **kw_main)
            ef_m_m_r = compute.compute_real_ef_man(pollutants, lf=lf_m_m, engine='main', **kw_main)
        else:
            ef_m_t_r = compute.compute_real_ef_non_man(pollutants, lf=lf_m_t, engine='main', **kw_main)
            ef_m_m_r = compute.compute_real_ef_non_man(pollutants, lf=lf_m_m, engine='main', **kw_main)
        
        ef_a_t_r = compute.compute_real_ef_non_man(pollutants, lf=lf_a_t, engine='auxiliary', **kw_aux)
        ef_a_m_r = compute.compute_real_ef_non_man(pollutants, lf=lf_a_m, engine='auxiliary', **kw_aux)
        ef_a_a_r = compute.compute_real_ef_non_man(pollutants, lf=lf_a_a, engine='auxiliary', **kw_aux)

        # 5. Tính tổng CO2
        e1 = p_main * t_trip * lf_m_t * ef_m_t_r.get('CO2', 0.0)
        e2 = p_main * t_maneuver * lf_m_m * ef_m_m_r.get('CO2', 0.0)
        e3 = p_aux * t_trip * lf_a_t * ef_a_t_r.get('CO2', 0.0)
        e4 = p_aux * t_maneuver * lf_a_m * ef_a_m_r.get('CO2', 0.0)
        e5 = p_aux * t_anchor * lf_a_a * ef_a_a_r.get('CO2', 0.0)

        total_co2_grams = e1 + e2 + e3 + e4 + e5
        total_tons = total_co2_grams / 1_000_000.0
        
        return total_tons

    except Exception as e:
        # Giữ lại một dòng in lỗi cơ bản cho server log
        print(f"Error calculating Ship CO2: {str(e)}")
        return 0.0


def create_ship(ship_data: ShipCreate, db: Session, actor: str = "system"):
    """Tạo mới một tàu biển"""
    ship_dict = ship_data.model_dump()
    
    # Tính time_in_port từ start_time và end_time để chuẩn hóa
    delta = ship_data.end_time - ship_data.start_time
    time_in_port = delta.total_seconds() / 3600.0
    if time_in_port < 0:
        raise HTTPException(status_code=400, detail="Thời gian rời cảng phải sau thời gian vào cảng")
    
    ship_dict["time_in_port"] = time_in_port
    
    new_ship = Ship(**ship_dict)
    db.add(new_ship)
    db.commit()
    db.refresh(new_ship)
    
    # Gán giá trị tính toán động
    new_ship.total_co2 = calculate_ship_co2(new_ship)
    
    try:
        from services.ship_activity_service import record_ship_activity
        record_ship_activity(db, actor, "Thêm mới tàu", f"Đã thêm tàu {new_ship.name}")
    except ImportError:
        pass
        
    return new_ship


def get_all_ships(db: Session):
    """Lấy danh sách toàn bộ tàu biển và tự động tính toán phát thải"""
    ships = db.query(Ship).order_by(Ship.id.desc()).all()
    for s in ships:
        s.total_co2 = calculate_ship_co2(s)
    return ships


def get_ship_by_id(ship_id: int, db: Session):
    """Lấy chi tiết một tàu biển theo ID"""
    ship = db.query(Ship).filter(Ship.id == ship_id).first()
    if not ship:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ship not found")
    
    ship.total_co2 = calculate_ship_co2(ship)
    return ship


def update_ship(ship_id: int, ship_data: ShipUpdate, db: Session, actor: str = "system"):
    """Cập nhật thông tin tàu biển"""
    ship = db.query(Ship).filter(Ship.id == ship_id).first()
    if not ship:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ship not found")
    
    update_dict = ship_data.model_dump(exclude_unset=True)
    
    # Tính lại time_in_port nếu user sửa ngày giờ
    start = update_dict.get('start_time', ship.start_time)
    end = update_dict.get('end_time', ship.end_time)
    if start and end:
        delta = end - start
        update_dict['time_in_port'] = delta.total_seconds() / 3600.0

    for key, value in update_dict.items():
        setattr(ship, key, value)
        
    db.commit()
    db.refresh(ship)
    
    ship.total_co2 = calculate_ship_co2(ship)
    
    try:
        from services.ship_activity_service import record_ship_activity
        record_ship_activity(db, actor, "Cập nhật tàu", f"Đã sửa dữ liệu tàu {ship.name}")
    except ImportError:
        pass
        
    return ship


def delete_ship(ship_id: int, db: Session, actor: str = "system"):
    """Xóa một tàu biển khỏi hệ thống"""
    ship = db.query(Ship).filter(Ship.id == ship_id).first()
    if not ship:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ship not found")
    
    name = ship.name
    db.delete(ship)
    db.commit()
    
    try:
        from services.ship_activity_service import record_ship_activity
        record_ship_activity(db, actor, "Xóa tàu", f"Đã xóa tàu {name}")
    except ImportError:
        pass
        
    return {"message": "Ship deleted successfully", "id": ship_id}