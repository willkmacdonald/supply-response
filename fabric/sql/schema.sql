-- Supply Response operational tables.
-- Generated from data/schemas/models.py; portable between Fabric Warehouse and SQLite.
-- All data is fictional and prefixed with RL-.

CREATE TABLE suppliers (
    supplier_id VARCHAR(255) NOT NULL,
    supplier_name VARCHAR(255) NOT NULL,
    country VARCHAR(255) NOT NULL,
    region VARCHAR(255) NOT NULL,
    risk_tier VARCHAR(32) NOT NULL,
    on_time_delivery_rate DECIMAL(18,4) NOT NULL,
    quality_score DECIMAL(18,4) NOT NULL,
    preferred BIT NOT NULL
);

CREATE TABLE parts (
    part_id VARCHAR(255) NOT NULL,
    part_number VARCHAR(255) NOT NULL,
    description VARCHAR(255) NOT NULL,
    part_type VARCHAR(32) NOT NULL,
    unit_of_measure VARCHAR(255) NOT NULL,
    standard_cost DECIMAL(18,4) NOT NULL,
    lead_time_days INT NOT NULL,
    safety_stock INT NOT NULL,
    critical BIT NOT NULL
);

CREATE TABLE supplier_parts (
    supplier_part_id VARCHAR(255) NOT NULL,
    supplier_id VARCHAR(255) NOT NULL,
    part_id VARCHAR(255) NOT NULL,
    unit_price DECIMAL(18,4) NOT NULL,
    lead_time_days INT NOT NULL,
    min_order_qty INT NOT NULL,
    is_primary_source BIT NOT NULL
);

CREATE TABLE purchase_orders (
    po_id VARCHAR(255) NOT NULL,
    po_line INT NOT NULL,
    supplier_id VARCHAR(255) NOT NULL,
    part_id VARCHAR(255) NOT NULL,
    plant_id VARCHAR(255) NOT NULL,
    order_qty INT NOT NULL,
    received_qty INT NOT NULL,
    promised_date DATE NOT NULL,
    revised_date DATE NULL,
    status VARCHAR(32) NOT NULL,
    unit_price DECIMAL(18,4) NOT NULL
);

CREATE TABLE inventory_positions (
    inventory_id VARCHAR(255) NOT NULL,
    part_id VARCHAR(255) NOT NULL,
    plant_id VARCHAR(255) NOT NULL,
    location_id VARCHAR(255) NOT NULL,
    on_hand INT NOT NULL,
    quality_hold INT NOT NULL,
    protected_allocation INT NOT NULL,
    in_transit INT NOT NULL,
    as_of_date DATE NOT NULL
);

CREATE TABLE bom_components (
    bom_id VARCHAR(255) NOT NULL,
    parent_part_id VARCHAR(255) NOT NULL,
    component_part_id VARCHAR(255) NOT NULL,
    qty_per DECIMAL(18,4) NOT NULL,
    scrap_factor DECIMAL(18,4) NOT NULL,
    level INT NOT NULL
);

CREATE TABLE production_orders (
    production_order_id VARCHAR(255) NOT NULL,
    plant_id VARCHAR(255) NOT NULL,
    part_id VARCHAR(255) NOT NULL,
    quantity INT NOT NULL,
    start_date DATE NOT NULL,
    due_date DATE NOT NULL,
    status VARCHAR(32) NOT NULL,
    priority INT NOT NULL
);

CREATE TABLE customers (
    customer_id VARCHAR(255) NOT NULL,
    customer_name VARCHAR(255) NOT NULL,
    segment VARCHAR(255) NOT NULL,
    region VARCHAR(255) NOT NULL,
    priority_tier INT NOT NULL,
    otif_target DECIMAL(18,4) NOT NULL
);

CREATE TABLE customer_orders (
    customer_order_id VARCHAR(255) NOT NULL,
    order_line INT NOT NULL,
    customer_id VARCHAR(255) NOT NULL,
    part_id VARCHAR(255) NOT NULL,
    plant_id VARCHAR(255) NOT NULL,
    quantity INT NOT NULL,
    requested_date DATE NOT NULL,
    promised_date DATE NOT NULL,
    unit_price DECIMAL(18,4) NOT NULL,
    unit_cost DECIMAL(18,4) NOT NULL,
    status VARCHAR(32) NOT NULL
);

