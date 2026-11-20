"""Data validation module for PayRecon.

Performs robust schema and business-rule validation on uploaded or generated
CSV datasets without silently modifying or discarding invalid records.
"""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any
import pandas as pd


@dataclass
class ValidationError:
    """Details of a single validation error."""
    row_index: int
    column: str
    value: Any
    message: str
    severity: str = "ERROR"  # "ERROR" or "WARNING"


@dataclass
class ValidationResult:
    """Complete validation results for a dataset."""
    dataset_name: str
    is_valid: bool
    total_rows: int
    valid_rows_count: int
    invalid_rows_count: int
    errors: list[ValidationError] = field(default_factory=list)
    invalid_row_indices: set[int] = field(default_factory=set)

    def summary(self) -> str:
        """Human-readable summary of validation."""
        if self.is_valid:
            return f"✓ {self.dataset_name}: All {self.total_rows} records passed validation."
        return (
            f"⚠ {self.dataset_name}: {len(self.errors)} issue(s) detected across "
            f"{self.invalid_rows_count} invalid record(s) out of {self.total_rows} total rows."
        )


REQUIRED_TRANSACTION_COLUMNS = [
    "transaction_id",
    "transaction_date",
    "amount",
    "status",
    "currency",
]

REQUIRED_SETTLEMENT_COLUMNS = [
    "settlement_id",
    "transaction_id",
    "settlement_date",
    "amount",
    "transaction_type",
    "original_transaction_id",
]

SUPPORTED_CURRENCIES = {"INR"}
VALID_TXN_STATUSES = {"SUCCESS", "FAILED"}
VALID_SETTLEMENT_TYPES = {"PAYMENT", "REFUND"}


def _parse_decimal(val: Any) -> tuple[Decimal | None, str | None]:
    """Safely parse value to Decimal; returns (Decimal, error_msg)."""
    if val is None or pd.isna(val):
        return None, "Amount is missing or null"
    str_val = (
        str(val)
        .strip()
        .replace(",", "")
        .replace("₹", "")
        .replace("INR", "")
        .replace("inr", "")
        .strip()
    )
    if not str_val:
        return None, "Amount is empty"
    try:
        dec = Decimal(str_val)
        if dec <= Decimal("0"):
            return None, f"Amount must be strictly positive (got {str_val})"
        return dec, None
    except (InvalidOperation, ValueError):
        return None, f"Amount '{str_val}' is not a valid decimal number"


def _parse_date(val: Any) -> tuple[datetime | None, str | None]:
    """Safely parse value to ISO date (YYYY-MM-DD); returns (date, error_msg)."""
    if val is None or pd.isna(val):
        return None, "Date is missing or null"
    str_val = str(val).strip()
    if not str_val:
        return None, "Date is empty"
    # Normalize string by removing time portion if present
    date_part = str_val.split("T")[0].split(" ")[0].strip()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            parsed = datetime.strptime(date_part, fmt)
            return parsed, None
        except ValueError:
            continue
    return None, f"Date '{str_val}' does not match expected format (YYYY-MM-DD)"


def validate_transactions(df: pd.DataFrame) -> ValidationResult:
    """Validate platform transactions DataFrame against business rules."""
    dataset_name = "Platform Transactions"
    errors: list[ValidationError] = []
    invalid_indices: set[int] = set()

    # 1. Required Columns Check
    missing_cols = [c for c in REQUIRED_TRANSACTION_COLUMNS if c not in df.columns]
    if missing_cols:
        errors.append(
            ValidationError(
                row_index=-1,
                column="columns",
                value=list(df.columns),
                message=f"Missing required columns: {missing_cols}",
            )
        )
        return ValidationResult(
            dataset_name=dataset_name,
            is_valid=False,
            total_rows=len(df),
            valid_rows_count=0,
            invalid_rows_count=len(df),
            errors=errors,
            invalid_row_indices=set(range(len(df))),
        )

    # 2. Duplicate Transaction ID check
    seen_ids: dict[str, int] = {}
    for idx, row in df.iterrows():
        txn_id = row.get("transaction_id")
        if pd.notna(txn_id) and str(txn_id).strip():
            str_id = str(txn_id).strip()
            if str_id in seen_ids:
                errors.append(
                    ValidationError(
                        row_index=int(idx),
                        column="transaction_id",
                        value=str_id,
                        message=f"Duplicate transaction_id '{str_id}' (first seen at row {seen_ids[str_id]})",
                    )
                )
                invalid_indices.add(int(idx))
            else:
                seen_ids[str_id] = int(idx)

    # 3. Row-by-row field validation
    for idx, row in df.iterrows():
        row_idx = int(idx)
        # Check transaction_id
        tid = row.get("transaction_id")
        if pd.isna(tid) or not str(tid).strip():
            errors.append(
                ValidationError(
                    row_index=row_idx,
                    column="transaction_id",
                    value=tid,
                    message="Missing or blank transaction_id",
                )
            )
            invalid_indices.add(row_idx)

        # Check transaction_date
        tdate = row.get("transaction_date")
        _, d_err = _parse_date(tdate)
        if d_err:
            errors.append(
                ValidationError(
                    row_index=row_idx,
                    column="transaction_date",
                    value=tdate,
                    message=d_err,
                )
            )
            invalid_indices.add(row_idx)

        # Check amount
        tamt = row.get("amount")
        _, a_err = _parse_decimal(tamt)
        if a_err:
            errors.append(
                ValidationError(
                    row_index=row_idx,
                    column="amount",
                    value=tamt,
                    message=a_err,
                )
            )
            invalid_indices.add(row_idx)

        # Check status
        tstatus = row.get("status")
        if pd.isna(tstatus) or str(tstatus).strip().upper() not in VALID_TXN_STATUSES:
            errors.append(
                ValidationError(
                    row_index=row_idx,
                    column="status",
                    value=tstatus,
                    message=f"Invalid transaction status '{tstatus}'. Expected one of {VALID_TXN_STATUSES}",
                )
            )
            invalid_indices.add(row_idx)

        # Check currency
        tcurr = row.get("currency")
        if pd.isna(tcurr) or str(tcurr).strip().upper() not in SUPPORTED_CURRENCIES:
            errors.append(
                ValidationError(
                    row_index=row_idx,
                    column="currency",
                    value=tcurr,
                    message=f"Unsupported currency '{tcurr}'. Expected {SUPPORTED_CURRENCIES}",
                )
            )
            invalid_indices.add(row_idx)

    valid_count = len(df) - len(invalid_indices)
    return ValidationResult(
        dataset_name=dataset_name,
        is_valid=len(errors) == 0,
        total_rows=len(df),
        valid_rows_count=valid_count,
        invalid_rows_count=len(invalid_indices),
        errors=errors,
        invalid_row_indices=invalid_indices,
    )


