"""BigQuery Managed MCP Tool Connector with Offline Mock Fallback."""

from __future__ import annotations

import logging
from typing import Any
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class TableColumn(BaseModel):
    name: str
    data_type: str
    mode: str = "NULLABLE"
    description: str = ""


class TableMetadata(BaseModel):
    table_id: str
    dataset_id: str
    num_rows: int = 1000
    columns: list[TableColumn] = Field(default_factory=list)


# Synthetic sample schema metadata for the demo datasets
SAMPLE_DATASETS: dict[str, dict[str, list[TableColumn]]] = {
    "sdo_finance_demo": {
        "invoices": [
            TableColumn(name="invoice_id", data_type="STRING", mode="REQUIRED", description="Unique invoice ID"),
            TableColumn(name="account_id", data_type="STRING", mode="REQUIRED", description="Wallbox customer account ID"),
            TableColumn(name="amount", data_type="NUMERIC", mode="REQUIRED", description="Invoice total amount"),
            TableColumn(name="currency", data_type="STRING", mode="REQUIRED", description="Billing currency (EUR, USD, GBP)"),
            TableColumn(name="status", data_type="STRING", mode="REQUIRED", description="Payment status (PAID, PENDING, OVERDUE)"),
            TableColumn(name="issue_date", data_type="DATE", mode="REQUIRED", description="Invoice issue date"),
            TableColumn(name="due_date", data_type="DATE", mode="REQUIRED", description="Invoice due date"),
        ],
        "exchange_rates": [
            TableColumn(name="rate_date", data_type="DATE", mode="REQUIRED", description="Date of exchange rate"),
            TableColumn(name="base_currency", data_type="STRING", mode="REQUIRED", description="Base currency (EUR)"),
            TableColumn(name="target_currency", data_type="STRING", mode="REQUIRED", description="Target currency (USD, GBP)"),
            TableColumn(name="rate", data_type="FLOAT64", mode="REQUIRED", description="Conversion exchange rate"),
        ],
        "billing_events": [
            TableColumn(name="event_id", data_type="STRING", mode="REQUIRED", description="Event UUID"),
            TableColumn(name="account_id", data_type="STRING", mode="REQUIRED", description="Customer account"),
            TableColumn(name="charger_id", data_type="STRING", mode="REQUIRED", description="Charger serial number"),
            TableColumn(name="kwh_consumed", data_type="FLOAT64", mode="REQUIRED", description="Energy dispensed in kWh"),
            TableColumn(name="event_timestamp", data_type="TIMESTAMP", mode="REQUIRED", description="Event timestamp"),
        ],
    },
    "sdo_sales_demo": {
        "opportunities": [
            TableColumn(name="opp_id", data_type="STRING", mode="REQUIRED", description="Unique opportunity ID"),
            TableColumn(name="account_name", data_type="STRING", mode="REQUIRED", description="Customer account name"),
            TableColumn(name="amount_eur", data_type="NUMERIC", mode="REQUIRED", description="Estimated pipeline amount in EUR"),
            TableColumn(name="stage", data_type="STRING", mode="REQUIRED", description="Sales stage: Prospecting, Qualified, Negotiation, Won, Lost"),
            TableColumn(name="close_date", data_type="DATE", mode="REQUIRED", description="Expected close date"),
        ],
        "accounts": [
            TableColumn(name="account_id", data_type="STRING", mode="REQUIRED", description="Account identifier"),
            TableColumn(name="region", data_type="STRING", mode="REQUIRED", description="Sales region: EMEA, NA, APAC"),
            TableColumn(name="tier", data_type="STRING", mode="REQUIRED", description="Enterprise, Commercial, SMB"),
        ],
        "lead_conversions": [
            TableColumn(name="lead_id", data_type="STRING", mode="REQUIRED", description="Lead identifier"),
            TableColumn(name="converted_flag", data_type="INT64", mode="REQUIRED", description="1 if converted, 0 otherwise"),
            TableColumn(name="conversion_timestamp", data_type="TIMESTAMP", mode="REQUIRED", description="Conversion time"),
        ],
    },
    "sdo_firmware_demo": {
        "charger_telemetry": [
            TableColumn(name="charger_id", data_type="STRING", mode="REQUIRED", description="Serial number of charger"),
            TableColumn(name="firmware_version", data_type="STRING", mode="REQUIRED", description="Installed firmware version (e.g. 5.14.8)"),
            TableColumn(name="voltage", data_type="FLOAT64", mode="REQUIRED", description="Operating line voltage"),
            TableColumn(name="current_amperes", data_type="FLOAT64", mode="REQUIRED", description="Charging current in Amperes"),
            TableColumn(name="temperature_celsius", data_type="FLOAT64", mode="REQUIRED", description="Internal hardware temperature"),
            TableColumn(name="event_timestamp", data_type="TIMESTAMP", mode="REQUIRED", description="Telemetry recording timestamp"),
        ],
        "firmware_releases": [
            TableColumn(name="release_id", data_type="STRING", mode="REQUIRED", description="Release identifier"),
            TableColumn(name="version", data_type="STRING", mode="REQUIRED", description="Semantic firmware version"),
            TableColumn(name="release_date", data_type="DATE", mode="REQUIRED", description="Public rollout date"),
            TableColumn(name="status", data_type="STRING", mode="REQUIRED", description="GA, STAGING, DEPRECATED"),
        ],
        "error_logs": [
            TableColumn(name="log_id", data_type="STRING", mode="REQUIRED", description="Log entry identifier"),
            TableColumn(name="charger_id", data_type="STRING", mode="REQUIRED", description="Affected charger"),
            TableColumn(name="error_code", data_type="STRING", mode="REQUIRED", description="OCPP error code"),
            TableColumn(name="severity", data_type="STRING", mode="REQUIRED", description="CRITICAL, WARNING, INFO"),
            TableColumn(name="log_timestamp", data_type="TIMESTAMP", mode="REQUIRED", description="Timestamp of occurrence"),
        ],
    },
    "sdo_marketing_demo": {
        "campaign_events": [
            TableColumn(name="event_id", data_type="STRING", mode="REQUIRED", description="Event tracking identifier"),
            TableColumn(name="campaign_id", data_type="STRING", mode="REQUIRED", description="Marketing campaign ID"),
            TableColumn(name="channel", data_type="STRING", mode="REQUIRED", description="Acquisition channel: Search, Social, Affiliate"),
            TableColumn(name="user_id_hashed", data_type="STRING", mode="REQUIRED", description="SHA-256 pseudonymized user ID"),
            TableColumn(name="event_type", data_type="STRING", mode="REQUIRED", description="Click, Impression, Signup, Purchase"),
            TableColumn(name="event_timestamp", data_type="TIMESTAMP", mode="REQUIRED", description="Event occurrence timestamp"),
        ],
        "user_acquisitions": [
            TableColumn(name="acquisition_id", data_type="STRING", mode="REQUIRED", description="Acquisition identifier"),
            TableColumn(name="campaign_id", data_type="STRING", mode="REQUIRED", description="Attributed campaign"),
            TableColumn(name="cac_usd", data_type="NUMERIC", mode="REQUIRED", description="Calculated Customer Acquisition Cost in USD"),
            TableColumn(name="converted_at", data_type="TIMESTAMP", mode="REQUIRED", description="Conversion timestamp"),
        ],
        "ad_spend": [
            TableColumn(name="spend_id", data_type="STRING", mode="REQUIRED", description="Ad spend record ID"),
            TableColumn(name="channel", data_type="STRING", mode="REQUIRED", description="Marketing channel"),
            TableColumn(name="amount_usd", data_type="NUMERIC", mode="REQUIRED", description="Gross ad spend amount"),
            TableColumn(name="spend_date", data_type="DATE", mode="REQUIRED", description="Date of spend"),
        ],
    },
    "sdo_logistics_demo": {
        "inventory": [
            TableColumn(name="part_id", data_type="STRING", mode="REQUIRED", description="SKU / Part number"),
            TableColumn(name="warehouse_id", data_type="STRING", mode="REQUIRED", description="Warehouse facility code"),
            TableColumn(name="quantity_on_hand", data_type="INT64", mode="REQUIRED", description="Physical stock count"),
            TableColumn(name="reorder_point", data_type="INT64", mode="REQUIRED", description="Safety threshold triggering replenishment"),
            TableColumn(name="last_updated", data_type="TIMESTAMP", mode="REQUIRED", description="Last stock inventory check"),
        ],
        "warehouse_dispatch": [
            TableColumn(name="dispatch_id", data_type="STRING", mode="REQUIRED", description="Fulfillment dispatch identifier"),
            TableColumn(name="order_id", data_type="STRING", mode="REQUIRED", description="Sales / manufacturing order ID"),
            TableColumn(name="dispatch_time_hours", data_type="FLOAT64", mode="REQUIRED", description="Fulfillment duration in hours"),
            TableColumn(name="sla_target_hours", data_type="FLOAT64", mode="REQUIRED", description="SLA target in hours"),
            TableColumn(name="status", data_type="STRING", mode="REQUIRED", description="ON_TIME, DELAYED, IN_TRANSIT"),
        ],
        "parts_catalog": [
            TableColumn(name="part_id", data_type="STRING", mode="REQUIRED", description="Part identifier"),
            TableColumn(name="part_name", data_type="STRING", mode="REQUIRED", description="Part component description"),
            TableColumn(name="category", data_type="STRING", mode="REQUIRED", description="Electronics, Enclosure, Cable, Connector"),
            TableColumn(name="unit_cost_eur", data_type="NUMERIC", mode="REQUIRED", description="BOM unit cost in EUR"),
        ],
    },
}


