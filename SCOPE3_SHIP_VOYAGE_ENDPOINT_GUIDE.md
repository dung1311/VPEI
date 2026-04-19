# Scope 3 Ship Voyage API Guide (Frontend)

## 1. Muc dich
Endpoint nay dung de tinh phat thai CO2 cho mot tuyen tau nhieu cang.

Tong phat thai duoc tinh theo:
- At sea: giua 2 cang lien tiep
- In port: tai tung cang (trip + maneuver + anchor)

Cong thuc tong quat:

- E_total = E_at_sea + E_in_port

## 2. Endpoint
- Method: POST
- URL: /api/scope3/ships/voyage/calculate
- Content-Type: application/json

Vi du local:
- http://127.0.0.1:8000/api/scope3/ships/voyage/calculate

## 3. Request Body

### 3.1 Thong tin tau
- name: string, bat buoc
- ship_type: enum string, bat buoc
  - container_ship | bulk_carrier | cruiser_ship | general_cargo_ship | other_ship | roro_ship | reefer_ship | oil_tanker
- year_built: number, bat buoc
- rpm: number > 0, bat buoc
- valve_type: C3 | SV, bat buoc
- is_man: boolean, bat buoc
- buoy: number >= 0, tuy chon (default = 0)

### 3.2 Van hanh
- v_trip: number > 0, bat buoc (km/h)
- v_maneuver: number > 0, bat buoc (km/h)
- v_max: number > 0, bat buoc (km/h)
- v_sea: number > 0, tuy chon (km/h)
- P_main: number > 0, bat buoc (kW)
- P_aux: number > 0, tuy chon (kW)
  - Neu khong truyen, backend tu gan P_aux = P_main / 5
- lf_aux_at_sea: number [0..1], tuy chon (default = 0.2)
- sea_buffer_hours: number >= 0, tuy chon (default = 2)
- default_sea_speed_ratio: number > 0, <= 1.2, tuy chon (default = 0.9)
- cap_speed_by_design: boolean, tuy chon (default = true)

### 3.3 Danh sach cang
- ports: array, bat buoc, toi thieu 2 phan tu

Moi phan tu trong ports:
- port_code: string, bat buoc
- port_name: string, tuy chon
- eta: datetime ISO string, bat buoc
- etd: datetime ISO string, bat buoc (phai >= eta)
- channel_distance_km: number >= 0, tuy chon
- sea_distance_to_next_km: number >= 0, tuy chon
  - Chi dung y nghia cho cang hien tai den cang tiep theo
- latitude: number, tuy chon
- longitude: number, tuy chon

## 4. Request Example

```json
{
  "name": "Haian Beta",
  "ship_type": "container_ship",
  "year_built": 2018,
  "rpm": 120,
  "valve_type": "C3",
  "is_man": true,
  "buoy": 0,
  "v_trip": 10,
  "v_maneuver": 6,
  "v_max": 20,
  "v_sea": 18,
  "P_main": 12000,
  "P_aux": 2400,
  "lf_aux_at_sea": 0.2,
  "sea_buffer_hours": 2,
  "default_sea_speed_ratio": 0.9,
  "cap_speed_by_design": true,
  "ports": [
    {
      "port_code": "HPH",
      "port_name": "Hai Phong",
      "eta": "2025-01-20T05:00:00",
      "etd": "2025-01-22T08:00:00",
      "channel_distance_km": 15,
      "sea_distance_to_next_km": 1300,
      "latitude": 20.85,
      "longitude": 106.68
    },
    {
      "port_code": "VUT",
      "port_name": "Vung Tau",
      "eta": "2025-01-24T19:00:00",
      "etd": "2025-01-25T04:00:00",
      "channel_distance_km": 12,
      "sea_distance_to_next_km": 900,
      "latitude": 10.35,
      "longitude": 107.07
    },
    {
      "port_code": "SGN",
      "port_name": "Sai Gon",
      "eta": "2025-01-25T14:00:00",
      "etd": "2025-01-26T06:00:00",
      "channel_distance_km": 8,
      "latitude": 10.77,
      "longitude": 106.70
    }
  ]
}
```

## 5. Response Structure

Luu y: mau duoi day da rut gon mang legs/ports/points/segments de de doc.

```json
{
  "ship": {
    "name": "Haian Beta",
    "ship_type": "container_ship",
    "year_built": 2018
  },
  "summary": {
    "num_ports": 3,
    "num_legs": 2,
    "at_sea_hours": 122.2222,
    "in_port_hours": 76.0,
    "at_sea_co2_tons": 690.720492,
    "in_port_co2_tons": 38.176161,
    "total_co2_tons": 728.896653
  },
  "legs": [
    {
      "from_port": "HPH",
      "to_port": "VUT",
      "hours": 72.2222,
      "distance_km": 1300.0,
      "speed_kmh": 18.0,
      "load_factor_main": 0.729,
      "load_factor_aux": 0.2,
      "co2_grams": 409988645.0,
      "co2_tons": 409.988645,
      "from": {
        "port_code": "HPH",
        "port_name": "Hai Phong",
        "latitude": 20.85,
        "longitude": 106.68
      },
      "to": {
        "port_code": "VUT",
        "port_name": "Vung Tau",
        "latitude": 10.35,
        "longitude": 107.07
      }
    }
  ],
  "ports": [
    {
      "port_code": "HPH",
      "port_name": "Hai Phong",
      "eta": "2025-01-20T05:00:00",
      "etd": "2025-01-22T08:00:00",
      "in_port_hours": 51.0,
      "t_trip": 3.0,
      "t_maneuver": 5.0,
      "t_anchor": 43.0,
      "co2_grams": 23000000.0,
      "co2_tons": 23.0,
      "latitude": 20.85,
      "longitude": 106.68
    }
  ],
  "map_route": {
    "points": [
      {
        "port_code": "HPH",
        "port_name": "Hai Phong",
        "latitude": 20.85,
        "longitude": 106.68,
        "eta": "2025-01-20T05:00:00",
        "etd": "2025-01-22T08:00:00"
      }
    ],
    "segments": [
      {
        "from_port": "HPH",
        "to_port": "VUT",
        "coordinates": [
          { "lat": 20.85, "lng": 106.68 },
          { "lat": 10.35, "lng": 107.07 }
        ],
        "distance_km": 1300.0,
        "co2_tons": 409.988645
      }
    ]
  }
}
```

## 6. Cach dung cho Frontend

### 6.1 Goi API

```javascript
async function calculateShipVoyage(payload) {
  const res = await fetch('/api/scope3/ships/voyage/calculate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Khong tinh duoc phat thai tuyen tau');
  }

  return res.json();
}
```

### 6.2 Render KPI
- Tong KPI: summary.total_co2_tons
- Tach phan:
  - summary.at_sea_co2_tons
  - summary.in_port_co2_tons

### 6.3 Render map
- Marker cang: map_route.points
- Polyline cac chang: map_route.segments[].coordinates
- Tooltip theo chang:
  - from_port -> to_port
  - co2_tons
  - distance_km

### 6.4 Render bang chi tiet
- Bang leg: dung legs
- Bang theo cang: dung ports

## 7. Validation va loi thuong gap
- ports < 2: 400, "Voyage must include at least 2 ports"
- etd < eta trong 1 cang: 422 (Pydantic validation error)
- Truong bat buoc thieu hoac sai kieu: 422

## 8. Ghi chu tich hop
- Endpoint hien tai khong yeu cau query param.
- Neu khong truyen latitude/longitude, map_route.segments.coordinates co the rong mot phan hoac toan bo.
- Du lieu response chi bao gom CO2 (khong co SO2/PM).