def validate_settlements(df: pd.DataFrame) -> ValidationResult:
    """Validate bank settlements DataFrame against business rules."""
    dataset_name = "Bank Settlements"
    errors: list[ValidationError] = []
    invalid_indices: set[int] = set()

    # 1. Required Columns Check
    missing_cols = [c for c in REQUIRED_SETTLEMENT_COLUMNS if c not in df.columns]
    if missing_cols:
        errors.append(
            ValidationError(
                row_index=-1,
                column="columns",
                value=list(df.columns),
                message=f"Missing required columns: {missing_cols}",
            )
        )
        return ValidationResult(
            dataset_name=dataset_name,
            is_valid=False,
            total_rows=len(df),
            valid_rows_count=0,
            invalid_rows_count=len(df),
            errors=errors,
            invalid_row_indices=set(range(len(df))),
        )

    # 2. Duplicate settlement_id check (strictly identical settlement record)
    seen_settle_ids: dict[str, int] = {}
    for idx, row in df.iterrows():
        sid = row.get("settlement_id")
        if pd.notna(sid) and str(sid).strip():
            str_sid = str(sid).strip()
            if str_sid in seen_settle_ids:
                errors.append(
                    ValidationError(
                        row_index=int(idx),
                        column="settlement_id",
                        value=str_sid,
                        message=f"Duplicate settlement_id '{str_sid}' (first seen at row {seen_settle_ids[str_sid]})",
                    )
                )
                invalid_indices.add(int(idx))
            else:
                seen_settle_ids[str_sid] = int(idx)

    # 3. Row-by-row field validation
    for idx, row in df.iterrows():
        row_idx = int(idx)
        # Check settlement_id
        sid = row.get("settlement_id")
        if pd.isna(sid) or not str(sid).strip():
            errors.append(
                ValidationError(
                    row_index=row_idx,
                    column="settlement_id",
                    value=sid,
                    message="Missing or blank settlement_id",
                )
            )
            invalid_indices.add(row_idx)

        # Check transaction_id (for payments, required)
        tid = row.get("transaction_id")
        ttype = str(row.get("transaction_type", "")).strip().upper()
        if ttype == "PAYMENT" and (pd.isna(tid) or not str(tid).strip()):
            errors.append(
                ValidationError(
                    row_index=row_idx,
                    column="transaction_id",
                    value=tid,
                    message="Missing or blank transaction_id for PAYMENT settlement",
                )
            )
            invalid_indices.add(row_idx)

        # Check settlement_date
        sdate = row.get("settlement_date")
        _, d_err = _parse_date(sdate)
        if d_err:
            errors.append(
                ValidationError(
                    row_index=row_idx,
                    column="settlement_date",
                    value=sdate,
                    message=d_err,
                )
            )
            invalid_indices.add(row_idx)

        # Check amount
        samt = row.get("amount")
        _, a_err = _parse_decimal(samt)
        if a_err:
            errors.append(
                ValidationError(
                    row_index=row_idx,
                    column="amount",
                    value=samt,
                    message=a_err,
                )
            )
            invalid_indices.add(row_idx)

        # Check transaction_type
        if pd.isna(ttype) or ttype not in VALID_SETTLEMENT_TYPES:
            errors.append(
                ValidationError(
                    row_index=row_idx,
                    column="transaction_type",
                    value=row.get("transaction_type"),
                    message=f"Invalid transaction_type '{row.get('transaction_type')}'. Expected {VALID_SETTLEMENT_TYPES}",
                )
            )
            invalid_indices.add(row_idx)

        # Check refund original_transaction_id
        if ttype == "REFUND":
            orig_id = row.get("original_transaction_id")
            if pd.isna(orig_id) or not str(orig_id).strip():
                errors.append(
                    ValidationError(
                        row_index=row_idx,
                        column="original_transaction_id",
                        value=orig_id,
                        message="Refund records must specify an original_transaction_id",
                    )
                )
                invalid_indices.add(row_idx)

    valid_count = len(df) - len(invalid_indices)
    return ValidationResult(
        dataset_name=dataset_name,
        is_valid=len(errors) == 0,
        total_rows=len(df),
        valid_rows_count=valid_count,
        invalid_rows_count=len(invalid_indices),
        errors=errors,
        invalid_row_indices=invalid_indices,
    )

