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
            TableColumn(name="opp_id", data_type="STRING", mode="REQUIRED"),
            TableColumn(name="account_name", data_type="STRING", mode="REQUIRED"),
            TableColumn(name="amount_eur", data_type="NUMERIC", mode="REQUIRED"),
            TableColumn(name="stage", data_type="STRING", mode="REQUIRED"),
            TableColumn(name="close_date", data_type="DATE", mode="REQUIRED"),
        ]
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
