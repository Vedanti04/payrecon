"""Automated test suite for PayRecon Reconciliation Engine.

Explicitly verifies:
1. Exact matching transaction
2. Late settlement (Mandatory Anomaly A)
3. Aggregate rounding discrepancy (Mandatory Anomaly B)
4. Duplicate bank entry prevention (Mandatory Anomaly C)
5. Unmatched orphan refund (Mandatory Anomaly D)
6. Missing settlement detection
7. Amount mismatch exceeding tolerance
8. Failed platform transaction handling
9. Invalid input data validation & error handling
10. Full dataset end-to-end reconciliation
"""

from decimal import Decimal
import pandas as pd
import pytest

from src.data_generator import generate_datasets
from src.data_validator import validate_transactions, validate_settlements
from src.reconciliation import (
    ReconciliationEngine,
    ReconciliationStatus,
)


@pytest.fixture
def empty_engine():
    """Default reconciliation engine for November 2026."""
    return ReconciliationEngine(
        rounding_tolerance=Decimal("0.05"),
        period_start="2026-11-01",
        period_end="2026-11-30",
    )


def test_exact_matching_transaction(empty_engine):
    """Test standard 1:1 matching transaction with exact amounts in November."""
    df_txn = pd.DataFrame([
        {
            "transaction_id": "TXN-001",
            "transaction_date": "2026-11-05",
            "amount": "1000.00",
            "status": "SUCCESS",
            "currency": "INR",
        }
    ])
    df_settle = pd.DataFrame([
        {
            "settlement_id": "SET-001",
            "transaction_id": "TXN-001",
            "settlement_date": "2026-11-07",
            "amount": "1000.00",
            "transaction_type": "PAYMENT",
            "original_transaction_id": "",
        }
    ])

    items, summary = empty_engine.reconcile(df_txn, df_settle)

    assert summary.matched_count == 1
    assert summary.matched_amount == Decimal("1000.00")
    assert summary.expected_payment_amount == Decimal("1000.00")
    assert summary.actual_valid_settlement_amount == Decimal("1000.00")
    assert summary.total_net_difference == Decimal("0.00")

    match_item = [it for it in items if it.transaction_id == "TXN-001"][0]
    assert match_item.status == ReconciliationStatus.MATCHED
    assert match_item.is_discrepancy is False
    assert match_item.difference_amount == Decimal("0.00")


def test_anomaly_a_late_settlement(empty_engine):
    """Mandatory Anomaly A: November successful transaction settled in December 2026.

    Must be classified as Late settlement (timing difference), NOT permanently missing.
    """
    df_txn = pd.DataFrame([
        {
            "transaction_id": "TXN-NOV-LATE",
            "transaction_date": "2026-11-29",
            "amount": "14500.00",
            "status": "SUCCESS",
            "currency": "INR",
        }
    ])
    df_settle = pd.DataFrame([
        {
            "settlement_id": "SET-DEC-LATE",
            "transaction_id": "TXN-NOV-LATE",
            "settlement_date": "2026-12-02",
            "amount": "14500.00",
            "transaction_type": "PAYMENT",
            "original_transaction_id": "",
        }
    ])

    items, summary = empty_engine.reconcile(df_txn, df_settle)

    assert summary.late_settlement_count == 1
    assert summary.late_settlement_amount == Decimal("14500.00")
    # Not missing!
    assert summary.missing_settlement_count == 0

    item = [it for it in items if it.transaction_id == "TXN-NOV-LATE"][0]
    assert item.status == ReconciliationStatus.LATE_SETTLEMENT
    assert item.issue_category == "Timing Difference (Late Settlement)"
    assert "timing difference" in item.explanation.lower()
    assert item.is_discrepancy is True


