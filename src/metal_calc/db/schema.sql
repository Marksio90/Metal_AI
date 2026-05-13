-- Metal Cost Estimation — SQLite schema
-- All monetary values in PLN (zł), all times in seconds.
-- Version: 1.0.0

PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

-- -----------------------------------------------------------------------
-- 1. machine_rates  (imported from Excel; version-controlled)
-- -----------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS machine_rates (
    id                     INTEGER PRIMARY KEY AUTOINCREMENT,
    lp                     INTEGER NOT NULL,
    name                   TEXT    NOT NULL,
    dept                   TEXT    NOT NULL,
    cennik_version         TEXT    NOT NULL DEFAULT '2025-04-07',
    valid_from             TEXT    NOT NULL,   -- ISO date
    valid_to               TEXT,              -- NULL = open-ended
    wage_piece_zl_h        REAL    NOT NULL,
    other_wage_multiplier  REAL    NOT NULL,
    total_wages_zl_h       REAL    NOT NULL,
    zus_zl_h               REAL    NOT NULL,
    ppk_zl_h               REAL    NOT NULL,
    direct_labour_zl_h     REAL    NOT NULL,
    overhead_dept_pct      REAL    NOT NULL,
    overhead_dept_zl_h     REAL    NOT NULL,
    overhead_co_pct        REAL    NOT NULL,
    overhead_co_zl_h       REAL    NOT NULL,
    production_cost_zl_h   REAL    NOT NULL,
    selling_cost_pct       REAL    NOT NULL,
    selling_cost_zl_h      REAL    NOT NULL,
    total_cost_zl_h        REAL    NOT NULL,
    rounded_zl_h           REAL    NOT NULL,
    price_0pct_zl_h        REAL    NOT NULL,
    price_20pct_zl_h       REAL    NOT NULL,
    price_45pct_zl_h       REAL    NOT NULL,
    UNIQUE(name, cennik_version)
);

-- -----------------------------------------------------------------------
-- 2. material_price_sources
-- -----------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS material_price_sources (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    material_family  TEXT    NOT NULL,   -- MaterialFamily enum value
    material_grade   TEXT    NOT NULL,   -- e.g. 'S235JR', '304'
    form             TEXT    NOT NULL,   -- MaterialForm enum value
    unit             TEXT    NOT NULL,   -- 'kg', 'mb', 'm2'
    price_per_unit   REAL    NOT NULL,
    source           TEXT    NOT NULL,   -- PriceSource enum value
    valid_from       TEXT    NOT NULL,   -- ISO date
    valid_to         TEXT,               -- NULL = open-ended
    source_ref       TEXT    NOT NULL DEFAULT '',
    confirmed        INTEGER NOT NULL DEFAULT 1,  -- 0 = unconfirmed/temporary
    created_at       TEXT    NOT NULL DEFAULT (datetime('now')),
    notes            TEXT    NOT NULL DEFAULT ''
);

-- -----------------------------------------------------------------------
-- 3. outside_service_prices
-- -----------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS outside_service_prices (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    service_type   TEXT  NOT NULL,  -- OutsideServiceType enum
    subtype        TEXT  NOT NULL DEFAULT '',  -- e.g. 'bebn', 'trawers'
    unit           TEXT  NOT NULL,
    price_per_unit REAL  NOT NULL,
    supplier       TEXT  NOT NULL DEFAULT '',
    valid_from     TEXT  NOT NULL,
    valid_to       TEXT,
    source_ref     TEXT  NOT NULL DEFAULT '',
    confirmed      INTEGER NOT NULL DEFAULT 1,
    created_at     TEXT  NOT NULL DEFAULT (datetime('now'))
);

