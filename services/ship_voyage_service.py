from __future__ import annotations

from datetime import timedelta
from typing import Any, Dict

from fastapi import HTTPException, status

import services.emission_ship as compute
from schemas.ship import ShipVoyageRequest, VoyagePortCall

POLLUTANTS = ("CO2", "SO2", "PM10", "PM2.5")
SULFUR_FRACTION = 0.005
AUX_BSFC = 227.0


def _bsfc_main(rpm: float) -> float:
    # Business rule: slow-speed main engine uses 195, otherwise 215 g/kWh.
    return 195.0 if float(rpm) < 130 else 215.0


def _sea_emission_factors_from_bsfc(bsfc: float) -> Dict[str, float]:
    pm10 = 0.5761 + (bsfc * 0.02247 * 7.0 * SULFUR_FRACTION)
    pm25 = pm10 * 0.8
    so2 = SULFUR_FRACTION * bsfc * 2.0 * 0.97753
    co2 = 3.114 * bsfc

    return {
        "CO2": co2,
        "SO2": so2,
        "PM10": pm10,
        "PM2.5": pm25,
    }


def _hours_between_port_calls(prev_port: VoyagePortCall, next_port: VoyagePortCall, sea_buffer_hours: float) -> float:
    start = prev_port.etd + timedelta(hours=float(sea_buffer_hours))
    hours = (next_port.eta - start).total_seconds() / 3600.0
    return max(hours, 0.0)


def _fallback_time_from_buoy(v_actual: float, buoy: int, status_name: str) -> float:
    if v_actual <= 0:
        return 0.0
    try:
        value = compute.compute_A(v_actual, buoy=buoy, status=status_name)
        return float(value) if value is not None else 0.0
    except Exception:
        return 0.0


def _pollutant_to_ship_table_name(pollutant: str) -> str:
    # in-port emission tables use SOx while API contract exposes SO2
    return "SOx" if pollutant == "SO2" else pollutant


def _get_in_port_real_efs(payload: ShipVoyageRequest, pollutants: tuple[str, ...], lf: float, engine: str) -> Dict[str, float]:
    table_pollutants = [_pollutant_to_ship_table_name(p) for p in pollutants]

    if engine == "main":
        if payload.is_man:
            raw = compute.compute_real_ef_man(
                table_pollutants,
                lf=lf,
                engine="main",
                year=payload.year_built,
                rpm=payload.rpm,
                valve_type=payload.valve_type.value,
            )
        else:
            raw = compute.compute_real_ef_non_man(
                table_pollutants,
                lf=lf,
                engine="main",
                year=payload.year_built,
                rpm=payload.rpm,
                valve_type=payload.valve_type.value,
            )
    else:
        raw = compute.compute_real_ef_non_man(
            table_pollutants,
            lf=lf,
            engine="auxiliary",
            year=payload.year_built,
            rpm=payload.rpm,
            valve_type=payload.valve_type.value,
        )

    return {
        original: float(raw.get(mapped, 0.0))
        for original, mapped in zip(pollutants, table_pollutants)
    }