def test_anomaly_b_aggregate_rounding_discrepancy(empty_engine):
    """Mandatory Anomaly B: Multiple transactions with small individual rounding diffs.

    Individual differences <= tolerance (0.05), but aggregate difference is tracked and detectable.
    """
    df_txn = pd.DataFrame([
        {"transaction_id": "TXN-R1", "transaction_date": "2026-11-04", "amount": "2500.50", "status": "SUCCESS", "currency": "INR"},
        {"transaction_id": "TXN-R2", "transaction_date": "2026-11-09", "amount": "4120.75", "status": "SUCCESS", "currency": "INR"},
        {"transaction_id": "TXN-R3", "transaction_date": "2026-11-15", "amount": "890.30", "status": "SUCCESS", "currency": "INR"},
    ])
    df_settle = pd.DataFrame([
        {"settlement_id": "SET-R1", "transaction_id": "TXN-R1", "settlement_date": "2026-11-06", "amount": "2500.49", "transaction_type": "PAYMENT", "original_transaction_id": ""},
        {"settlement_id": "SET-R2", "transaction_id": "TXN-R2", "settlement_date": "2026-11-11", "amount": "4120.73", "transaction_type": "PAYMENT", "original_transaction_id": ""},
        {"settlement_id": "SET-R3", "transaction_id": "TXN-R3", "settlement_date": "2026-11-17", "amount": "890.29", "transaction_type": "PAYMENT", "original_transaction_id": ""},
    ])

    items, summary = empty_engine.reconcile(df_txn, df_settle)

    assert summary.rounding_discrepancy_count == 3
    # Expected aggregate diff: (-0.01) + (-0.02) + (-0.01) = -0.04
    assert summary.aggregate_rounding_discrepancy == Decimal("-0.04")

    for item in items:
        if item.transaction_id.startswith("TXN-R"):
            assert item.status == ReconciliationStatus.AGGREGATE_ROUNDING
            assert "within rounding tolerance" in item.explanation.lower()


def test_anomaly_c_duplicate_bank_entry(empty_engine):
    """Mandatory Anomaly C: Duplicated bank settlement entry referencing an existing transaction.

    Engine must detect duplicate entry and prevent double-counting.
    """
    df_txn = pd.DataFrame([
        {
            "transaction_id": "TXN-DUP-01",
            "transaction_date": "2026-11-08",
            "amount": "7800.00",
            "status": "SUCCESS",
            "currency": "INR",
        }
    ])
    df_settle = pd.DataFrame([
        {
            "settlement_id": "SET-DUP-01A",
            "transaction_id": "TXN-DUP-01",
            "settlement_date": "2026-11-10",
            "amount": "7800.00",
            "transaction_type": "PAYMENT",
            "original_transaction_id": "",
        },
        {
            "settlement_id": "SET-DUP-01B",
            "transaction_id": "TXN-DUP-01",
            "settlement_date": "2026-11-10",
            "amount": "7800.00",
            "transaction_type": "PAYMENT",
            "original_transaction_id": "",
        },
    ])

    items, summary = empty_engine.reconcile(df_txn, df_settle)

    assert summary.duplicate_settlement_count == 1
    assert summary.duplicate_settlement_amount_prevented == Decimal("7800.00")
    # Verify settlement was counted only once in actual valid settlement amount!
    assert summary.actual_valid_settlement_amount == Decimal("7800.00")
    assert summary.expected_payment_amount == Decimal("7800.00")
    assert summary.total_net_difference == Decimal("0.00")

    dup_items = [it for it in items if it.status == ReconciliationStatus.DUPLICATE_SETTLEMENT]
    assert len(dup_items) == 1
    assert "prevent double-counting" in dup_items[0].explanation.lower()


