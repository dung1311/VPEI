-- Migration: add ship_voyages table + index for Scope 3 inter-port vessel records
-- Safe to run multiple times on SQLite.

CREATE TABLE IF NOT EXISTS ship_voyages (
    id INTEGER PRIMARY KEY,
    name VARCHAR NOT NULL,
    ship_type VARCHAR(18) NOT NULL,
    year_built INTEGER NOT NULL,
    rpm FLOAT NOT NULL,
    valve_type VARCHAR(2) NOT NULL,
    is_man BOOLEAN NOT NULL DEFAULT 0,
    buoy INTEGER DEFAULT 0,
    P_main FLOAT NOT NULL,
    P_aux FLOAT,
    start_time DATETIME,
    end_time DATETIME,
    total_co2 FLOAT DEFAULT 0.0,
    payload_json TEXT
);

CREATE INDEX IF NOT EXISTS ix_ship_voyages_start_time ON ship_voyages (start_time);
