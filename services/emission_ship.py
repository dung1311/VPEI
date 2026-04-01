#services/emission_ship.py
import pandas as pd

def compute_lf(v_actual, v_max, engine='main', type='container', status='trip'):
    """
    Compute the load factor (LF) of an aircraft.

    Parameters:
    v_actual (float): Actual airspeed of the aircraft.
    v_max (float): Maximum airspeed of the aircraft.
    engine (str): Type of engine ('main' or 'auxiliary').
    type (str): Type of aircraft (e.g., 'container', 'bulk_carrier').
    status (str): Operational status ('trip' or 'maneuver').

    Returns:
    float: Load factor (LF).
    """

    if engine == 'main':
        lf = (v_actual / v_max) ** 3
        return lf
    elif engine == 'auxiliary':
        try:
            lf_table = pd.read_csv('static/LF_auxiliary.csv')
            
            row = lf_table[lf_table['ship'] == type]
            
            if row.empty:
                print(f"Warning: Can not find ship type '{type}'. Default LF=0.5 will be used.")
                return 0.5
            
            if status in row.columns:
                lf = row[status].values[0]
                return float(lf)
            else:
                raise ValueError(f"Status '{status}' is invalid (only accept: trip, maneuver, mooring)")
                
        except FileNotFoundError:
            raise FileNotFoundError("File 'LF_auxiliary.csv' not found")
            
    else:
        raise ValueError("Engine must be 'main' or 'auxiliary'")

def compute_ef_base(pollutants, engine='main', engine_speed='SSD', year=2020, tier=0, rpm=150):
    """
    Compute the Base Emission Factor (EF_base) for a list of pollutants.

    Parameters:
    pollutants (list): List of pollutant types (e.g., ['NOx', 'CO2']).
    engine (str): Type of engine ('main' or 'auxiliary').
    engine_speed (str): Speed category for main engines ('SSD', 'MSD', 'HSD').
    year (int): Year of the ship's construction.
    tier (int): Tier standard of the engine (0, 1, 2, 3).
    rpm (int): Revolutions per minute of the engine.

    Returns:
    dict: A dictionary mapping each pollutant to its Base Emission Factor (g/kWh).
    """


    match year:
        case year if year < 2000:
            tier = 0    
        case year if 2000 <= year < 2009:
            tier = 1
        case year if 2009 <= year < 2016:
            tier = 2
        case year if year >= 2016:
            tier = 3
        case _:
            raise ValueError("Year is invalid")

    match rpm:
        case rpm if rpm < 130:
            engine_speed = 'SSD'
        case rpm if 130 <= rpm < 2000:
            engine_speed = 'MSD'
        case rpm if rpm >= 2000:    
            engine_speed = 'HSD'
        case _:
            raise ValueError("RPM is invalid")


    try:
        ef_table = pd.read_csv('static/EF_base.csv')
    except FileNotFoundError:
        raise FileNotFoundError("File 'EF_base.csv' not found")

    results = {}


    for pollutant in pollutants:

        row = ef_table[(ef_table['exhaust'] == pollutant) & (ef_table['Tier'] == tier)]

        if row.empty:
            print(f"Warning: Configuration for pollutant '{pollutant}' at Tier {tier} not found. Returning 0.0.")
            results[pollutant] = 0.0
            continue

        ef_value = 0.0

        if engine == 'main':
            if engine_speed == 'SSD':

                ef_value = row['main (SSD)'].values[0]
            elif engine_speed == 'MSD':

                ef_value = row['main(MSD)'].values[0]
            elif engine_speed == 'HSD':
               
                ef_value = row['main(HSD)'].values[0]
            else:
                raise ValueError(f"Engine speed '{engine_speed}' is invalid (only accept: SSD, MSD)")
        
        elif engine == 'auxiliary':
            ef_value = row['auxiliary'].values[0]
            
        else:
            raise ValueError("Engine must be 'main' or 'auxiliary'")
        
        results[pollutant] = float(ef_value)

    return results

import pandas as pd
import numpy as np

