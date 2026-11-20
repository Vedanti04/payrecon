"""Tests for PayRecon synthetic data generator."""

import os
import pandas as pd
import pytest

from src.data_generator import generate_datasets
from src.data_validator import validate_transactions, validate_settlements


def test_generate_datasets_creates_files(tmp_path):
    """Test that data generator creates valid CSV files with expected columns."""
    out_dir = str(tmp_path / "data")
    txn_file, settle_file = generate_datasets(output_dir=out_dir, seed=42)

    assert os.path.exists(txn_file)
    assert os.path.exists(settle_file)

    df_txn = pd.read_csv(txn_file)
    df_settle = pd.read_csv(settle_file)

    assert len(df_txn) > 40
    assert len(df_settle) > 40

    # Check required transaction columns
    assert "transaction_id" in df_txn.columns
    assert "transaction_date" in df_txn.columns
    assert "amount" in df_txn.columns
    assert "status" in df_txn.columns
    assert "currency" in df_txn.columns

    # Check required settlement columns
    assert "settlement_id" in df_settle.columns
    assert "transaction_id" in df_settle.columns
    assert "settlement_date" in df_settle.columns
    assert "amount" in df_settle.columns
    assert "transaction_type" in df_settle.columns
    assert "original_transaction_id" in df_settle.columns


def test_generate_datasets_reproducibility(tmp_path):
    """Test that generator produces identical output with the same seed."""
    dir1 = str(tmp_path / "run1")
    dir2 = str(tmp_path / "run2")

    t1, s1 = generate_datasets(output_dir=dir1, seed=123)
    t2, s2 = generate_datasets(output_dir=dir2, seed=123)

    df_t1 = pd.read_csv(t1)
    df_t2 = pd.read_csv(t2)
    pd.testing.assert_frame_equal(df_t1, df_t2)

    df_s1 = pd.read_csv(s1)
    df_s2 = pd.read_csv(s2)
    pd.testing.assert_frame_equal(df_s1, df_s2)


def test_planted_anomalies_present_in_generated_data(tmp_path):
    """Verify that all 4 mandatory anomalies are planted in generated data."""
    out_dir = str(tmp_path / "data")
    t_file, s_file = generate_datasets(output_dir=out_dir, seed=42)

    df_txn = pd.read_csv(t_file)
    df_settle = pd.read_csv(s_file)

    # Anomaly A: Late Settlement (Nov txn settled in Dec)
    late_settles = df_settle[df_settle["settlement_date"].str.startswith("2026-12")]
    assert len(late_settles) >= 1
    late_txn_id = late_settles.iloc[0]["transaction_id"]
    late_txn = df_txn[df_txn["transaction_id"] == late_txn_id]
    assert len(late_txn) == 1
    assert late_txn.iloc[0]["transaction_date"].startswith("2026-11")

    # Anomaly B: Rounding differences
    rnd_txns = df_txn[df_txn["transaction_id"].str.contains("RND")]
    assert len(rnd_txns) >= 5

    # Anomaly C: Duplicate settlement
    dup_settles = df_settle[df_settle["transaction_id"].str.contains("DUP")]
    assert len(dup_settles) >= 2

    # Anomaly D: Unmatched refund (original_transaction_id not in transactions)
    orphan_refunds = df_settle[
        (df_settle["transaction_type"] == "REFUND")
        & (~df_settle["original_transaction_id"].isin(df_txn["transaction_id"]))
    ]
    assert len(orphan_refunds) >= 1

