"""Synthetic data generator for PayRecon.

Generates realistic platform transactions and bank settlements for November 2026,
with reproducible planted anomalies for reconciliation testing.
"""

import csv
import os
import random
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP


def generate_datasets(
    output_dir: str = "data",
    seed: int = 42,
    num_normal_txns: int = 45,
) -> tuple[str, str]:
    """Generate transactions.csv and settlements.csv for November 2026.

    Planted anomalies:
    A. LATE SETTLEMENT: Successful Nov txn settled in Dec 2026 (timing difference).
    B. ROUNDING DIFFERENCE: Multiple transactions with small rounding differences (aggregating noticeably).
    C. DUPLICATE ENTRY: Duplicated bank settlement entry referencing the same transaction.
    D. UNMATCHED REFUND: Bank refund referencing an original transaction ID not in transactions dataset.
    Plus:
    - Missing settlement (successful txn with no settlement).
    - Amount mismatch exceeding tolerance.
    - Failed platform transaction (no settlement expected).
    - Matched refund (valid refund referencing a successful original transaction).

    Args:
        output_dir: Directory where CSV files should be written.
        seed: Random seed for reproducibility.
        num_normal_txns: Number of normal matching transactions to generate.

    Returns:
        Tuple of (transactions_path, settlements_path).
    """
    random.seed(seed)
    os.makedirs(output_dir, exist_ok=True)

    transactions: list[dict] = []
    settlements: list[dict] = []

    # 1. Generate normal matching transactions across November 2026
    start_date = date(2026, 11, 1)
    end_date = date(2026, 11, 28)
    date_range_days = (end_date - start_date).days

    for i in range(1, num_normal_txns + 1):
        txn_day_offset = random.randint(0, date_range_days)
        txn_date = start_date + timedelta(days=txn_day_offset)
        # Settlements settle 1-2 days after transaction, still within Nov 2026
        settle_delay = random.randint(1, 2)
        settle_date = txn_date + timedelta(days=settle_delay)
        if settle_date > date(2026, 11, 30):
            settle_date = date(2026, 11, 30)

        txn_id = f"TXN-202611-{i:04d}"
        settle_id = f"SET-202611-{i:04d}"
        amount = Decimal(str(random.randint(500, 25000))) + Decimal(
            str(random.choice([0, 25, 50, 75, 99]))
        ) / Decimal("100")
        amount_str = f"{amount:.2f}"

        transactions.append(
            {
                "transaction_id": txn_id,
                "transaction_date": txn_date.isoformat(),
                "amount": amount_str,
                "status": "SUCCESS",
                "currency": "INR",
            }
        )

        settlements.append(
            {
                "settlement_id": settle_id,
                "transaction_id": txn_id,
                "settlement_date": settle_date.isoformat(),
                "amount": amount_str,
                "transaction_type": "PAYMENT",
                "original_transaction_id": "",
            }
        )

    # 2. Planted Anomaly A: LATE SETTLEMENT (Timing difference)
    # Successful November transaction settled in December 2026
    late_txn_id = "TXN-202611-LATE01"
    late_settle_id = "SET-202612-LATE01"
    late_amount = "14500.00"
    transactions.append(
        {
            "transaction_id": late_txn_id,
            "transaction_date": "2026-11-29",
            "amount": late_amount,
            "status": "SUCCESS",
            "currency": "INR",
        }
    )
    settlements.append(
        {
            "settlement_id": late_settle_id,
            "transaction_id": late_txn_id,
            "settlement_date": "2026-12-02",  # Settle in Dec 2026
            "amount": late_amount,
            "transaction_type": "PAYMENT",
            "original_transaction_id": "",
        }
    )

    # 3. Planted Anomaly B: ROUNDING DIFFERENCE
    # Multiple transactions with small individual rounding differences (0.01 - 0.02 INR)
    # that individually may pass tolerance but aggregate to a noticeable difference
    rounding_cases = [
        ("TXN-202611-RND01", "SET-202611-RND01", "2026-11-04", "2026-11-05", "2500.50", "2500.49"),  # -0.01
        ("TXN-202611-RND02", "SET-202611-RND02", "2026-11-09", "2026-11-11", "4120.75", "4120.73"),  # -0.02
        ("TXN-202611-RND03", "SET-202611-RND03", "2026-11-15", "2026-11-17", "890.30", "890.29"),   # -0.01
        ("TXN-202611-RND04", "SET-202611-RND04", "2026-11-21", "2026-11-23", "6730.00", "6729.98"),  # -0.02
        ("TXN-202611-RND05", "SET-202611-RND05", "2026-11-26", "2026-11-28", "1345.85", "1345.83"),  # -0.02
    ]
    for txn_id, set_id, t_date, s_date, t_amt, s_amt in rounding_cases:
        transactions.append(
            {
                "transaction_id": txn_id,
                "transaction_date": t_date,
                "amount": t_amt,
                "status": "SUCCESS",
                "currency": "INR",
            }
        )
        settlements.append(
            {
                "settlement_id": set_id,
                "transaction_id": txn_id,
                "settlement_date": s_date,
                "amount": s_amt,
                "transaction_type": "PAYMENT",
                "original_transaction_id": "",
            }
        )

    # Also an explicit AMOUNT MISMATCH exceeding tolerance
    transactions.append(
        {
            "transaction_id": "TXN-202611-MIS01",
            "transaction_date": "2026-11-12",
            "amount": "12000.00",
            "status": "SUCCESS",
            "currency": "INR",
        }
    )
    settlements.append(
        {
            "settlement_id": "SET-202611-MIS01",
            "transaction_id": "TXN-202611-MIS01",
            "settlement_date": "2026-11-14",
            "amount": "11500.00",  # 500 INR difference
            "transaction_type": "PAYMENT",
            "original_transaction_id": "",
        }
    )

    # 4. Planted Anomaly C: DUPLICATE ENTRY
    # Bank settlement record duplicated for an existing transaction
    dup_txn_id = "TXN-202611-DUP01"
    dup_amount = "7800.00"
    transactions.append(
        {
            "transaction_id": dup_txn_id,
            "transaction_date": "2026-11-08",
            "amount": dup_amount,
            "status": "SUCCESS",
            "currency": "INR",
        }
    )
    # Original settlement
    settlements.append(
        {
            "settlement_id": "SET-202611-DUP01A",
            "transaction_id": dup_txn_id,
            "settlement_date": "2026-11-10",
            "amount": dup_amount,
            "transaction_type": "PAYMENT",
            "original_transaction_id": "",
        }
    )
    # Duplicate settlement
    settlements.append(
        {
            "settlement_id": "SET-202611-DUP01B",
            "transaction_id": dup_txn_id,
            "settlement_date": "2026-11-10",
            "amount": dup_amount,
            "transaction_type": "PAYMENT",
            "original_transaction_id": "",
        }
    )

    # 5. Planted Anomaly D: UNMATCHED REFUND (Orphan refund)
    # Refund record referencing an original transaction ID that does not exist in platform transactions
    settlements.append(
        {
            "settlement_id": "SET-202611-REF99",
            "transaction_id": "REF-UNKNOWN-9999",
            "settlement_date": "2026-11-22",
            "amount": "3200.00",
            "transaction_type": "REFUND",
            "original_transaction_id": "TXN-GHOST-88888",  # Non-existent in transactions
        }
    )

    # 6. Additional realistic scenarios:
    # A. MISSING SETTLEMENT (Successful payment, never settled by bank)
    transactions.append(
        {
            "transaction_id": "TXN-202611-MISS01",
            "transaction_date": "2026-11-18",
            "amount": "9500.00",
            "status": "SUCCESS",
            "currency": "INR",
        }
    )

    # B. FAILED TRANSACTION (Platform status FAILED - no bank settlement expected)
    transactions.append(
        {
            "transaction_id": "TXN-202611-FAIL01",
            "transaction_date": "2026-11-06",
            "amount": "3100.00",
            "status": "FAILED",
            "currency": "INR",
        }
    )

    # C. VALID MATCHED REFUND (Bank refund referencing a valid prior platform transaction)
    valid_orig_txn_id = "TXN-202611-ORIG01"
    valid_orig_amt = "4500.00"
    transactions.append(
        {
            "transaction_id": valid_orig_txn_id,
            "transaction_date": "2026-11-11",
            "amount": valid_orig_amt,
            "status": "SUCCESS",
            "currency": "INR",
        }
    )
    settlements.append(
        {
            "settlement_id": "SET-202611-ORIG01",
            "transaction_id": valid_orig_txn_id,
            "settlement_date": "2026-11-13",
            "amount": valid_orig_amt,
            "transaction_type": "PAYMENT",
            "original_transaction_id": "",
        }
    )
    settlements.append(
        {
            "settlement_id": "SET-202611-REF01",
            "transaction_id": "REF-TXN-0001",
            "settlement_date": "2026-11-20",
            "amount": valid_orig_amt,
            "transaction_type": "REFUND",
            "original_transaction_id": valid_orig_txn_id,  # Valid match!
        }
    )

    # Write transactions.csv
    txn_file = os.path.join(output_dir, "transactions.csv")
    with open(txn_file, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["transaction_id", "transaction_date", "amount", "status", "currency"],
        )
        writer.writeheader()
        writer.writerows(transactions)

    # Write settlements.csv
    settle_file = os.path.join(output_dir, "settlements.csv")
    with open(settle_file, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "settlement_id",
                "transaction_id",
                "settlement_date",
                "amount",
                "transaction_type",
                "original_transaction_id",
            ],
        )
        writer.writeheader()
        writer.writerows(settlements)

    return txn_file, settle_file


if __name__ == "__main__":
    t_file, s_file = generate_datasets()
    print(f"Generated {t_file} and {s_file}")