def compute_lla(pollutants, lf):
    """
    Tính hệ số điều chỉnh tải thấp (Low Load Adjustment - LLA) cho động cơ Non-MAN.
    
    Parameters:
    pollutants (list): Danh sách các chất ô nhiễm (ví dụ: ['NOx', 'HC']).
    lf (float): Hệ số tải thực tế (0.0 - 1.0).
    
    Returns:
    dict: Dictionary chứa hệ số LLA cho từng chất ô nhiễm.
    """
    try:
        lla_table = pd.read_csv('static/LLA_non_man.csv')
    except FileNotFoundError:
        print("Error: File 'LLA_non_man.csv' not found.")
        return {p: 1.0 for p in pollutants}

    # 2. Xử lý ép kiểu cột Load mạnh tay sang float
    lla_table['Load'] = lla_table['Load'].astype(str).str.replace('%', '', regex=False).astype(float)
        
    results = {}
    


    current_load_percent = lf * 100
    max_table_load = lla_table['Load'].max() 

    for pollutant in pollutants:
    
        col_name = pollutant

        if col_name not in lla_table.columns:
            print(f"Warning: Pollutant '{pollutant}' (mapped to '{col_name}') not found in LLA columns. Returning 1.0.")
            results[pollutant] = 1.0
            continue

        if current_load_percent > max_table_load:
            results[pollutant] = 1.0
        else:
            nearest_idx = (lla_table['Load'] - current_load_percent).abs().idxmin()
            
            val = lla_table.loc[nearest_idx, col_name]
            results[pollutant] = float(val)

    return results


import pandas as pd

def compute_efa_non_man(pollutants, valve_type='C3'):
    """
    Compute Emission Factor Adjustment (EFA) for Non-MAN engines.
    
    Based on Formula: Adjusted EF = EF_base * EFA
    This function returns the EFA component from Table 4.

    Parameters:
    pollutants (list): List of pollutant types (e.g., ['NOx', 'CO', 'HC']).
    valve_type (str): Type of valve configuration. 
                      'SV' (Slide Valve) or 'C3' (No Slide Valve / Conventional).
                      Default is 'C3'.

    Returns:
    dict: Dictionary mapping pollutants to their EFA values.
    """
    
    # 1. Load the lookup table
    try:
        df = pd.read_csv('static/EFA_non_man.csv')
    except FileNotFoundError:
        raise FileNotFoundError("File 'EFA_non_man.csv' not found")

    # 2. Validate valve_type (Column selection)
    if valve_type not in ['SV', 'C3']:
        raise ValueError(f"Valve type '{valve_type}' is invalid. Use 'SV' (Slide Valve) or 'C3' (No Slide Valve).")

    # 3. Column mapping (User input -> CSV Pollutant name)
    # Mapping HC to VOC, and PM10/PM2.5 to generic PM as per Table 4

    results = {}

    for p in pollutants:
        # Map input name to table name
        table_name = p
        
        # Filter row by Pollutant name
        row = df[df['Pollutant'] == table_name]
        
        if row.empty:
            print(f"Warning: Pollutant '{p}' (mapped to '{table_name}') not found in EFA table. Returning 1.0.")
            results[p] = 1.0
        else:
            # Get value from the specific column (SV or C3)
            val = row[valve_type].values[0]
            results[p] = float(val)

    return results

def compute_real_ef_non_man(pollutants, lf, engine='main', year=2010, rpm=100, valve_type='C3'):
    """
    Compute the Real Emission Factor (EF) for Non-MAN engines.
    Formula: EF = EF_base * EFA * LLA (Low Load Adjustment)
    """
    # print(engine)
    base_efs = compute_ef_base(pollutants, engine='main', year=year, rpm=rpm)
    
    if lf > 0.2 or engine=='auxiliary':
        real_ef = compute_ef_base(pollutants, engine=engine, year=year, rpm=rpm)
        return real_ef

    efas = compute_efa_non_man(pollutants, valve_type=valve_type)
    

    llas = compute_lla(pollutants, lf)
    
    final_ef = {}

    for p in pollutants:
        b = base_efs.get(p, 0.0)
        e = efas.get(p, 1.0)
        l = llas.get(p, 1.0)

        real = b * e * l
        final_ef[p] = real
        
    return final_ef