def test_anomaly_d_unmatched_refund(empty_engine):
    """Mandatory Anomaly D: Bank refund referencing an original transaction ID not in transactions.

    Flagged as orphan refund.
    """
    df_txn = pd.DataFrame([
        {
            "transaction_id": "TXN-VALID-01",
            "transaction_date": "2026-11-01",
            "amount": "2000.00",
            "status": "SUCCESS",
            "currency": "INR",
        }
    ])
    df_settle = pd.DataFrame([
        {
            "settlement_id": "SET-REF-GHOST",
            "transaction_id": "REF-ORPHAN-01",
            "settlement_date": "2026-11-15",
            "amount": "3200.00",
            "transaction_type": "REFUND",
            "original_transaction_id": "TXN-NON-EXISTENT-ID",
        }
    ])

    items, summary = empty_engine.reconcile(df_txn, df_settle)

    assert summary.unmatched_refund_count == 1
    assert summary.unmatched_refund_amount == Decimal("3200.00")

    orphan_items = [it for it in items if it.status == ReconciliationStatus.UNMATCHED_REFUND]
    assert len(orphan_items) == 1
    assert orphan_items[0].original_transaction_id == "TXN-NON-EXISTENT-ID"
    assert "orphan" in orphan_items[0].explanation.lower()


def test_missing_settlement(empty_engine):
    """Test successful platform payment with no bank settlement."""
    df_txn = pd.DataFrame([
        {
            "transaction_id": "TXN-MISS-01",
            "transaction_date": "2026-11-18",
            "amount": "9500.00",
            "status": "SUCCESS",
            "currency": "INR",
        }
    ])
    df_settle = pd.DataFrame(columns=[
        "settlement_id", "transaction_id", "settlement_date", "amount", "transaction_type", "original_transaction_id"
    ])

    items, summary = empty_engine.reconcile(df_txn, df_settle)

    assert summary.missing_settlement_count == 1
    assert summary.missing_settlement_amount == Decimal("9500.00")
    assert summary.total_net_difference == Decimal("9500.00")

    item = [it for it in items if it.transaction_id == "TXN-MISS-01"][0]
    assert item.status == ReconciliationStatus.MISSING_SETTLEMENT
    assert item.is_discrepancy is True


def test_amount_mismatch_exceeding_tolerance(empty_engine):
    """Test transaction where difference exceeds configurable tolerance."""
    df_txn = pd.DataFrame([
        {
            "transaction_id": "TXN-MISMATCH",
            "transaction_date": "2026-11-12",
            "amount": "12000.00",
            "status": "SUCCESS",
            "currency": "INR",
        }
    ])
    df_settle = pd.DataFrame([
        {
            "settlement_id": "SET-MISMATCH",
            "transaction_id": "TXN-MISMATCH",
            "settlement_date": "2026-11-14",
            "amount": "11500.00",
            "transaction_type": "PAYMENT",
            "original_transaction_id": "",
        }
    ])

    items, summary = empty_engine.reconcile(df_txn, df_settle)

    assert summary.amount_mismatch_count == 1
    assert summary.amount_mismatch_diff == Decimal("-500.00")

    item = [it for it in items if it.transaction_id == "TXN-MISMATCH"][0]
    assert item.status == ReconciliationStatus.AMOUNT_MISMATCH
    assert "exceeds" in item.explanation.lower()


def test_failed_platform_transaction_handling(empty_engine):
    """Test that failed platform payments are NOT treated as payment obligations."""
    df_txn = pd.DataFrame([
        {
            "transaction_id": "TXN-FAILED-01",
            "transaction_date": "2026-11-06",
            "amount": "3100.00",
            "status": "FAILED",
            "currency": "INR",
        }
    ])
    df_settle = pd.DataFrame(columns=[
        "settlement_id", "transaction_id", "settlement_date", "amount", "transaction_type", "original_transaction_id"
    ])

    items, summary = empty_engine.reconcile(df_txn, df_settle)

    assert summary.failed_txn_count == 1
    # Expected payment amount must be 0 (failed payment is not an obligation)
    assert summary.expected_payment_amount == Decimal("0.00")
    assert summary.missing_settlement_count == 0

    item = [it for it in items if it.transaction_id == "TXN-FAILED-01"][0]
    assert item.status == ReconciliationStatus.FAILED_TXN_IGNORED
    assert item.is_discrepancy is False


