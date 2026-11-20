"""Core Payment Reconciliation Engine for PayRecon.

Performs deterministic, explainable reconciliation between platform transactions
and bank settlements using Python's Decimal for financial accuracy.
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any
import pandas as pd

from src.data_validator import (
    validate_transactions,
    validate_settlements,
    ValidationResult,
)


class ReconciliationStatus:
    """Standardized reconciliation classification statuses."""
    MATCHED = "Matched"
    LATE_SETTLEMENT = "Late settlement"
    MISSING_SETTLEMENT = "Missing settlement"
    AMOUNT_MISMATCH = "Amount mismatch"
    DUPLICATE_SETTLEMENT = "Duplicate settlement"
    AGGREGATE_ROUNDING = "Aggregate rounding discrepancy"
    UNMATCHED_REFUND = "Unmatched refund"
    MATCHED_REFUND = "Matched refund"
    UNMATCHED_SETTLEMENT = "Unmatched settlement"
    FAILED_TXN_IGNORED = "Failed transaction (No settlement expected)"
    UNEXPECTED_SETTLEMENT_FAILED_TXN = "Unexpected settlement for failed transaction"
    INVALID_RECORD = "Invalid record"


@dataclass
class ReconciliationItem:
    """Detailed reconciliation record for explorer, reporting, and audit trail."""
    record_id: str
    transaction_id: str
    settlement_id: str | None
    record_type: str  # "TRANSACTION" or "SETTLEMENT"
    platform_amount: Decimal | None
    bank_amount: Decimal | None
    transaction_date: str | None
    settlement_date: str | None
    status: str
    issue_category: str
    difference_amount: Decimal  # Bank - Platform (or discrepancy amount)
    is_discrepancy: bool
    explanation: str
    original_transaction_id: str | None = None
    currency: str = "INR"

    def to_dict(self) -> dict[str, Any]:
        """Convert item to dictionary for DataFrame rendering."""
        return {
            "Record ID": self.record_id,
            "Transaction ID": self.transaction_id,
            "Settlement ID": self.settlement_id or "N/A",
            "Record Type": self.record_type,
            "Platform Amount (INR)": float(self.platform_amount) if self.platform_amount is not None else None,
            "Bank Amount (INR)": float(self.bank_amount) if self.bank_amount is not None else None,
            "Transaction Date": self.transaction_date or "N/A",
            "Settlement Date": self.settlement_date or "N/A",
            "Reconciliation Status": self.status,
            "Issue Category": self.issue_category,
            "Difference (INR)": float(self.difference_amount),
            "Is Discrepancy": self.is_discrepancy,
            "Explanation": self.explanation,
            "Original Txn ID": self.original_transaction_id or "N/A",
        }


@dataclass
class ReconciliationSummary:
    """Financial and operational reconciliation KPI summary."""
    # Counts
    total_platform_transactions: int = 0
    total_bank_settlements: int = 0
    matched_count: int = 0
    late_settlement_count: int = 0
    missing_settlement_count: int = 0
    amount_mismatch_count: int = 0
    rounding_discrepancy_count: int = 0
    duplicate_settlement_count: int = 0
    unmatched_refund_count: int = 0
    matched_refund_count: int = 0
    unmatched_settlement_count: int = 0
    failed_txn_count: int = 0
    invalid_records_count: int = 0
    total_discrepancies_count: int = 0

    # Financial Amounts (in Decimal)
    expected_payment_amount: Decimal = Decimal("0.00")
    actual_valid_settlement_amount: Decimal = Decimal("0.00")
    total_net_difference: Decimal = Decimal("0.00")
    matched_amount: Decimal = Decimal("0.00")
    late_settlement_amount: Decimal = Decimal("0.00")
    missing_settlement_amount: Decimal = Decimal("0.00")
    duplicate_settlement_amount_prevented: Decimal = Decimal("0.00")
    amount_mismatch_diff: Decimal = Decimal("0.00")
    aggregate_rounding_discrepancy: Decimal = Decimal("0.00")
    unmatched_refund_amount: Decimal = Decimal("0.00")
    matched_refund_amount: Decimal = Decimal("0.00")
    unmatched_settlement_amount: Decimal = Decimal("0.00")
    total_refund_amount: Decimal = Decimal("0.00")
    gross_discrepancy_amount: Decimal = Decimal("0.00")

    # Parameters
    rounding_tolerance: Decimal = Decimal("0.05")
    reconciliation_period: str = "November 2026"
    reconciliation_rate_pct: float = 0.0


class ReconciliationEngine:
    """Core reconciliation processor comparing platform transactions and bank settlements."""

    def __init__(
        self,
        rounding_tolerance: Decimal = Decimal("0.05"),
        period_start: str = "2026-11-01",
        period_end: str = "2026-11-30",
    ):
        self.rounding_tolerance = rounding_tolerance
        self.period_start = datetime.strptime(period_start, "%Y-%m-%d").date()
        self.period_end = datetime.strptime(period_end, "%Y-%m-%d").date()

    @staticmethod
    def _to_decimal(val: Any) -> Decimal:
        """Safely convert value to 2-decimal Decimal."""
        if val is None or pd.isna(val):
            return Decimal("0.00")
        try:
            str_val = (
                str(val)
                .strip()
                .replace(",", "")
                .replace("₹", "")
                .replace("INR", "")
                .replace("inr", "")
                .strip()
            )
            return Decimal(str_val).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        except (InvalidOperation, ValueError):
            return Decimal("0.00")

    @staticmethod
    def _parse_date(val: Any) -> date | None:
        """Parse date string to date object."""
        if val is None or pd.isna(val):
            return None
        str_val = str(val).strip()
        date_part = str_val.split("T")[0].split(" ")[0].strip()
        for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y", "%d/%m/%Y"):
            try:
                return datetime.strptime(date_part, fmt).date()
            except ValueError:
                continue
        return None

    def reconcile(
        self,
        df_transactions: pd.DataFrame,
        df_settlements: pd.DataFrame,
        val_txn: ValidationResult | None = None,
        val_set: ValidationResult | None = None,
    ) -> tuple[list[ReconciliationItem], ReconciliationSummary]:
        """Execute full reconciliation analysis."""
        # 1. Run validation if not provided
        if val_txn is None:
            val_txn = validate_transactions(df_transactions)
        if val_set is None:
            val_set = validate_settlements(df_settlements)

        items: list[ReconciliationItem] = []
        summary = ReconciliationSummary(
            rounding_tolerance=self.rounding_tolerance,
            total_platform_transactions=len(df_transactions),
            total_bank_settlements=len(df_settlements),
        )

        # Track invalid row indices
        invalid_txn_indices = val_txn.invalid_row_indices
        invalid_set_indices = val_set.invalid_row_indices

        # Record validation errors as INVALID_RECORD items
        for err in val_txn.errors:
            if err.row_index >= 0 and err.row_index < len(df_transactions):
                row = df_transactions.iloc[err.row_index]
                tid = str(row.get("transaction_id", f"ROW-{err.row_index}"))
                amt = self._to_decimal(row.get("amount", 0))
                items.append(
                    ReconciliationItem(
                        record_id=f"INVALID-TXN-{err.row_index}",
                        transaction_id=tid,
                        settlement_id=None,
                        record_type="TRANSACTION",
                        platform_amount=amt,
                        bank_amount=None,
                        transaction_date=str(row.get("transaction_date", "")),
                        settlement_date=None,
                        status=ReconciliationStatus.INVALID_RECORD,
                        issue_category="Invalid Input Data",
                        difference_amount=amt,
                        is_discrepancy=True,
                        explanation=f"Platform transaction validation failure: {err.message} (Column: {err.column}, Value: '{err.value}')",
                    )
                )
                summary.invalid_records_count += 1

        for err in val_set.errors:
            if err.row_index >= 0 and err.row_index < len(df_settlements):
                row = df_settlements.iloc[err.row_index]
                sid = str(row.get("settlement_id", f"ROW-{err.row_index}"))
                tid = str(row.get("transaction_id", "UNKNOWN"))
                amt = self._to_decimal(row.get("amount", 0))
                items.append(
                    ReconciliationItem(
                        record_id=f"INVALID-SET-{err.row_index}",
                        transaction_id=tid,
                        settlement_id=sid,
                        record_type="SETTLEMENT",
                        platform_amount=None,
                        bank_amount=amt,
                        transaction_date=None,
                        settlement_date=str(row.get("settlement_date", "")),
                        status=ReconciliationStatus.INVALID_RECORD,
                        issue_category="Invalid Input Data",
                        difference_amount=amt,
                        is_discrepancy=True,
                        explanation=f"Bank settlement validation failure: {err.message} (Column: {err.column}, Value: '{err.value}')",
                    )
                )
                summary.invalid_records_count += 1

        # Build lookup maps for valid rows
        # Platform transactions map: transaction_id -> row_dict
        txns_map: dict[str, dict[str, Any]] = {}
        for idx, row in df_transactions.iterrows():
            if idx in invalid_txn_indices:
                continue
            tid = str(row.get("transaction_id", "")).strip()
            if tid:
                txns_map[tid] = {
                    "row_index": idx,
                    "transaction_id": tid,
                    "transaction_date": str(row.get("transaction_date", "")).strip(),
                    "date_obj": self._parse_date(row.get("transaction_date")),
                    "amount": self._to_decimal(row.get("amount")),
                    "status": str(row.get("status", "")).strip().upper(),
                    "currency": str(row.get("currency", "INR")).strip().upper(),
                }

        # Settlements processing:
        # Separate PAYMENT vs REFUND
        # Detect DUPLICATE bank settlements referencing the same transaction_id for PAYMENT
        payments_by_tid: dict[str, list[dict[str, Any]]] = {}
        refunds_list: list[dict[str, Any]] = []

        for idx, row in df_settlements.iterrows():
            if idx in invalid_set_indices:
                continue
            sid = str(row.get("settlement_id", "")).strip()
            tid = str(row.get("transaction_id", "")).strip()
            ttype = str(row.get("transaction_type", "")).strip().upper()
            orig_id = str(row.get("original_transaction_id", "")).strip() if pd.notna(row.get("original_transaction_id")) else ""
            sdate_str = str(row.get("settlement_date", "")).strip()
            sdate_obj = self._parse_date(sdate_str)
            samt = self._to_decimal(row.get("amount"))

            record = {
                "row_index": idx,
                "settlement_id": sid,
                "transaction_id": tid,
                "transaction_type": ttype,
                "original_transaction_id": orig_id,
                "settlement_date": sdate_str,
                "date_obj": sdate_obj,
                "amount": samt,
            }

            if ttype == "REFUND":
                refunds_list.append(record)
            else:
                payments_by_tid.setdefault(tid, []).append(record)

        # 2. Process Bank Duplicate Settlements (Prevent Double-Counting)
        valid_settlements_by_tid: dict[str, dict[str, Any]] = {}
        for tid, s_list in payments_by_tid.items():
            # First settlement is primary; any additional are duplicates
            valid_settlements_by_tid[tid] = s_list[0]
            if len(s_list) > 1:
                for dup in s_list[1:]:
                    dup_amt = dup["amount"]
                    summary.duplicate_settlement_count += 1
                    summary.duplicate_settlement_amount_prevented += dup_amt
                    items.append(
                        ReconciliationItem(
                            record_id=dup["settlement_id"],
                            transaction_id=tid,
                            settlement_id=dup["settlement_id"],
                            record_type="SETTLEMENT",
                            platform_amount=txns_map[tid]["amount"] if tid in txns_map else None,
                            bank_amount=dup_amt,
                            transaction_date=txns_map[tid]["transaction_date"] if tid in txns_map else None,
                            settlement_date=dup["settlement_date"],
                            status=ReconciliationStatus.DUPLICATE_SETTLEMENT,
                            issue_category="Duplicate Bank Settlement",
                            difference_amount=dup_amt,
                            is_discrepancy=True,
                            explanation=(
                                f"Duplicate settlement {dup['settlement_id']} detected for transaction {tid}. "
                                f"Primary settlement {s_list[0]['settlement_id']} already accounted for. "
                                f"Duplicate amount ₹{dup_amt} excluded to prevent double-counting."
                            ),
                        )
                    )

        # 3. Process Bank Refunds
        for ref in refunds_list:
            orig_id = ref["original_transaction_id"]
            ref_amt = ref["amount"]
            summary.total_refund_amount += ref_amt

            if not orig_id or orig_id not in txns_map:
                # Planted Anomaly D: UNMATCHED REFUND (Orphan refund)
                summary.unmatched_refund_count += 1
                summary.unmatched_refund_amount += ref_amt
                items.append(
                    ReconciliationItem(
                        record_id=ref["settlement_id"],
                        transaction_id=ref["transaction_id"],
                        settlement_id=ref["settlement_id"],
                        record_type="SETTLEMENT",
                        platform_amount=None,
                        bank_amount=ref_amt,
                        transaction_date=None,
                        settlement_date=ref["settlement_date"],
                        status=ReconciliationStatus.UNMATCHED_REFUND,
                        issue_category="Unmatched Bank Refund (Orphan)",
                        difference_amount=ref_amt,
                        is_discrepancy=True,
                        explanation=(
                            f"Bank refund {ref['settlement_id']} references original_transaction_id '{orig_id}', "
                            f"which does not exist in platform transaction records. Flagged as an orphan refund."
                        ),
                        original_transaction_id=orig_id,
                    )
                )
            else:
                # Valid Matched Refund referencing an existing transaction
                orig_txn = txns_map[orig_id]
                summary.matched_refund_count += 1
                summary.matched_refund_amount += ref_amt
                items.append(
                    ReconciliationItem(
                        record_id=ref["settlement_id"],
                        transaction_id=ref["transaction_id"],
                        settlement_id=ref["settlement_id"],
                        record_type="SETTLEMENT",
                        platform_amount=orig_txn["amount"],
                        bank_amount=ref_amt,
                        transaction_date=orig_txn["transaction_date"],
                        settlement_date=ref["settlement_date"],
                        status=ReconciliationStatus.MATCHED_REFUND,
                        issue_category="Matched Bank Refund",
                        difference_amount=Decimal("0.00"),
                        is_discrepancy=False,
                        explanation=(
                            f"Bank refund {ref['settlement_id']} successfully reconciled with original "
                            f"platform transaction {orig_id} (dated {orig_txn['transaction_date']}). "
                            f"Reported separately from gross payment settlements."
                        ),
                        original_transaction_id=orig_id,
                    )
                )

        # 4. Process Platform Transactions
        # Separate FAILED vs SUCCESS
        for tid, txn in txns_map.items():
            t_status = txn["status"]
            t_amt = txn["amount"]
            t_date = txn["transaction_date"]
            t_date_obj = txn["date_obj"]

            settlement = valid_settlements_by_tid.get(tid)

            # Failed platform payments
            if t_status == "FAILED":
                summary.failed_txn_count += 1
                if settlement is not None:
                    # Anomaly: Bank settled a failed transaction!
                    s_amt = settlement["amount"]
                    items.append(
                        ReconciliationItem(
                            record_id=f"REC-{tid}",
                            transaction_id=tid,
                            settlement_id=settlement["settlement_id"],
                            record_type="TRANSACTION",
                            platform_amount=t_amt,
                            bank_amount=s_amt,
                            transaction_date=t_date,
                            settlement_date=settlement["settlement_date"],
                            status=ReconciliationStatus.UNEXPECTED_SETTLEMENT_FAILED_TXN,
                            issue_category="Unexpected Settlement for Failed Transaction",
                            difference_amount=s_amt,
                            is_discrepancy=True,
                            explanation=(
                                f"Platform marked transaction {tid} as FAILED, but bank settled ₹{s_amt} "
                                f"under settlement {settlement['settlement_id']}."
                            ),
                        )
                    )
                else:
                    # Normal: Failed payment has no bank settlement. Not an obligation.
                    items.append(
                        ReconciliationItem(
                            record_id=f"REC-{tid}",
                            transaction_id=tid,
                            settlement_id=None,
                            record_type="TRANSACTION",
                            platform_amount=t_amt,
                            bank_amount=None,
                            transaction_date=t_date,
                            settlement_date=None,
                            status=ReconciliationStatus.FAILED_TXN_IGNORED,
                            issue_category="Failed Payment (No Obligation)",
                            difference_amount=Decimal("0.00"),
                            is_discrepancy=False,
                            explanation="Platform payment failed. Excluded from expected settlement obligations.",
                        )
                    )
                continue

            # Successful platform payments
            summary.expected_payment_amount += t_amt

            if settlement is None:
                # Planted Scenario: MISSING SETTLEMENT
                summary.missing_settlement_count += 1
                summary.missing_settlement_amount += t_amt
                items.append(
                    ReconciliationItem(
                        record_id=f"REC-{tid}",
                        transaction_id=tid,
                        settlement_id=None,
                        record_type="TRANSACTION",
                        platform_amount=t_amt,
                        bank_amount=None,
                        transaction_date=t_date,
                        settlement_date=None,
                        status=ReconciliationStatus.MISSING_SETTLEMENT,
                        issue_category="Missing Bank Settlement",
                        difference_amount=-t_amt,
                        is_discrepancy=True,
                        explanation=(
                            f"Platform recorded successful payment of ₹{t_amt} on {t_date}, "
                            f"but no bank settlement was received."
                        ),
                    )
                )
                continue

            # Settlement exists: check timing & amount
            s_amt = settlement["amount"]
            s_date = settlement["settlement_date"]
            s_date_obj = settlement["date_obj"]
            s_id = settlement["settlement_id"]
            diff = s_amt - t_amt

            # Check if settled in December 2026 or later (Planted Anomaly A: LATE SETTLEMENT)
            is_settled_in_current_period = (
                s_date_obj is not None and s_date_obj <= self.period_end
            )

            if not is_settled_in_current_period:
                summary.late_settlement_count += 1
                summary.late_settlement_amount += t_amt
                items.append(
                    ReconciliationItem(
                        record_id=f"REC-{tid}",
                        transaction_id=tid,
                        settlement_id=s_id,
                        record_type="TRANSACTION",
                        platform_amount=t_amt,
                        bank_amount=s_amt,
                        transaction_date=t_date,
                        settlement_date=s_date,
                        status=ReconciliationStatus.LATE_SETTLEMENT,
                        issue_category="Timing Difference (Late Settlement)",
                        difference_amount=diff,
                        is_discrepancy=True,
                        explanation=(
                            f"November transaction ({t_date}) was settled on {s_date} (December 2026). "
                            f"Classified as a timing difference across the month-end cutoff, not permanently missing."
                        ),
                    )
                )
                continue

            # Settled within November 2026: Compare amounts
            summary.actual_valid_settlement_amount += s_amt

            if diff == Decimal("0.00"):
                # Exact match
                summary.matched_count += 1
                summary.matched_amount += t_amt
                items.append(
                    ReconciliationItem(
                        record_id=f"REC-{tid}",
                        transaction_id=tid,
                        settlement_id=s_id,
                        record_type="TRANSACTION",
                        platform_amount=t_amt,
                        bank_amount=s_amt,
                        transaction_date=t_date,
                        settlement_date=s_date,
                        status=ReconciliationStatus.MATCHED,
                        issue_category="Matched",
                        difference_amount=Decimal("0.00"),
                        is_discrepancy=False,
                        explanation=f"Fully reconciled. Platform amount matches bank settlement on {s_date}.",
                    )
                )
            elif abs(diff) <= self.rounding_tolerance:
                # Planted Anomaly B: ROUNDING DIFFERENCE (Within tolerance)
                summary.rounding_discrepancy_count += 1
                summary.aggregate_rounding_discrepancy += diff
                summary.matched_amount += s_amt
                items.append(
                    ReconciliationItem(
                        record_id=f"REC-{tid}",
                        transaction_id=tid,
                        settlement_id=s_id,
                        record_type="TRANSACTION",
                        platform_amount=t_amt,
                        bank_amount=s_amt,
                        transaction_date=t_date,
                        settlement_date=s_date,
                        status=ReconciliationStatus.AGGREGATE_ROUNDING,
                        issue_category="Rounding Difference",
                        difference_amount=diff,
                        is_discrepancy=True,
                        explanation=(
                            f"Individual difference of ₹{diff:+.2f} is within rounding tolerance (₹{self.rounding_tolerance}). "
                            f"Contributes to aggregate rounding difference."
                        ),
                    )
                )
            else:
                # Amount Mismatch (Exceeds tolerance)
                summary.amount_mismatch_count += 1
                summary.amount_mismatch_diff += diff
                items.append(
                    ReconciliationItem(
                        record_id=f"REC-{tid}",
                        transaction_id=tid,
                        settlement_id=s_id,
                        record_type="TRANSACTION",
                        platform_amount=t_amt,
                        bank_amount=s_amt,
                        transaction_date=t_date,
                        settlement_date=s_date,
                        status=ReconciliationStatus.AMOUNT_MISMATCH,
                        issue_category="Amount Mismatch",
                        difference_amount=diff,
                        is_discrepancy=True,
                        explanation=(
                            f"Platform amount ₹{t_amt} differs from bank settlement ₹{s_amt} by ₹{diff:+.2f}, "
                            f"which exceeds the configured tolerance of ₹{self.rounding_tolerance}."
                        ),
                    )
                )

        # 5. Check for Bank Settlements referencing non-existent platform transactions (Unmatched payment settlements)
        for tid, s_record in valid_settlements_by_tid.items():
            if tid not in txns_map:
                s_amt = s_record["amount"]
                summary.unmatched_settlement_count += 1
                summary.unmatched_settlement_amount += s_amt
                items.append(
                    ReconciliationItem(
                        record_id=s_record["settlement_id"],
                        transaction_id=tid,
                        settlement_id=s_record["settlement_id"],
                        record_type="SETTLEMENT",
                        platform_amount=None,
                        bank_amount=s_amt,
                        transaction_date=None,
                        settlement_date=s_record["settlement_date"],
                        status=ReconciliationStatus.UNMATCHED_SETTLEMENT,
                        issue_category="Unmatched Bank Settlement",
                        difference_amount=s_amt,
                        is_discrepancy=True,
                        explanation=(
                            f"Bank settlement {s_record['settlement_id']} references transaction ID '{tid}', "
                            f"which does not exist in platform transactions."
                        ),
                    )
                )

        # 6. Final Financial Aggregates
        summary.total_net_difference = (
            summary.expected_payment_amount - summary.actual_valid_settlement_amount
        )
        summary.total_discrepancies_count = sum(1 for item in items if item.is_discrepancy)

        # Gross discrepancy amount
        summary.gross_discrepancy_amount = (
            summary.missing_settlement_amount
            + summary.late_settlement_amount
            + abs(summary.amount_mismatch_diff)
            + abs(summary.aggregate_rounding_discrepancy)
            + summary.duplicate_settlement_amount_prevented
            + summary.unmatched_refund_amount
            + summary.unmatched_settlement_amount
        )

        # Reconciliation Rate: Matched / Total Expected Transactions
        eligible_txns = summary.total_platform_transactions - summary.failed_txn_count - summary.invalid_records_count
        if eligible_txns > 0:
            summary.reconciliation_rate_pct = round(
                ((summary.matched_count + summary.rounding_discrepancy_count) / eligible_txns) * 100,
                2,
            )

        return items, summary