def _calculate_in_port_for_call(payload: ShipVoyageRequest, port: VoyagePortCall) -> Dict[str, Any]:
    in_port_hours = max((port.etd - port.eta).total_seconds() / 3600.0, 0.0)

    if port.channel_distance_km is not None:
        distance = float(port.channel_distance_km)
        t_trip = (2.0 * distance / payload.v_trip) if payload.v_trip > 0 else 0.0
        t_maneuver = (2.0 * distance / payload.v_maneuver) if payload.v_maneuver > 0 else 0.0
    else:
        # fallback to buoy-based duration model to stay compatible with old logic
        t_trip = _fallback_time_from_buoy(payload.v_trip, payload.buoy, "trip")
        t_maneuver = _fallback_time_from_buoy(payload.v_maneuver, payload.buoy, "maneuver")

    t_anchor = max(in_port_hours - t_trip - t_maneuver, 0.0)

    ship_type = payload.ship_type.value
    p_aux = float(payload.P_aux if payload.P_aux is not None else payload.P_main / 5.0)

    lf_m_trip = float(compute.compute_lf(payload.v_trip, payload.v_max, engine="main", type=ship_type, status="trip"))
    lf_m_maneuver = float(
        compute.compute_lf(payload.v_maneuver, payload.v_max, engine="main", type=ship_type, status="maneuver")
    )
    lf_a_trip = float(compute.compute_lf(payload.v_trip, payload.v_max, engine="auxiliary", type=ship_type, status="trip"))
    lf_a_maneuver = float(
        compute.compute_lf(payload.v_maneuver, payload.v_max, engine="auxiliary", type=ship_type, status="maneuver")
    )
    lf_a_anchor = float(compute.compute_lf(0.0, payload.v_max, engine="auxiliary", type=ship_type, status="mooring"))

    ef_m_trip = _get_in_port_real_efs(payload, POLLUTANTS, lf_m_trip, engine="main")
    ef_m_maneuver = _get_in_port_real_efs(payload, POLLUTANTS, lf_m_maneuver, engine="main")
    ef_a_trip = _get_in_port_real_efs(payload, POLLUTANTS, lf_a_trip, engine="auxiliary")
    ef_a_maneuver = _get_in_port_real_efs(payload, POLLUTANTS, lf_a_maneuver, engine="auxiliary")
    ef_a_anchor = _get_in_port_real_efs(payload, POLLUTANTS, lf_a_anchor, engine="auxiliary")

    emissions_grams: Dict[str, float] = {}
    emissions_tons: Dict[str, float] = {}

    for pollutant in POLLUTANTS:
        e1 = payload.P_main * t_trip * lf_m_trip * ef_m_trip[pollutant]
        e2 = payload.P_main * t_maneuver * lf_m_maneuver * ef_m_maneuver[pollutant]
        e3 = p_aux * t_trip * lf_a_trip * ef_a_trip[pollutant]
        e4 = p_aux * t_maneuver * lf_a_maneuver * ef_a_maneuver[pollutant]
        e5 = p_aux * t_anchor * lf_a_anchor * ef_a_anchor[pollutant]

        grams = float(e1 + e2 + e3 + e4 + e5)
        emissions_grams[pollutant] = grams
        emissions_tons[pollutant] = grams / 1_000_000.0

    return {
        "port_code": port.port_code,
        "port_name": port.port_name or port.port_code,
        "eta": port.eta.isoformat(),
        "etd": port.etd.isoformat(),
        "in_port_hours": round(in_port_hours, 4),
        "t_trip": round(t_trip, 4),
        "t_maneuver": round(t_maneuver, 4),
        "t_anchor": round(t_anchor, 4),
        "co2_grams": round(emissions_grams["CO2"], 4),
        "co2_tons": round(emissions_tons["CO2"], 6),
        "emissions_grams": {k: round(v, 4) for k, v in emissions_grams.items()},
        "emissions_tons": {k: round(v, 6) for k, v in emissions_tons.items()},
        "latitude": port.latitude,
        "longitude": port.longitude,
    }


def _calculate_at_sea_leg(payload: ShipVoyageRequest, prev_port: VoyagePortCall, next_port: VoyagePortCall) -> Dict[str, Any]:
    schedule_hours = _hours_between_port_calls(prev_port, next_port, payload.sea_buffer_hours)

    if schedule_hours <= 0:
        zero_emissions = {p: 0.0 for p in POLLUTANTS}
        return {
            "from_port": prev_port.port_code,
            "to_port": next_port.port_code,
            "hours": 0.0,
            "distance_km": float(prev_port.sea_distance_to_next_km or 0.0),
            "speed_kmh": 0.0,
            "note": "Leg is too short/overlapped in schedule; treated as in-port operation.",
            "co2_grams": 0.0,
            "co2_tons": 0.0,
            "emissions_grams": zero_emissions,
            "emissions_tons": zero_emissions,
            "from": {
                "port_code": prev_port.port_code,
                "port_name": prev_port.port_name or prev_port.port_code,
                "latitude": prev_port.latitude,
                "longitude": prev_port.longitude,
            },
            "to": {
                "port_code": next_port.port_code,
                "port_name": next_port.port_name or next_port.port_code,
                "latitude": next_port.latitude,
                "longitude": next_port.longitude,
            },
        }

    design_speed = payload.v_sea or (payload.default_sea_speed_ratio * payload.v_max)

    if prev_port.sea_distance_to_next_km is not None:
        distance_km = float(prev_port.sea_distance_to_next_km)
        raw_speed = distance_km / schedule_hours if schedule_hours > 0 else 0.0
    else:
        raw_speed = design_speed
        distance_km = schedule_hours * raw_speed

    speed_kmh = raw_speed
    if payload.cap_speed_by_design and design_speed > 0:
        speed_kmh = min(speed_kmh, design_speed)

    hours = (distance_km / speed_kmh) if speed_kmh > 0 else 0.0

    lf_main = max(0.0, min(1.5, (speed_kmh / payload.v_max) ** 3))
    lf_aux = payload.lf_aux_at_sea

    p_aux = float(payload.P_aux if payload.P_aux is not None else payload.P_main / 5.0)
    ef_main = _sea_emission_factors_from_bsfc(_bsfc_main(payload.rpm))
    ef_aux = _sea_emission_factors_from_bsfc(AUX_BSFC)

    emissions_grams: Dict[str, float] = {}
    emissions_tons: Dict[str, float] = {}

    for pollutant in POLLUTANTS:
        grams = (
            payload.P_main * lf_main * hours * ef_main[pollutant]
            + p_aux * lf_aux * hours * ef_aux[pollutant]
        )
        emissions_grams[pollutant] = float(grams)
        emissions_tons[pollutant] = float(grams) / 1_000_000.0

    return {
        "from_port": prev_port.port_code,
        "to_port": next_port.port_code,
        "hours": round(hours, 4),
        "distance_km": round(distance_km, 4),
        "speed_kmh": round(speed_kmh, 4),
        "load_factor_main": round(lf_main, 6),
        "load_factor_aux": round(lf_aux, 6),
        "co2_grams": round(emissions_grams["CO2"], 4),
        "co2_tons": round(emissions_tons["CO2"], 6),
        "emissions_grams": {k: round(v, 4) for k, v in emissions_grams.items()},
        "emissions_tons": {k: round(v, 6) for k, v in emissions_tons.items()},
        "from": {
            "port_code": prev_port.port_code,
            "port_name": prev_port.port_name or prev_port.port_code,
            "latitude": prev_port.latitude,
            "longitude": prev_port.longitude,
        },
        "to": {
            "port_code": next_port.port_code,
            "port_name": next_port.port_name or next_port.port_code,
            "latitude": next_port.latitude,
            "longitude": next_port.longitude,
        },
    }


