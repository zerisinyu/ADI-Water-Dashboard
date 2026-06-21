"""
ETL Pipeline for the Water Utility Dashboard.

Orchestrates the full extract-validate-transform-load cycle with structured
logging and centralised derived-metric calculations.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import pandas as pd

from data.database import get_connection, init_database, query, DATA_DIR
from data.schemas import validate_dataframe, SCHEMA_REGISTRY

logger = logging.getLogger(__name__)


@dataclass
class PipelineRunResult:
    """Stores the outcome of a single pipeline run."""
    started_at: datetime
    finished_at: Optional[datetime] = None
    duration_seconds: float = 0.0
    tables_loaded: dict[str, int] = field(default_factory=dict)
    validation_results: dict[str, dict] = field(default_factory=dict)
    derived_metrics_created: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return len(self.errors) == 0


class ETLPipeline:
    """
    End-to-end data pipeline: extract CSVs -> validate schemas ->
    compute derived metrics -> load into DuckDB views.
    """

    def __init__(self) -> None:
        self._last_run: Optional[PipelineRunResult] = None

    @property
    def last_run(self) -> Optional[PipelineRunResult]:
        return self._last_run

    def run(self, force: bool = False) -> PipelineRunResult:
        """Execute the full pipeline."""
        result = PipelineRunResult(started_at=datetime.now())
        t0 = time.perf_counter()

        try:
            self._extract(result, force=force)
            self._validate(result)
            self._transform(result)
        except Exception as exc:
            result.errors.append(f"Pipeline failed: {exc}")
            logger.exception("Pipeline run failed")

        result.duration_seconds = time.perf_counter() - t0
        result.finished_at = datetime.now()
        self._last_run = result

        status = "SUCCESS" if result.success else "FAILED"
        logger.info(
            "Pipeline %s in %.2fs — %d tables, %d derived metrics, %d errors",
            status,
            result.duration_seconds,
            len(result.tables_loaded),
            len(result.derived_metrics_created),
            len(result.errors),
        )
        return result

    # ------------------------------------------------------------------
    # Extract
    # ------------------------------------------------------------------

    def _extract(self, result: PipelineRunResult, force: bool = False) -> None:
        """Load CSV files into DuckDB tables."""
        logger.info("EXTRACT — loading CSVs into DuckDB")
        counts = init_database(force=force)
        result.tables_loaded = counts

    # ------------------------------------------------------------------
    # Validate
    # ------------------------------------------------------------------

    def _validate(self, result: PipelineRunResult) -> None:
        """Run Pandera schema validation on each table."""
        logger.info("VALIDATE — checking schemas")
        conn = get_connection()

        for table_name in SCHEMA_REGISTRY:
            try:
                df = conn.execute(f"SELECT * FROM {table_name}").fetchdf()
                vr = validate_dataframe(table_name, df)
                result.validation_results[table_name] = vr
                if not vr["valid"]:
                    n_err = len(vr["errors"])
                    logger.warning(
                        "Validation: %s has %d issues (showing first 5): %s",
                        table_name, n_err, vr["errors"][:5],
                    )
            except Exception as exc:
                result.validation_results[table_name] = {
                    "valid": False,
                    "errors": [str(exc)],
                    "row_count": 0,
                }

    # ------------------------------------------------------------------
    # Transform — derived metrics as DuckDB views
    # ------------------------------------------------------------------

    def _transform(self, result: PipelineRunResult) -> None:
        """Create derived-metric views in DuckDB."""
        logger.info("TRANSFORM — creating derived metrics")
        conn = get_connection()

        views = {
            "v_billing_monthly": """
                CREATE OR REPLACE VIEW v_billing_monthly AS
                SELECT
                    date_trunc('month', date)::DATE AS month,
                    country,
                    zone,
                    COUNT(DISTINCT customer_id) AS customers,
                    SUM(consumption_m3)          AS total_consumption_m3,
                    SUM(billed)                  AS total_billed,
                    SUM(paid)                    AS total_paid,
                    CASE WHEN SUM(billed) > 0
                         THEN SUM(paid) / SUM(billed) * 100
                         ELSE 0 END              AS collection_efficiency
                FROM billing
                WHERE date IS NOT NULL
                GROUP BY 1, 2, 3
            """,
            "v_production_monthly": """
                CREATE OR REPLACE VIEW v_production_monthly AS
                SELECT
                    date_trunc('month', date)::DATE AS month,
                    country,
                    source,
                    SUM(production_m3)   AS total_production_m3,
                    AVG(service_hours)   AS avg_service_hours,
                    COUNT(*)             AS days_recorded
                FROM production
                WHERE date IS NOT NULL
                GROUP BY 1, 2, 3
            """,
            "v_nrw_monthly": """
                CREATE OR REPLACE VIEW v_nrw_monthly AS
                SELECT
                    p.month,
                    p.country,
                    p.total_production_m3,
                    COALESCE(b.total_consumption_m3, 0) AS total_consumption_m3,
                    CASE WHEN p.total_production_m3 > 0
                         THEN (p.total_production_m3 - COALESCE(b.total_consumption_m3, 0))
                              / p.total_production_m3 * 100
                         ELSE 0 END AS nrw_pct,
                    p.avg_service_hours
                FROM (
                    SELECT month, country,
                           SUM(total_production_m3) AS total_production_m3,
                           AVG(avg_service_hours) AS avg_service_hours
                    FROM v_production_monthly GROUP BY 1, 2
                ) p
                LEFT JOIN (
                    SELECT month, country,
                           SUM(total_consumption_m3) AS total_consumption_m3
                    FROM v_billing_monthly GROUP BY 1, 2
                ) b ON p.month = b.month AND p.country = b.country
            """,
            "v_service_quality": """
                CREATE OR REPLACE VIEW v_service_quality AS
                SELECT
                    country, city, zone, month, year,
                    make_date(year, month, 1) AS date,
                    w_supplied, total_consumption, metered,
                    CASE WHEN tests_conducted_chlorine > 0 AND test_conducted_ecoli > 0
                         THEN (
                            CAST(test_passed_chlorine AS DOUBLE) / tests_conducted_chlorine * 100
                            + CAST(tests_passed_ecoli AS DOUBLE) / test_conducted_ecoli * 100
                         ) / 2
                         ELSE NULL END AS water_quality_rate,
                    CASE WHEN complaints > 0
                         THEN CAST(resolved AS DOUBLE) / complaints * 100
                         ELSE NULL END AS complaint_resolution_rate,
                    CASE WHEN w_supplied > 0
                         THEN (w_supplied - total_consumption) / w_supplied * 100
                         ELSE NULL END AS nrw_rate,
                    CASE WHEN households > 0
                         THEN CAST(sewer_connections AS DOUBLE) / households * 100
                         ELSE NULL END AS sewer_coverage_rate,
                    ww_capacity, ww_treated, ww_reused, ww_collected,
                    complaints, resolved, complaint_resolution,
                    sewer_connections, public_toilets,
                    workforce, f_workforce,
                    hh_emptied, fs_treated, fs_reused,
                    households
                FROM sw_service
            """,
            "v_financial_monthly": """
                CREATE OR REPLACE VIEW v_financial_monthly AS
                SELECT
                    date,
                    country,
                    city,
                    sewer_length,
                    complaints,
                    resolved,
                    blocks,
                    sewer_billed,
                    sewer_revenue,
                    opex,
                    san_staff,
                    w_staff,
                    propoor_popn,
                    CASE WHEN sewer_billed > 0
                         THEN sewer_revenue / sewer_billed * 100
                         ELSE 0 END AS sewer_collection_rate,
                    CASE WHEN opex > 0
                         THEN sewer_revenue / opex * 100
                         ELSE 0 END AS cost_recovery_pct
                FROM fin_service
            """,
        }

        for view_name, ddl in views.items():
            try:
                conn.execute(ddl)
                result.derived_metrics_created.append(view_name)
                logger.info("Created view: %s", view_name)
            except Exception as exc:
                result.errors.append(f"View {view_name}: {exc}")
                logger.exception("Failed to create view %s", view_name)


# Module-level singleton
_pipeline = ETLPipeline()


def run_pipeline(force: bool = False) -> PipelineRunResult:
    """Run the ETL pipeline (module-level convenience function)."""
    return _pipeline.run(force=force)


def get_last_run() -> Optional[PipelineRunResult]:
    """Return the result of the most recent pipeline run."""
    return _pipeline.last_run
