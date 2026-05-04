# Scope 3 Tàu Liên Cảng API Guide (Frontend)

## 1. Purpose
This endpoint calculates route emissions for a ship across multiple ports.

Total emission model:
- E_total = E_at_sea + E_in_port

The API now returns all required pollutants:
- CO2
- SO2
- PM10
- PM2.5

## 2. Pollutant Formulas (At Sea)
The at-sea emission factors are derived from BSFC with sulfur fixed at 0.5%.

- PM10 = 0.5761 + (BSFC * 0.02247 * 7 * 0.5%)
- PM2.5 = PM10 * 0.8
- SO2 = 0.5% * BSFC * 2 * 0.97753
- CO2 = 3.114 * BSFC

BSFC rule:
- Main engine: 195 g/kWh if RPM < 130, else 215 g/kWh
- Auxiliary engine (at sea): 227 g/kWh

## 3. Endpoint
- Method: POST
- URL: /api/scope3/ships/voyage/calculate
- Content-Type: application/json
- Auth: Required (must login first to receive `access_token` cookie)

Local URL:
- http://127.0.0.1:8000/api/scope3/ships/voyage/calculate

Authentication note:
- If request has no valid login cookie, backend redirects to `/login` with HTTP `302`.

## 4. Request Body

### 4.1 Ship Info
- name: string, required
- ship_type: enum string, required
  - container_ship | bulk_carrier | cruiser_ship | general_cargo_ship | other_ship | roro_ship | reefer_ship | oil_tanker
- year_built: number, required
- rpm: number > 0, required
- valve_type: C3 | SV, required
- is_man: boolean, required
- buoy: number >= 0, optional (default = 0)

### 4.2 Operation Inputs
- v_trip: number > 0, required (km/h)
- v_maneuver: number > 0, required (km/h)
- v_max: number > 0, required (km/h)
- v_sea: number > 0, optional (km/h)
- P_main: number > 0, required (kW)
- P_aux: number > 0, optional (kW)
  - If omitted, backend sets P_aux = P_main / 5
- lf_aux_at_sea: number [0..1], optional (default = 0.729)
- sea_buffer_hours: number >= 0, optional (default = 2)
- default_sea_speed_ratio: number > 0, <= 1.2, optional (default = 0.9)
- cap_speed_by_design: boolean, optional (default = true)

### 4.3 Port List
- ports: array, required, min length = 2

Each port item:
- port_code: string, required
- port_name: string, optional
- eta: ISO datetime string, required
- etd: ISO datetime string, required (must be >= eta)
- channel_distance_km: number >= 0, optional
- sea_distance_to_next_km: number >= 0, optional
  - Meaningful for the leg from current port to next port
- latitude: number, optional
- longitude: number, optional

## 5. Request Example

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

## 6. Response Structure
Note: sample below is shortened for readability.

```json
{
  "ship": {
    "name": "Haian Beta",
    "ship_type": "container_ship",
    "year_built": 2018
  },
  "pollutants": ["CO2", "SO2", "PM10", "PM2.5"],
  "summary": {
    "num_ports": 3,
    "num_legs": 2,
    "at_sea_hours": 122.2222,
    "in_port_hours": 76.0,
    "at_sea_tons": {
      "CO2": 690.720492,
      "SO2": 2.177944,
      "PM10": 0.828338,
      "PM2.5": 0.663089
    },
    "in_port_tons": {
      "CO2": 38.176161,
      "SO2": 0.01343,
      "PM10": 0.005891,
      "PM2.5": 0.005292
    },
    "total_tons": {
      "CO2": 728.896653,
      "SO2": 2.191374,
      "PM10": 0.834229,
      "PM2.5": 0.668381
    },
    "total_co2_tons": 728.896653
  },
  "legs": [
    {
      "from_port": "HPH",
      "to_port": "VUT",
      "co2_tons": 408.153018,
      "emissions_tons": {
        "CO2": 408.153018,
        "SO2": 1.281252,
        "PM10": 0.487032,
        "PM2.5": 0.389625
      }
    }
  ],
  "ports": [
    {
      "port_code": "HPH",
      "co2_tons": 22.209998,
      "emissions_tons": {
        "CO2": 22.209998,
        "SO2": 0.01343,
        "PM10": 0.005891,
        "PM2.5": 0.005292
      }
    }
  ],
  "map_route": {
    "points": [
      {
        "port_code": "HPH",
        "latitude": 20.85,
        "longitude": 106.68
      }
    ],
    "segments": [
      {
        "from_port": "HPH",
        "to_port": "VUT",
        "distance_km": 1300.0,
        "co2_tons": 408.153018,
        "emissions_tons": {
          "CO2": 408.153018,
          "SO2": 1.281252,
          "PM10": 0.487032,
          "PM2.5": 0.389625
        }
      }
    ]
  }
}
```

## 7. Frontend Usage

### 7.1 Call API
```javascript
async function calculateShipVoyage(payload) {
  const res = await fetch('/api/scope3/ships/voyage/calculate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include', // send login cookie
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to calculate inter-port ship emissions');
  }

  return res.json();
}
```

### 7.2 Render KPI
- Total: summary.total_tons.CO2 (or summary.total_co2_tons)
- Pollutant switch:
  - summary.total_tons.SO2
  - summary.total_tons.PM10
  - summary.total_tons["PM2.5"]

### 7.3 Render Map
- Port markers: map_route.points
- Route polylines: map_route.segments[].coordinates
- Segment tooltip:
  - from_port -> to_port
  - emissions_tons for all pollutants
  - distance_km

### 7.4 Render Tables
- Leg table: legs
- Port table: ports
- Each row can show emissions_tons.CO2/SO2/PM10/PM2.5

## 8. Common Validation Errors
- Not logged in / session expired: HTTP 302 redirect to /login
- ports length < 2: 400, "Voyage must include at least 2 ports"
- etd < eta in a port record: 422
- Missing required fields / wrong type: 422

## 9. Notes
- No query params are required.
- If lat/lng are missing, map_route.segments.coordinates can be partial or empty.
- For backward compatibility, co2_tons/co2_grams are still included in legs and ports.
