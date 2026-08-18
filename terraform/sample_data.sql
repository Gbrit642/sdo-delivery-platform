-- Wallbox SDO Platform Sample BigQuery Data for Finance Demo
-- Project: managed-agent-504409 | Dataset: sdo_finance_demo

-- 1. Create Invoices Table
CREATE TABLE IF NOT EXISTS `sdo_finance_demo.invoices` (
    invoice_id STRING OPTIONS(description="Unique Invoice UUID"),
    account_id STRING OPTIONS(description="Wallbox Customer Account ID"),
    amount NUMERIC OPTIONS(description="Invoice Gross Amount"),
    currency STRING OPTIONS(description="Billing Currency Code: EUR, USD, GBP"),
    status STRING OPTIONS(description="Payment Status: PAID, PENDING, OVERDUE"),
    issue_date DATE OPTIONS(description="Invoice Issue Date"),
    due_date DATE OPTIONS(description="Payment Due Date")
)
PARTITION BY issue_date
CLUSTER BY currency, status;

-- 2. Create Exchange Rates Table
CREATE TABLE IF NOT EXISTS `sdo_finance_demo.exchange_rates` (
    rate_date DATE OPTIONS(description="Effective Date of Exchange Rate"),
    base_currency STRING OPTIONS(description="Base Currency Code (EUR)"),
    target_currency STRING OPTIONS(description="Target Currency Code (USD, GBP)"),
    rate FLOAT64 OPTIONS(description="FX Multiplier Rate")
)
PARTITION BY rate_date
CLUSTER BY target_currency;

-- 3. Seed Sample Records
INSERT INTO `sdo_finance_demo.invoices` (invoice_id, account_id, amount, currency, status, issue_date, due_date)
VALUES
    ('INV-2026-001', 'ACC-WBX-901', 1250.00, 'EUR', 'PAID', '2026-08-01', '2026-08-15'),
    ('INV-2026-002', 'ACC-WBX-902', 8400.50, 'USD', 'PAID', '2026-08-02', '2026-08-16'),
    ('INV-2026-003', 'ACC-WBX-903', 3100.00, 'GBP', 'PAID', '2026-08-03', '2026-08-17'),
    ('INV-2026-004', 'ACC-WBX-904', 500.00, 'EUR', 'PENDING', '2026-08-10', '2026-08-24');

INSERT INTO `sdo_finance_demo.exchange_rates` (rate_date, base_currency, target_currency, rate)
VALUES
    ('2026-08-01', 'EUR', 'USD', 1.0850),
    ('2026-08-01', 'EUR', 'GBP', 0.8540),
    ('2026-08-02', 'EUR', 'USD', 1.0865),
    ('2026-08-03', 'EUR', 'GBP', 0.8530);