def _sum_pollutants(target: Dict[str, float], source: Dict[str, float]) -> None:
    for pollutant in POLLUTANTS:
        target[pollutant] = float(target.get(pollutant, 0.0)) + float(source.get(pollutant, 0.0))


def calculate_ship_voyage_emissions(payload: ShipVoyageRequest) -> Dict[str, Any]:
    if len(payload.ports) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Voyage must include at least 2 ports",
        )

    sea_legs: list[Dict[str, Any]] = []
    port_calls: list[Dict[str, Any]] = []

    at_sea_tons = {p: 0.0 for p in POLLUTANTS}
    in_port_tons = {p: 0.0 for p in POLLUTANTS}

    for idx in range(len(payload.ports) - 1):
        leg = _calculate_at_sea_leg(payload, payload.ports[idx], payload.ports[idx + 1])
        sea_legs.append(leg)
        _sum_pollutants(at_sea_tons, leg["emissions_tons"])

    for port in payload.ports:
        info = _calculate_in_port_for_call(payload, port)
        port_calls.append(info)
        _sum_pollutants(in_port_tons, info["emissions_tons"])

    total_tons = {p: at_sea_tons[p] + in_port_tons[p] for p in POLLUTANTS}

    map_points = [
        {
            "port_code": p.port_code,
            "port_name": p.port_name or p.port_code,
            "latitude": p.latitude,
            "longitude": p.longitude,
            "eta": p.eta.isoformat(),
            "etd": p.etd.isoformat(),
        }
        for p in payload.ports
    ]

    map_segments = []
    for leg in sea_legs:
        coords = []
        if leg["from"].get("latitude") is not None and leg["from"].get("longitude") is not None:
            coords.append({"lat": leg["from"]["latitude"], "lng": leg["from"]["longitude"]})
        if leg["to"].get("latitude") is not None and leg["to"].get("longitude") is not None:
            coords.append({"lat": leg["to"]["latitude"], "lng": leg["to"]["longitude"]})

        map_segments.append(
            {
                "from_port": leg["from_port"],
                "to_port": leg["to_port"],
                "coordinates": coords,
                "distance_km": leg["distance_km"],
                "co2_tons": leg["co2_tons"],
                "emissions_tons": leg["emissions_tons"],
            }
        )

    total_at_sea_hours = sum(float(x["hours"]) for x in sea_legs)
    total_in_port_hours = sum(float(x["in_port_hours"]) for x in port_calls)

    return {
        "ship": {
            "name": payload.name,
            "ship_type": payload.ship_type.value,
            "year_built": payload.year_built,
        },
        "pollutants": list(POLLUTANTS),
        "summary": {
            "num_ports": len(payload.ports),
            "num_legs": len(sea_legs),
            "at_sea_hours": round(total_at_sea_hours, 4),
            "in_port_hours": round(total_in_port_hours, 4),
            "at_sea_tons": {k: round(v, 6) for k, v in at_sea_tons.items()},
            "in_port_tons": {k: round(v, 6) for k, v in in_port_tons.items()},
            "total_tons": {k: round(v, 6) for k, v in total_tons.items()},
            "at_sea_co2_tons": round(at_sea_tons["CO2"], 6),
            "in_port_co2_tons": round(in_port_tons["CO2"], 6),
            "total_co2_tons": round(total_tons["CO2"], 6),
        },
        "legs": sea_legs,
        "ports": port_calls,
        "map_route": {
            "points": map_points,
            "segments": map_segments,
        },
    }
