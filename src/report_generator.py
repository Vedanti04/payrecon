"""Report generation module for PayRecon.

Generates 6 distinct, downloadable auditable CSV reports:
1. Complete Reconciliation Report (All records with statuses and explanations)
2. Matched Transactions Report (Fully reconciled 1:1 and within-tolerance records)
3. Unmatched & Missing Transactions Report (Missing settlements and unmatched items)
4. Duplicate Records Report (Duplicate bank entries excluded from settlement)
5. Refund Discrepancy Report (Segregated matched refunds and orphan unmatched refunds)
6. Executive Financial Summary Report (High-level financial KPIs and ledger breakdown)
"""

import io
import csv
from decimal import Decimal
import pandas as pd

from src.reconciliation import (
    ReconciliationItem,
    ReconciliationStatus,
    ReconciliationSummary,
)


def generate_reconciliation_csv(items: list[ReconciliationItem]) -> str:
    """Generate complete CSV string for all reconciliation items."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Record ID",
        "Transaction ID",
        "Settlement ID",
        "Record Type",
        "Platform Amount (INR)",
        "Bank Amount (INR)",
        "Transaction Date",
        "Settlement Date",
        "Reconciliation Status",
        "Issue Category",
        "Difference (INR)",
        "Is Discrepancy",
        "Explanation",
        "Original Txn ID",
    ])
    for it in items:
        writer.writerow([
            it.record_id,
            it.transaction_id,
            it.settlement_id or "N/A",
            it.record_type,
            f"{it.platform_amount:.2f}" if it.platform_amount is not None else "N/A",
            f"{it.bank_amount:.2f}" if it.bank_amount is not None else "N/A",
            it.transaction_date or "N/A",
            it.settlement_date or "N/A",
            it.status,
            it.issue_category,
            f"{it.difference_amount:.2f}",
            "YES" if it.is_discrepancy else "NO",
            it.explanation,
            it.original_transaction_id or "N/A",
        ])
    return output.getvalue()


def generate_matched_csv(items: list[ReconciliationItem]) -> str:
    """Generate CSV string containing only matched transactions."""
    matched_items = [
        it for it in items
        if it.status in (ReconciliationStatus.MATCHED, ReconciliationStatus.AGGREGATE_ROUNDING)
    ]
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Record ID",
        "Transaction ID",
        "Settlement ID",
        "Platform Amount (INR)",
        "Bank Amount (INR)",
        "Variance (INR)",
        "Transaction Date",
        "Settlement Date",
        "Match Type",
        "Explanation",
    ])
    for it in matched_items:
        writer.writerow([
            it.record_id,
            it.transaction_id,
            it.settlement_id or "N/A",
            f"{it.platform_amount:.2f}" if it.platform_amount is not None else "N/A",
            f"{it.bank_amount:.2f}" if it.bank_amount is not None else "N/A",
            f"{it.difference_amount:.2f}",
            it.transaction_date or "N/A",
            it.settlement_date or "N/A",
            it.issue_category,
            it.explanation,
        ])
    return output.getvalue()


def generate_unmatched_csv(items: list[ReconciliationItem]) -> str:
    """Generate CSV string containing missing and unmatched payment transactions."""
    unmatched_items = [
        it for it in items
        if it.status in (
            ReconciliationStatus.MISSING_SETTLEMENT,
            ReconciliationStatus.UNMATCHED_SETTLEMENT,
            ReconciliationStatus.AMOUNT_MISMATCH,
        )
    ]
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Record ID",
        "Transaction ID",
        "Settlement ID",
        "Record Type",
        "Platform Amount (INR)",
        "Bank Amount (INR)",
        "Difference (INR)",
        "Transaction Date",
        "Settlement Date",
        "Issue Category",
        "Explanation",
    ])
    for it in unmatched_items:
        writer.writerow([
            it.record_id,
            it.transaction_id,
            it.settlement_id or "N/A",
            it.record_type,
            f"{it.platform_amount:.2f}" if it.platform_amount is not None else "N/A",
            f"{it.bank_amount:.2f}" if it.bank_amount is not None else "N/A",
            f"{it.difference_amount:.2f}",
            it.transaction_date or "N/A",
            it.settlement_date or "N/A",
            it.issue_category,
            it.explanation,
        ])
    return output.getvalue()


def generate_duplicates_csv(items: list[ReconciliationItem]) -> str:
    """Generate CSV string containing duplicate bank settlement records."""
    dup_items = [
        it for it in items
        if it.status == ReconciliationStatus.DUPLICATE_SETTLEMENT
    ]
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Duplicate Settlement ID",
        "Transaction ID",
        "Duplicated Bank Amount (INR)",
        "Settlement Date",
        "Status",
        "Action Taken",
        "Explanation",
    ])
    for it in dup_items:
        writer.writerow([
            it.settlement_id or it.record_id,
            it.transaction_id,
            f"{it.bank_amount:.2f}" if it.bank_amount is not None else "N/A",
            it.settlement_date or "N/A",
            "DUPLICATE DETECTED",
            "EXCLUDED FROM SETTLEMENT TOTALS",
            it.explanation,
        ])
    return output.getvalue()


def generate_refunds_csv(items: list[ReconciliationItem]) -> str:
    """Generate CSV string containing all bank refund records with reconciliation audit status."""
    refund_items = [
        it for it in items
        if it.status in (ReconciliationStatus.MATCHED_REFUND, ReconciliationStatus.UNMATCHED_REFUND)
    ]
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Settlement ID",
        "Refund Txn ID",
        "Original Transaction ID",
        "Refund Amount (INR)",
        "Settlement Date",
        "Refund Classification",
        "Issue Category",
        "Explanation",
    ])
    for it in refund_items:
        writer.writerow([
            it.settlement_id or it.record_id,
            it.transaction_id,
            it.original_transaction_id or "MISSING",
            f"{it.bank_amount:.2f}" if it.bank_amount is not None else "N/A",
            it.settlement_date or "N/A",
            it.status,
            it.issue_category,
            it.explanation,
        ])
    return output.getvalue()


def generate_discrepancy_csv(items: list[ReconciliationItem]) -> str:
    """Generate CSV string containing all discrepancy exception records."""
    discrepancies = [it for it in items if it.is_discrepancy]
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Record ID",
        "Transaction ID",
        "Settlement ID",
        "Record Type",
        "Platform Amount (INR)",
        "Bank Amount (INR)",
        "Transaction Date",
        "Settlement Date",
        "Issue Category",
        "Reconciliation Status",
        "Difference (INR)",
        "Explanation",
        "Original Txn ID",
    ])
    for it in discrepancies:
        writer.writerow([
            it.record_id,
            it.transaction_id,
            it.settlement_id or "N/A",
            it.record_type,
            f"{it.platform_amount:.2f}" if it.platform_amount is not None else "N/A",
            f"{it.bank_amount:.2f}" if it.bank_amount is not None else "N/A",
            it.transaction_date or "N/A",
            it.settlement_date or "N/A",
            it.issue_category,
            it.status,
            f"{it.difference_amount:.2f}",
            it.explanation,
            it.original_transaction_id or "N/A",
        ])
    return output.getvalue()


def generate_summary_csv(summary: ReconciliationSummary) -> str:
    """Generate executive financial and operational reconciliation summary CSV string."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Category", "Metric", "Value", "Unit / Currency", "Description"])

    metrics = [
        ("Period", "Reconciliation Period", summary.reconciliation_period, "Month", "Accounting reconciliation period"),
        ("Operational", "Total Platform Transactions", summary.total_platform_transactions, "Count", "Total records in platform transaction log"),
        ("Operational", "Total Bank Settlements", summary.total_bank_settlements, "Count", "Total settlement rows received from bank"),
        ("Financial", "Expected Payment Amount", f"{summary.expected_payment_amount:.2f}", "INR", "Sum of all SUCCESS platform payments"),
        ("Financial", "Actual Valid Settlement Amount", f"{summary.actual_valid_settlement_amount:.2f}", "INR", "Sum of valid non-duplicate settlements received in Nov"),
        ("Financial", "Total Net Difference", f"{summary.total_net_difference:.2f}", "INR", "Expected Payment Amount minus Actual Settlement Amount"),
        ("Financial", "Gross Discrepancy Exposure", f"{summary.gross_discrepancy_amount:.2f}", "INR", "Sum of all absolute financial discrepancies"),
        ("Matched", "Matched Transactions Count", summary.matched_count, "Count", "Transactions with exact 1:1 settlement match"),
        ("Matched", "Matched Amount", f"{summary.matched_amount:.2f}", "INR", "Total principal settled and matched"),
        ("Timing", "Late Settlements Count", summary.late_settlement_count, "Count", "November transactions settled in December (Timing Difference)"),
        ("Timing", "Late Settlements Amount", f"{summary.late_settlement_amount:.2f}", "INR", "Funds settled in subsequent month"),
        ("Exception", "Missing Settlements Count", summary.missing_settlement_count, "Count", "Successful platform payments with no bank settlement"),
        ("Exception", "Missing Settlements Amount", f"{summary.missing_settlement_amount:.2f}", "INR", "Total platform funds pending bank settlement"),
        ("Exception", "Amount Mismatches Count", summary.amount_mismatch_count, "Count", "Transactions exceeding rounding tolerance"),
        ("Exception", "Amount Mismatch Net Diff", f"{summary.amount_mismatch_diff:.2f}", "INR", "Net discrepancy on mismatched transactions"),
        ("Rounding", "Rounding Discrepancy Count", summary.rounding_discrepancy_count, "Count", f"Transactions within tolerance (<= INR {summary.rounding_tolerance})"),
        ("Rounding", "Aggregate Rounding Discrepancy", f"{summary.aggregate_rounding_discrepancy:.2f}", "INR", "Net aggregate sum of small rounding variances"),
        ("Duplicate", "Duplicate Settlements Count", summary.duplicate_settlement_count, "Count", "Duplicate bank settlements detected"),
        ("Duplicate", "Duplicate Amount Prevented", f"{summary.duplicate_settlement_amount_prevented:.2f}", "INR", "Total duplicated bank funds excluded from double-counting"),
        ("Refunds", "Total Bank Refunds", f"{summary.total_refund_amount:.2f}", "INR", "Total gross refunds processed by bank"),
        ("Refunds", "Matched Refunds Count", summary.matched_refund_count, "Count", "Bank refunds matched to platform transactions"),
        ("Refunds", "Matched Refunds Amount", f"{summary.matched_refund_amount:.2f}", "INR", "Valid matched refunds reported separately"),
        ("Refunds", "Unmatched Orphan Refunds Count", summary.unmatched_refund_count, "Count", "Bank refunds referencing non-existent transaction IDs"),
        ("Refunds", "Unmatched Orphan Refunds Amount", f"{summary.unmatched_refund_amount:.2f}", "INR", "Orphan refunds requiring bank escalation"),
        ("Exception", "Unmatched Settlements Count", summary.unmatched_settlement_count, "Count", "Bank settlements with no matching platform transaction"),
        ("Exception", "Unmatched Settlements Amount", f"{summary.unmatched_settlement_amount:.2f}", "INR", "Bank funds cleared without platform record"),
        ("Validation", "Failed Platform Transactions", summary.failed_txn_count, "Count", "Platform failed payments (no bank obligation expected)"),
        ("Validation", "Invalid Input Records", summary.invalid_records_count, "Count", "Records failing schema or value checks"),
        ("KPI", "Reconciliation Success Rate", f"{summary.reconciliation_rate_pct:.2f}%", "Percentage", "Percentage of eligible platform volume reconciled"),
    ]

    for cat, metric, val, unit, desc in metrics:
        writer.writerow([cat, metric, val, unit, desc])

    return output.getvalue()
