"""Tests for report generator module."""

import io
import csv
from decimal import Decimal
import pandas as pd
import pytest

from src.reconciliation import (
    ReconciliationEngine,
    ReconciliationItem,
    ReconciliationStatus,
    ReconciliationSummary,
)
from src.report_generator import (
    generate_reconciliation_csv,
    generate_discrepancy_csv,
    generate_summary_csv,
    generate_matched_csv,
    generate_unmatched_csv,
    generate_duplicates_csv,
    generate_refunds_csv,
)


@pytest.fixture
def sample_reconciliation():
    """Generate sample reconciliation items and summary."""
    df_t = pd.DataFrame([
        {"transaction_id": "TXN-001", "transaction_date": "2026-11-05", "amount": "1000.00", "status": "SUCCESS", "currency": "INR"},
        {"transaction_id": "TXN-002", "transaction_date": "2026-11-10", "amount": "2500.00", "status": "SUCCESS", "currency": "INR"},
        {"transaction_id": "TXN-003", "transaction_date": "2026-11-29", "amount": "3000.00", "status": "SUCCESS", "currency": "INR"},
        {"transaction_id": "TXN-DUP", "transaction_date": "2026-11-08", "amount": "5000.00", "status": "SUCCESS", "currency": "INR"},
    ])
    df_s = pd.DataFrame([
        {"settlement_id": "SET-001", "transaction_id": "TXN-001", "settlement_date": "2026-11-07", "amount": "1000.00", "transaction_type": "PAYMENT", "original_transaction_id": ""},
        {"settlement_id": "SET-003", "transaction_id": "TXN-003", "settlement_date": "2026-12-02", "amount": "3000.00", "transaction_type": "PAYMENT", "original_transaction_id": ""},
        {"settlement_id": "SET-DUP-1", "transaction_id": "TXN-DUP", "settlement_date": "2026-11-10", "amount": "5000.00", "transaction_type": "PAYMENT", "original_transaction_id": ""},
        {"settlement_id": "SET-DUP-2", "transaction_id": "TXN-DUP", "settlement_date": "2026-11-10", "amount": "5000.00", "transaction_type": "PAYMENT", "original_transaction_id": ""},
        {"settlement_id": "SET-REF-99", "transaction_id": "REF-001", "settlement_date": "2026-11-20", "amount": "500.00", "transaction_type": "REFUND", "original_transaction_id": "TXN-ORPHAN"},
        {"settlement_id": "SET-REF-01", "transaction_id": "REF-002", "settlement_date": "2026-11-20", "amount": "1000.00", "transaction_type": "REFUND", "original_transaction_id": "TXN-001"},
    ])

    engine = ReconciliationEngine()
    items, summary = engine.reconcile(df_t, df_s)
    return items, summary


def test_generate_reconciliation_csv(sample_reconciliation):
    """Test full reconciliation CSV generation."""
    items, _ = sample_reconciliation
    csv_str = generate_reconciliation_csv(items)

    assert "Record ID" in csv_str
    assert "Transaction ID" in csv_str
    assert "Settlement ID" in csv_str
    assert "Reconciliation Status" in csv_str

    df = pd.read_csv(io.StringIO(csv_str))
    assert len(df) == len(items)
    assert "TXN-001" in df["Transaction ID"].values
    assert "TXN-003" in df["Transaction ID"].values


def test_generate_discrepancy_csv(sample_reconciliation):
    """Test discrepancy-only CSV report generation."""
    items, _ = sample_reconciliation
    csv_str = generate_discrepancy_csv(items)

    df = pd.read_csv(io.StringIO(csv_str))
    discrepancy_count = sum(1 for it in items if it.is_discrepancy)
    assert len(df) == discrepancy_count
    assert "TXN-001" not in df["Transaction ID"].values
    assert "TXN-002" in df["Transaction ID"].values


def test_generate_summary_csv(sample_reconciliation):
    """Test executive summary CSV generation."""
    _, summary = sample_reconciliation
    csv_str = generate_summary_csv(summary)

    df = pd.read_csv(io.StringIO(csv_str))
    assert "Expected Payment Amount" in df["Metric"].values
    assert "Actual Valid Settlement Amount" in df["Metric"].values
    assert "Late Settlements Count" in df["Metric"].values
    assert "Reconciliation Success Rate" in df["Metric"].values


def test_generate_matched_csv(sample_reconciliation):
    """Test matched transaction report CSV generation."""
    items, _ = sample_reconciliation
    csv_str = generate_matched_csv(items)
    df = pd.read_csv(io.StringIO(csv_str))
    assert "TXN-001" in df["Transaction ID"].values
    assert "TXN-002" not in df["Transaction ID"].values


def test_generate_unmatched_csv(sample_reconciliation):
    """Test unmatched transaction report CSV generation."""
    items, _ = sample_reconciliation
    csv_str = generate_unmatched_csv(items)
    df = pd.read_csv(io.StringIO(csv_str))
    assert "TXN-002" in df["Transaction ID"].values
    assert "TXN-001" not in df["Transaction ID"].values


def test_generate_duplicates_csv(sample_reconciliation):
    """Test duplicate records report CSV generation."""
    items, _ = sample_reconciliation
    csv_str = generate_duplicates_csv(items)
    df = pd.read_csv(io.StringIO(csv_str))
    assert len(df) >= 1
    assert "TXN-DUP" in df["Transaction ID"].values
    assert "EXCLUDED FROM SETTLEMENT TOTALS" in df["Action Taken"].values


def test_generate_refunds_csv(sample_reconciliation):
    """Test refunds discrepancy report CSV generation."""
    items, _ = sample_reconciliation
    csv_str = generate_refunds_csv(items)
    df = pd.read_csv(io.StringIO(csv_str))
    assert len(df) == 2
    assert "TXN-ORPHAN" in df["Original Transaction ID"].values
    assert "TXN-001" in df["Original Transaction ID"].values