class BigQueryMCPClient:
    """Client for BigQuery Managed Model Context Protocol (MCP) server."""

    def __init__(self, project_id: str = "managed-agent-504409", dataset_id: str = "sdo_finance_demo") -> None:
        self.project_id = project_id
        self.dataset_id = dataset_id

    async def list_tables(self, dataset_id: str | None = None) -> list[str]:
        """List available tables in the specified dataset."""
        ds = dataset_id or self.dataset_id
        tables = SAMPLE_DATASETS.get(ds, {})
        return list(tables.keys())

    async def get_table_schema(self, table_name: str, dataset_id: str | None = None) -> TableMetadata:
        """Inspect table schema and column definitions."""
        ds = dataset_id or self.dataset_id
        tables = SAMPLE_DATASETS.get(ds, {})
        if table_name not in tables:
            raise KeyError(f"Table '{table_name}' not found in dataset '{ds}'.")

        columns = tables[table_name]
        return TableMetadata(table_id=table_name, dataset_id=ds, columns=columns)

    async def execute_query(self, sql_query: str) -> dict[str, Any]:
        """Execute a BigQuery SQL transformation or query."""
        logger.info("Executing BigQuery SQL query: %s", sql_query.strip().splitlines()[0])
        # Return synthetic results conforming to query structure
        return {
            "job_id": "job_bq_mock_01KZZ998877",
            "status": "DONE",
            "bytes_processed": 1048576,
            "rows_affected": 42,
            "sample_rows": [
                {"currency": "EUR", "total_revenue_eur": 125400.50, "usd_equivalent": 136059.54, "variance_pct": 0.02},
                {"currency": "USD", "total_revenue_eur": 98200.00, "usd_equivalent": 98200.00, "variance_pct": 0.00},
            ],
        }