CREATE TABLE transport_options (
    transport_option_id VARCHAR(255) NOT NULL,
    origin VARCHAR(255) NOT NULL,
    destination VARCHAR(255) NOT NULL,
    mode VARCHAR(32) NOT NULL,
    transit_days INT NOT NULL,
    cost_per_unit DECIMAL(18,4) NOT NULL,
    fixed_cost DECIMAL(18,4) NOT NULL,
    max_qty INT NOT NULL
);

CREATE TABLE quality_qualifications (
    qualification_id VARCHAR(255) NOT NULL,
    supplier_id VARCHAR(255) NOT NULL,
    part_id VARCHAR(255) NOT NULL,
    status VARCHAR(32) NOT NULL,
    audit_complete BIT NOT NULL,
    first_article_complete BIT NOT NULL,
    expected_decision_date DATE NULL,
    note VARCHAR(255) NOT NULL,
    source_reference VARCHAR(255) NOT NULL
);

CREATE TABLE disruptions (
    disruption_id VARCHAR(255) NOT NULL,
    supplier_id VARCHAR(255) NOT NULL,
    part_id VARCHAR(255) NOT NULL,
    plant_id VARCHAR(255) NOT NULL,
    po_id VARCHAR(255) NULL,
    po_line INT NULL,
    delayed_qty INT NOT NULL,
    original_date DATE NOT NULL,
    revised_date DATE NULL,
    partial_qty INT NOT NULL,
    partial_date DATE NULL,
    recovery_date_confirmed BIT NOT NULL,
    severity VARCHAR(32) NOT NULL,
    status VARCHAR(32) NOT NULL,
    signal_received_at DATETIME2 NOT NULL,
    signal_source VARCHAR(255) NOT NULL,
    signal_reference VARCHAR(255) NOT NULL,
    summary VARCHAR(255) NOT NULL
);

CREATE TABLE response_scenarios (
    scenario_id VARCHAR(255) NOT NULL,
    disruption_id VARCHAR(255) NOT NULL,
    scenario_type VARCHAR(32) NOT NULL,
    title VARCHAR(255) NOT NULL,
    description VARCHAR(255) NOT NULL,
    expedite_qty INT NOT NULL,
    transfer_qty INT NOT NULL,
    resequenced_qty INT NOT NULL,
    alternate_supplier_id VARCHAR(255) NULL,
    transport_option_id VARCHAR(255) NULL,
    available_date DATE NULL,
    executable BIT NOT NULL,
    blocking_constraint VARCHAR(255) NULL,
    requires_approval BIT NOT NULL,
    assumptions VARCHAR(4000) NOT NULL
);

CREATE TABLE action_ledger (
    action_id VARCHAR(255) NOT NULL,
    disruption_id VARCHAR(255) NOT NULL,
    scenario_id VARCHAR(255) NULL,
    action_type VARCHAR(255) NOT NULL,
    status VARCHAR(32) NOT NULL,
    decided_by VARCHAR(255) NOT NULL,
    decided_at DATETIME2 NOT NULL,
    rationale VARCHAR(255) NOT NULL,
    evidence VARCHAR(4000) NOT NULL,
    calculation_version VARCHAR(255) NOT NULL,
    follow_up_tasks VARCHAR(4000) NOT NULL
);

CREATE TABLE outcome_history (
    outcome_id VARCHAR(255) NOT NULL,
    disruption_id VARCHAR(255) NOT NULL,
    scenario_id VARCHAR(255) NULL,
    action_id VARCHAR(255) NULL,
    predicted_revenue_protected DECIMAL(18,4) NOT NULL,
    actual_revenue_protected DECIMAL(18,4) NOT NULL,
    predicted_cost DECIMAL(18,4) NOT NULL,
    actual_cost DECIMAL(18,4) NOT NULL,
    predicted_otif_impact DECIMAL(18,4) NOT NULL,
    actual_otif_impact DECIMAL(18,4) NOT NULL,
    recorded_at DATETIME2 NOT NULL,
    lessons_learned VARCHAR(255) NOT NULL
);