def test_invalid_input_data_validation(empty_engine):
    """Test validator detection of invalid data (missing IDs, negative amount, bad currency)."""
    df_txn = pd.DataFrame([
        {
            "transaction_id": "",  # Missing ID
            "transaction_date": "2026-11-01",
            "amount": "-500.00",   # Negative amount
            "status": "UNKNOWN",   # Invalid status
            "currency": "USD",     # Unsupported currency
        }
    ])
    df_settle = pd.DataFrame([
        {
            "settlement_id": "SET-001",
            "transaction_id": "TXN-001",
            "settlement_date": "not-a-date",  # Bad date
            "amount": "abc",                 # Non-numeric
            "transaction_type": "DEPOSIT",    # Invalid type
            "original_transaction_id": "",
        }
    ])

    val_txn = validate_transactions(df_txn)
    val_set = validate_settlements(df_settle)

    assert val_txn.is_valid is False
    assert val_set.is_valid is False
    assert len(val_txn.errors) >= 3
    assert len(val_set.errors) >= 2

    # Verify reconciliation engine handles them as INVALID_RECORD without crashing or discarding
    items, summary = empty_engine.reconcile(df_txn, df_settle, val_txn, val_set)
    assert summary.invalid_records_count > 0
    invalid_items = [it for it in items if it.status == ReconciliationStatus.INVALID_RECORD]
    assert len(invalid_items) > 0


def test_unmatched_bank_settlement(empty_engine):
    """Test bank settlement referencing a transaction ID absent from platform transactions."""
    df_txn = pd.DataFrame([
        {
            "transaction_id": "TXN-KNOWN-01",
            "transaction_date": "2026-11-05",
            "amount": "1000.00",
            "status": "SUCCESS",
            "currency": "INR",
        }
    ])
    df_settle = pd.DataFrame([
        {
            "settlement_id": "SET-ORPHAN-SETTLE",
            "transaction_id": "TXN-UNKNOWN-999",
            "settlement_date": "2026-11-07",
            "amount": "2500.00",
            "transaction_type": "PAYMENT",
            "original_transaction_id": "",
        }
    ])

    items, summary = empty_engine.reconcile(df_txn, df_settle)
    assert summary.unmatched_settlement_count == 1
    assert summary.unmatched_settlement_amount == Decimal("2500.00")
    unmatched = [it for it in items if it.status == ReconciliationStatus.UNMATCHED_SETTLEMENT]
    assert len(unmatched) == 1
    assert unmatched[0].transaction_id == "TXN-UNKNOWN-999"


def test_full_synthetic_dataset_reconciliation(tmp_path):
    """Test full reconciliation on generated synthetic dataset with all planted anomalies."""
    out_dir = str(tmp_path / "data")
    t_path, s_path = generate_datasets(output_dir=out_dir, seed=42)

    df_t = pd.read_csv(t_path)
    df_s = pd.read_csv(s_path)

    engine = ReconciliationEngine(rounding_tolerance=Decimal("0.05"))
    items, summary = engine.reconcile(df_t, df_s)

    # All 4 mandatory anomalies must be detected
    assert summary.late_settlement_count >= 1, "Anomaly A (Late Settlement) not detected"
    assert summary.rounding_discrepancy_count >= 5, "Anomaly B (Rounding Diff) not detected"
    assert summary.duplicate_settlement_count >= 1, "Anomaly C (Duplicate Settlement) not detected"
    assert summary.unmatched_refund_count >= 1, "Anomaly D (Unmatched Refund) not detected"

    # Additional scenarios
    assert summary.missing_settlement_count >= 1, "Missing settlement not detected"
    assert summary.amount_mismatch_count >= 1, "Amount mismatch not detected"
    assert summary.matched_refund_count >= 1, "Matched refund not detected"
    assert summary.failed_txn_count >= 1, "Failed txn not detected"

    # Financial integrity checks
    assert summary.expected_payment_amount > Decimal("0.00")
    assert summary.actual_valid_settlement_amount > Decimal("0.00")
    assert summary.duplicate_settlement_amount_prevented > Decimal("0.00")
    assert summary.reconciliation_rate_pct > 80.0
