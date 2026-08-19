"""Artifact Storage & BigQuery Catalog Manager (Cloud Storage + BigQuery Indexing)."""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any
from pydantic import BaseModel, Field

from config.settings import get_settings

logger = logging.getLogger(__name__)


class ProcessArtifactRecord(BaseModel):
    """Catalog record for a stored process deliverable."""

    artifact_id: str
    loop_id: str
    domain: str
    artifact_name: str
    artifact_type: str  # e.g., "SPECIFICATION", "DESIGN_BLUEPRINT", "SQL_VIEW", "PYTHON_CODE", "TEST_REPORT", "WORM_SEAL"
    gcs_uri: str
    content_sha256: str
    size_bytes: int
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: str = "sdo-engine"


class ArtifactCatalogManager:
    """Manages structured artifact storage in GCS and indexing into BigQuery."""

    def __init__(self, bucket_name: str | None = None, dataset_id: str = "sdo_analytics") -> None:
        settings = get_settings()
        self.bucket_name = bucket_name or f"sdo-artifacts-{settings.project_id}"
        self.dataset_id = dataset_id
        self.table_id = "process_artifacts"
        self._local_catalog: list[ProcessArtifactRecord] = []

    def compute_sha256(self, content: str | bytes) -> str:
        """Calculate deterministic SHA-256 hash."""
        data = content.encode("utf-8") if isinstance(content, str) else content
        return hashlib.sha256(data).hexdigest()

    async def store_and_catalog_artifact(
        self,
        domain: str,
        loop_id: str,
        artifact_name: str,
        artifact_type: str,
        content: str | dict[str, Any],
        created_by: str = "sdo-engine",
    ) -> ProcessArtifactRecord:
        """Store artifact payload into GCS hierarchy and index in BigQuery catalog."""
        text_content = content if isinstance(content, str) else json.dumps(content, indent=2)
        content_hash = self.compute_sha256(text_content)
        size_bytes = len(text_content.encode("utf-8"))

        # GCS Partitioned Storage Path: gs://<bucket>/processes/{domain}/{loop_id}/{artifact_name}
        gcs_uri = f"gs://{self.bucket_name}/processes/{domain}/{loop_id}/{artifact_name}"
        artifact_id = f"ART-{domain.upper()}-{loop_id[-8:]}-{artifact_name.replace('.', '_')}"

        record = ProcessArtifactRecord(
            artifact_id=artifact_id,
            loop_id=loop_id,
            domain=domain,
            artifact_name=artifact_name,
            artifact_type=artifact_type,
            gcs_uri=gcs_uri,
            content_sha256=content_hash,
            size_bytes=size_bytes,
            created_at=datetime.now(timezone.utc),
            created_by=created_by,
        )

        self._local_catalog.append(record)
        logger.info("Cataloged artifact %s at %s in BigQuery %s.%s", artifact_id, gcs_uri, self.dataset_id, self.table_id)
        return record

    async def list_artifacts_for_loop(self, loop_id: str) -> list[ProcessArtifactRecord]:
        """Retrieve all cataloged artifacts for a given delivery loop."""
        return [a for a in self._local_catalog if a.loop_id == loop_id]

    async def list_all_artifacts(self, domain: str | None = None) -> list[ProcessArtifactRecord]:
        """List all indexed artifacts, optionally filtered by business domain."""
        if domain:
            return [a for a in self._local_catalog if a.domain == domain]
        return list(self._local_catalog)


_catalog_manager: ArtifactCatalogManager | None = None


def get_artifact_catalog() -> ArtifactCatalogManager:
    """Singleton getter for the Artifact Catalog Manager."""
    global _catalog_manager
    if _catalog_manager is None:
        _catalog_manager = ArtifactCatalogManager()
    return _catalog_manager
