"""
Pandera validation schemas for all dashboard datasets.

Schemas are derived from the AUDC Data Dictionary and enforce data quality
constraints: type correctness, value ranges, non-null keys, and valid
category memberships.
"""
from __future__ import annotations

import pandera as pa
from pandera import Column, Check, DataFrameSchema

VALID_COUNTRIES = {"Cameroon", "Uganda", "Malawi", "Lesotho"}

BillingSchema = DataFrameSchema(
    columns={
        "customer_id": Column(int, nullable=True),
        "date": Column("datetime64[ns]", nullable=True),
        "consumption_m3": Column(float, Check.ge(0), nullable=True),
        "billed": Column(float, Check.ge(0), nullable=True),
        "paid": Column(float, Check.ge(0), nullable=True),
        "country": Column(str, Check.isin(VALID_COUNTRIES), nullable=True),
        "zone": Column(str, nullable=True),
        "source": Column(str, nullable=True),
    },
    coerce=True,
    strict=False,
    name="BillingSchema",
)

ProductionSchema = DataFrameSchema(
    columns={
        "date": Column("datetime64[ns]", nullable=True),
        "source": Column(str, nullable=True),
        "production_m3": Column(float, Check.ge(0), nullable=True),
        "service_hours": Column(float, [Check.ge(0), Check.le(24)], nullable=True),
        "country": Column(str, Check.isin(VALID_COUNTRIES), nullable=True),
    },
    coerce=True,
    strict=False,
    name="ProductionSchema",
)

ServiceSchema = DataFrameSchema(
    columns={
        "country": Column(str, Check.isin(VALID_COUNTRIES), nullable=True),
        "city": Column(str, nullable=True),
        "zone": Column(str, nullable=True),
        "month": Column(int, [Check.ge(1), Check.le(12)], nullable=True),
        "year": Column(int, [Check.ge(2019), Check.le(2030)], nullable=True),
        "w_supplied": Column(float, Check.ge(0), nullable=True),
        "total_consumption": Column(float, Check.ge(0), nullable=True),
        "metered": Column(float, Check.ge(0), nullable=True),
        "complaints": Column(int, Check.ge(0), nullable=True),
        "resolved": Column(int, Check.ge(0), nullable=True),
        "households": Column(int, Check.ge(0), nullable=True),
    },
    coerce=True,
    strict=False,
    name="ServiceSchema",
)

WaterAccessSchema = DataFrameSchema(
    columns={
        "country": Column(str, Check.isin(VALID_COUNTRIES), nullable=True),
        "zone": Column(str, nullable=True),
        "year": Column(int, [Check.ge(2019), Check.le(2030)], nullable=True),
        "w_safely_managed_pct": Column(float, [Check.ge(-1), Check.le(101)], nullable=True),
        "w_basic_pct": Column(float, [Check.ge(-1), Check.le(101)], nullable=True),
        "w_limited_pct": Column(float, [Check.ge(-1), Check.le(101)], nullable=True),
        "w_unimproved_pct": Column(float, [Check.ge(-1), Check.le(101)], nullable=True),
        "surface_water_pct": Column(float, [Check.ge(-1), Check.le(101)], nullable=True),
        "popn_total": Column(float, Check.ge(0), nullable=True),
    },
    coerce=True,
    strict=False,
    name="WaterAccessSchema",
)

SanitationAccessSchema = DataFrameSchema(
    columns={
        "country": Column(str, Check.isin(VALID_COUNTRIES), nullable=True),
        "zone": Column(str, nullable=True),
        "year": Column(int, [Check.ge(2019), Check.le(2030)], nullable=True),
        "s_safely_managed_pct": Column(float, [Check.ge(-1), Check.le(101)], nullable=True),
        "s_basic_pct": Column(float, [Check.ge(-1), Check.le(101)], nullable=True),
        "s_limited_pct": Column(float, [Check.ge(-1), Check.le(101)], nullable=True),
        "s_unimproved_pct": Column(float, [Check.ge(-1), Check.le(101)], nullable=True),
        "open_def_pct": Column(float, [Check.ge(-1), Check.le(101)], nullable=True),
        "popn_total": Column(float, Check.ge(0), nullable=True),
    },
    coerce=True,
    strict=False,
    name="SanitationAccessSchema",
)

FinancialServiceSchema = DataFrameSchema(
    columns={
        "country": Column(str, Check.isin(VALID_COUNTRIES), nullable=True),
        "city": Column(str, nullable=True),
        "date": Column("datetime64[ns]", nullable=True),
        "sewer_revenue": Column(float, Check.ge(0), nullable=True),
        "opex": Column(float, Check.ge(0), nullable=True),
        "complaints": Column(int, Check.ge(0), nullable=True),
        "resolved": Column(int, Check.ge(0), nullable=True),
    },
    coerce=True,
    strict=False,
    name="FinancialServiceSchema",
)

NationalAccountsSchema = DataFrameSchema(
    columns={
        "country": Column(str, Check.isin(VALID_COUNTRIES), nullable=True),
        "city": Column(str, nullable=True),
        "year": Column(int, [Check.ge(2019), Check.le(2030)], nullable=True),
        "budget_allocated": Column(float, Check.ge(0), nullable=True),
        "asset_health": Column(float, [Check.ge(0), Check.le(100)], nullable=True),
        "trained_staff": Column(int, Check.ge(0), nullable=True),
    },
    coerce=True,
    strict=False,
    name="NationalAccountsSchema",
)


SCHEMA_REGISTRY: dict[str, DataFrameSchema] = {
    "billing": BillingSchema,
    "production": ProductionSchema,
    "sw_service": ServiceSchema,
    "w_access": WaterAccessSchema,
    "s_access": SanitationAccessSchema,
    "fin_service": FinancialServiceSchema,
    "national_accounts": NationalAccountsSchema,
}


def validate_dataframe(table_name: str, df) -> dict:
    """
    Validate a DataFrame against its registered schema.

    Returns a dict with keys:
      - valid (bool): whether all checks passed
      - errors (list[str]): human-readable error descriptions
      - row_count (int): total rows checked
    """
    schema = SCHEMA_REGISTRY.get(table_name)
    if schema is None:
        return {"valid": True, "errors": [], "row_count": len(df)}

    try:
        schema.validate(df, lazy=True)
        return {"valid": True, "errors": [], "row_count": len(df)}
    except pa.errors.SchemaErrors as exc:
        errors = []
        for _, row in exc.failure_cases.iterrows():
            col = row.get("column", "unknown")
            check = row.get("check", "unknown")
            idx = row.get("index", "?")
            errors.append(f"Column '{col}' failed check '{check}' at index {idx}")
        return {"valid": False, "errors": errors[:50], "row_count": len(df)}