-- -----------------------------------------------------------------------
-- 4. rfq  (request for quotation — intake card)
-- -----------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS rfq (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    rfq_number      TEXT    NOT NULL UNIQUE,
    client          TEXT    NOT NULL,
    salesperson     TEXT    NOT NULL,
    received_at     TEXT    NOT NULL,   -- ISO datetime
    subject         TEXT    NOT NULL DEFAULT '',
    body_text       TEXT    NOT NULL DEFAULT '',
    status          TEXT    NOT NULL DEFAULT 'nowe',  -- RFQStatus enum
    missing_fields  TEXT    NOT NULL DEFAULT '',      -- JSON array of field names
    created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- -----------------------------------------------------------------------
-- 5. rfq_attachments
-- -----------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS rfq_attachments (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    rfq_id        INTEGER NOT NULL REFERENCES rfq(id) ON DELETE CASCADE,
    filename      TEXT    NOT NULL,
    file_type     TEXT    NOT NULL DEFAULT '',  -- 'pdf', 'jpg', 'dxf', 'stp', etc.
    file_path     TEXT    NOT NULL,
    verified      INTEGER NOT NULL DEFAULT 0,
    anonymised    INTEGER NOT NULL DEFAULT 0,
    created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- -----------------------------------------------------------------------
-- 6. quotes
-- -----------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS quotes (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    quote_number     TEXT    NOT NULL,
    version          INTEGER NOT NULL DEFAULT 1,
    rfq_id           INTEGER REFERENCES rfq(id),
    client           TEXT    NOT NULL,
    salesperson      TEXT    NOT NULL,
    price_profile    INTEGER NOT NULL DEFAULT 0,  -- 0, 20, or 45
    cennik_version   TEXT    NOT NULL DEFAULT '2025-04-07',
    calc_date        TEXT    NOT NULL,
    valid_until      TEXT    NOT NULL,
    status           TEXT    NOT NULL DEFAULT 'szkic',  -- QuoteStatus enum
    tech_notes       TEXT    NOT NULL DEFAULT '',
    commercial_notes TEXT    NOT NULL DEFAULT '',
    created_at       TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at       TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE(quote_number, version)
);

-- -----------------------------------------------------------------------
-- 7. quote_items
-- -----------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS quote_items (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    quote_id        INTEGER NOT NULL REFERENCES quotes(id) ON DELETE CASCADE,
    seq             INTEGER NOT NULL DEFAULT 1,
    item_name       TEXT    NOT NULL,
    product_family  TEXT    NOT NULL,  -- ProductFamily enum value
    material_desc   TEXT    NOT NULL DEFAULT '',
    finish          TEXT    NOT NULL DEFAULT '',
    quantity        INTEGER NOT NULL,
    unit_mass_kg    REAL,
    surface_dm2     REAL,
    packaging_cost_zl REAL  NOT NULL DEFAULT 0.0,
    adjustment_zl   REAL    NOT NULL DEFAULT 0.0,
    notes           TEXT    NOT NULL DEFAULT ''
);

-- -----------------------------------------------------------------------
-- 8. quote_operations
-- -----------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS quote_operations (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    quote_item_id    INTEGER NOT NULL REFERENCES quote_items(id) ON DELETE CASCADE,
    seq              INTEGER NOT NULL DEFAULT 1,
    operation_name   TEXT    NOT NULL,
    machine_name     TEXT    NOT NULL,
    setup_sec        REAL    NOT NULL DEFAULT 0.0,
    cycle_sec        REAL    NOT NULL DEFAULT 0.0,
    extra_sec        REAL    NOT NULL DEFAULT 0.0,
    quantity         INTEGER NOT NULL,
    rate_zl_s        REAL    NOT NULL,   -- snapshot of stawka at calc time
    effective_time_s REAL    NOT NULL,   -- calculated: setup + cycle*qty + extra
    cost_zl          REAL    NOT NULL,   -- effective_time_s * rate_zl_s
    note             TEXT    NOT NULL DEFAULT ''
);

-- -----------------------------------------------------------------------
-- 9. quote_materials
-- -----------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS quote_materials (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    quote_item_id       INTEGER NOT NULL REFERENCES quote_items(id) ON DELETE CASCADE,
    material_name       TEXT    NOT NULL,
    unit                TEXT    NOT NULL,
    quantity_net        REAL    NOT NULL,
    scrap_factor        REAL    NOT NULL DEFAULT 1.0,
    quantity_gross      REAL    NOT NULL,
    price_per_unit      REAL    NOT NULL,
    price_source        TEXT    NOT NULL DEFAULT '',
    cost_zl             REAL    NOT NULL,
    note                TEXT    NOT NULL DEFAULT ''
);

-- -----------------------------------------------------------------------
-- 10. quote_outside_processing
-- -----------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS quote_outside_processing (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    quote_item_id  INTEGER NOT NULL REFERENCES quote_items(id) ON DELETE CASCADE,
    service_name   TEXT    NOT NULL,
    service_type   TEXT    NOT NULL,
    subtype        TEXT    NOT NULL DEFAULT '',
    unit           TEXT    NOT NULL,
    quantity       REAL    NOT NULL,
    price_per_unit REAL    NOT NULL,
    price_source   TEXT    NOT NULL DEFAULT '',
    cost_zl        REAL    NOT NULL,
    note           TEXT    NOT NULL DEFAULT ''
);

-- -----------------------------------------------------------------------
-- 11. assumptions_log
-- -----------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS assumptions_log (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    quote_id      INTEGER REFERENCES quotes(id) ON DELETE CASCADE,
    quote_item_id INTEGER REFERENCES quote_items(id) ON DELETE CASCADE,
    rfq_id        INTEGER REFERENCES rfq(id) ON DELETE CASCADE,
    field_name    TEXT    NOT NULL,
    assumed_value TEXT    NOT NULL,
    reason        TEXT    NOT NULL,
    confirmed     INTEGER NOT NULL DEFAULT 0,
    created_at    TEXT    NOT NULL DEFAULT (datetime('now')),
    confirmed_at  TEXT,
    confirmed_by  TEXT    NOT NULL DEFAULT ''
);

-- -----------------------------------------------------------------------
-- Indexes
-- -----------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_rfq_status       ON rfq(status);
CREATE INDEX IF NOT EXISTS idx_rfq_client       ON rfq(client);
CREATE INDEX IF NOT EXISTS idx_quotes_rfq       ON quotes(rfq_id);
CREATE INDEX IF NOT EXISTS idx_quotes_status    ON quotes(status);
CREATE INDEX IF NOT EXISTS idx_quote_items_q    ON quote_items(quote_id);
CREATE INDEX IF NOT EXISTS idx_ops_item         ON quote_operations(quote_item_id);
CREATE INDEX IF NOT EXISTS idx_mats_item        ON quote_materials(quote_item_id);
CREATE INDEX IF NOT EXISTS idx_osp_item         ON quote_outside_processing(quote_item_id);
CREATE INDEX IF NOT EXISTS idx_alog_quote       ON assumptions_log(quote_id);
CREATE INDEX IF NOT EXISTS idx_mps_family       ON material_price_sources(material_family, material_grade);