def compute_laf_man(pollutants, lf, valve_type='C3'):
    """
    Tính hệ số điều chỉnh tải (LAF) cho động cơ MAN.
    Động cơ MAN thường có bảng tra chi tiết từ 1% - 100% tải.

    Parameters:
    pollutants (list): Danh sách chất ô nhiễm.
    lf (float): Hệ số tải (0.0 - 1.0).
    valve_type (str): Loại cấu hình MAN ('C3' hoặc 'SV').

    Returns:
    dict: Dictionary chứa LAF cho từng chất.
    """
    
    # 1. Xác định file dữ liệu dựa trên loại MAN
    if valve_type == 'C3':
        filename = 'static/LAF_MAN_C3.csv'
    elif valve_type == 'SV':
        filename = 'static/LAF_MAN_SV.csv'
    else:
        raise ValueError("Loại MAN không hợp lệ. Chỉ chấp nhận 'C3' hoặc 'SV'.")

    try:
        df = pd.read_csv(filename)
    except FileNotFoundError:
        raise FileNotFoundError(f"Không tìm thấy file '{filename}'")

    # 2. Xử lý cột Load
    # 2. Xử lý ép kiểu cột Load mạnh tay sang float
    df['Load'] = df['Load'].astype(str).str.replace('%', '', regex=False).astype(float)

    current_load_percent = lf * 100
    
    results = {}

    for p in pollutants:
        # Lấy tên cột chuẩn trong CSV
        target_col = p

        if target_col not in df.columns:
            print(f"Warning: Pollutant '{p}' (mapped to '{target_col}') not found in {valve_type} table. Returning 1.0")
            results[p] = 1.0
            continue

        # 4. Tìm giá trị LAF tại mức tải gần nhất (Nearest Interpolation)
        # Vì bảng MAN rất chi tiết (từng 1%), việc lấy nearest là đủ chính xác
        idx = (df['Load'] - current_load_percent).abs().idxmin()
        val = df.loc[idx, target_col]
        results[p] = float(val)

    return results

def compute_real_ef_man(pollutants, lf, engine='main', year=2010, rpm=100, valve_type='C3'):
    """
    Tính toán EF thực tế cho động cơ MAN.
    Công thức: EF = EF_base * LAF
    (Động cơ MAN thường tích hợp các điều chỉnh khác vào thẳng bảng LAF)
    """
    base_efs = compute_ef_base(pollutants, engine=engine, year=year, rpm=rpm)
    
    lafs = compute_laf_man(pollutants, lf, valve_type=valve_type)
    
    final_ef = {}
    
    
    for p in pollutants:
        b = base_efs.get(p, 0.0)
        l = lafs.get(p, 1.0)
        
        real = b * l
        final_ef[p] = real
        
    return final_ef

def compute_A(v_actual, buoy = 0, status='trip'):
    s_table = pd.read_csv('static/buoy.csv')
    row = s_table[s_table['buoy'] == buoy]
    if row.empty:
        print(f"Warning: Can not find buoy '{buoy}'. Default A=0.85 will be used.")
        return None
    
    S = row[status].values[0]
    A = 2* (S / v_actual )
    return float(A)

def compute_E(pollutants, v_actual, v_max, P, engine='main', type='container', status='trip', buoy=0, is_man=True, valve_type='C3', rpm=100, year=2010):
    lf = compute_lf(v_actual, v_max, engine=engine, type=type, status=status)

    A = compute_A(v_actual, buoy=buoy, status=status)
    if is_man:
        ef_man = compute_real_ef_man(pollutants, lf = lf, engine=engine, valve_type=valve_type, rpm=rpm, year=year)
        E = {}
        for p in pollutants:
            E[p] = lf * A * P * ef_man[p]
        return E
    else:
        ef_non_man = compute_real_ef_non_man(pollutants, engine=engine, lf=lf, valve_type=valve_type, rpm=rpm, year=year)
        E = {}
        for p in pollutants:
            E[p] = lf * A * P * ef_non_man[p]
        return E


if __name__ == "__main__":
    print(compute_lf(10, 20, engine='auxiliary', type='container', status='trip'))

