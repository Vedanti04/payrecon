# PayRecon – Intelligent Payment Reconciliation System

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.30%2B-FF4B4B.svg)](https://streamlit.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Tests: Pytest](https://img.shields.io/badge/tests-21%20passed-brightgreen.svg)](tests/)

**PayRecon** is an institutional-grade payment reconciliation engine and interactive audit dashboard designed for modern fintechs, payment gateways, and merchant platforms. It deterministically compares platform-recorded customer payments against partner bank clearing settlement files, identifies and explains discrepancies, enforces double-counting protection, and produces audit-ready financial statements.

---

## 📌 Executive Summary & Problem Context

In modern payment platforms, customer transactions are captured and authorized in real time ($T+0$), whereas acquiring and settlement banks clear funds in batches over a $T+1$ to $T+2$ business-day clearing window.

At month-end (specifically **November 2026** for this reconciliation cycle), platform accounting ledgers must reconcile against bank clearing statements. Variances routinely occur due to:
1. **Timing Differences**: Month-end transactions settling in the subsequent accounting cycle (December 2026).
2. **Batch Rounding Variances**: Minute penny differences across platform and bank fee calculation engines that accumulate into detectable discrepancies.
3. **Transmission Duplicates**: Banking network retries or batch replays that duplicate settlement lines.
4. **Orphan & Unmatched Refunds**: Bank-initiated chargebacks or refunds referencing unrecognized transaction identifiers.

PayRecon automates this reconciliation process using Python's high-precision `decimal.Decimal`, protecting financial integrity while providing explainable audit narratives.

---

## 🚀 Key Features

- **High-Precision Financial Math**: Core engine uses Python's `Decimal` with `ROUND_HALF_UP` to prevent IEEE 754 binary floating-point representation drift.
- **Reproducible Synthetic Data Generation**: Generates complete November 2026 datasets with planted assessment anomalies using fixed random seeds.
- **Robust Ingestion & Schema Validation**:
  - Validates missing IDs, invalid date formats, negative/malformed amounts, invalid transaction types, and unsupported currencies.
  - Non-destructive: Does **not** silently modify or discard invalid records; reports them with full row coordinates for audit inspection.
- **Comprehensive Discrepancy Classification**:
  - `Matched`: Exact 1:1 match.
  - `Late settlement`: Month-end timing difference (settled in December 2026).
  - `Missing settlement`: Platform payments lacking bank settlement.
  - `Amount mismatch`: Variance exceeding configurable rounding tolerance.
  - `Duplicate settlement`: Duplicate bank credit identified and excluded from valid totals.
  - `Aggregate rounding discrepancy`: Small variances ($\le \text{tolerance}$) tracked and aggregated.
  - `Unmatched refund`: Orphan refund referencing non-existent platform transaction.
  - `Matched refund`: Segregated and reported separately from gross payments.
  - `Failed transaction`: Excluded from payment settlement obligations.
  - `Invalid record`: Flagged input data failing schema checks.
- **Interactive Fintech Streamlit Dashboard**:
  - Executive KPI summary cards with directional status badges.
  - Comprehensive financial ledger accounting for variances and timing differences.
  - 5 interactive Plotly visualizations (Status Donut, Discrepancy Bar, Timeline Trend, Amount Comparison, Financial Waterfall Walk).
  - Dedicated Data Management Center with direct sample CSV downloads and live dataset previews.
  - Searchable, multi-filterable Transaction Explorer with deep-dive audit trace modal.
  - 6 exportable auditable CSV reports (Full Reconciliation, Matched, Unmatched, Duplicates, Refunds, Executive Summary).
  - Built-in Dark/Light theme toggle with fintech corporate styling.

---

## 🏗️ Project Architecture

```
PayRecon/
├── app.py                     # Streamlit frontend & interactive dashboard
├── requirements.txt           # Production dependencies
├── README.md                  # System documentation & deployment guide
├── data/
│   ├── transactions.csv       # Platform transactions (November 2026)
│   └── settlements.csv        # Bank settlement records
├── src/
│   ├── __init__.py
│   ├── data_generator.py      # Reproducible synthetic dataset generator
│   ├── data_validator.py      # Non-destructive CSV schema and value validator
│   ├── reconciliation.py      # Core Decimal-based reconciliation engine
│   └── report_generator.py    # Downloadable CSV report builder
└── tests/
    ├── __init__.py
    ├── test_data_generator.py # Tests for data generation & reproducibility
    ├── test_reconciliation.py # Tests for all 4 mandatory anomalies & edge cases
    └── test_report_generator.py # Tests for CSV report exports
```

---

## 🛠️ Technology Stack

- **Python 3.10+**: Core programming language.
- **Streamlit**: Production web application dashboard and reactive UI.
- **Pandas**: Efficient tabular data handling and data frame manipulation.
- **Plotly**: Interactive data visualizations and financial distribution charts.
- **Decimal (`decimal.Decimal`)**: Strict arbitrary-precision monetary calculation.
- **Pytest**: Automated test framework with 100% scenario coverage.

---

## 📦 Installation & Setup

### 1. Prerequisites
Ensure you have Python 3.10 or higher installed:
```bash
python --version
```

### 2. Clone / Open Directory
```bash
cd c:\PayRecon
```

### 3. Create and Activate Virtual Environment (Recommended)
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS / Linux
python3 -m venv venv
source venv/bin/activate
```

### 4. Install Dependencies
```bash
pip install -r requirements.txt
```

---

## 🚦 How to Run the Application

### 1. Generate Sample Data (Optional, done automatically on startup)
```bash
python src/data_generator.py
```

### 2. Launch Streamlit Dashboard
```bash
# Recommended (runs via Python module directly):
python -m streamlit run app.py

# Or on Windows using the helper scripts:
.\run.ps1
# or
run.bat

# If streamlit is added to your PATH:
streamlit run app.py
```
The application will open in your default browser at `http://localhost:8501`.

---

## 🧪 Automated Testing

PayRecon includes an extensive test suite verifying all 4 mandatory assessment anomalies, financial calculations, data validations, and export functions:

```bash
python -m pytest tests -v
```

### Tested Scenarios:
1. `test_exact_matching_transaction`: Verifies 1:1 reconciliation in November 2026.
2. `test_anomaly_a_late_settlement`: Verifies that November transactions settled in December are categorized as **Timing Differences (Late Settlement)**, not missing.
3. `test_anomaly_b_aggregate_rounding_discrepancy`: Verifies that penny differences within tolerance are detected and aggregated accurately.
4. `test_anomaly_c_duplicate_bank_entry`: Verifies duplicate detection and prevents double-counting of bank settlement funds.
5. `test_anomaly_d_unmatched_refund`: Verifies that refunds referencing non-existent platform transactions are flagged as **Orphan Refunds**.
6. `test_missing_settlement`: Verifies missing settlement classification for unsettled platform payments.
7. `test_amount_mismatch_exceeding_tolerance`: Verifies detection of variances exceeding configured rounding tolerance.
8. `test_failed_platform_transaction_handling`: Verifies failed payments are not treated as payment obligations.
9. `test_invalid_input_data_validation`: Tests schema validation across missing columns, invalid dates, negative values, and bad currencies.
10. `test_full_synthetic_dataset_reconciliation`: End-to-end reconciliation across 50+ transactions.
11. `test_report_generator`: Verifies integrity of all 3 CSV report outputs.

---

## 📑 CSV File Format Requirements

PayRecon accepts two CSV input files:

### 1. Platform Transactions (`transactions.csv`)
| Column Name | Type | Example | Description |
|---|---|---|---|
| `transaction_id` | String | `TXN-202611-0001` | Unique transaction identifier |
| `transaction_date` | Date (YYYY-MM-DD) | `2026-11-05` | Timestamp of platform payment authorization |
| `amount` | Decimal | `1250.50` | Strictly positive transaction amount |
| `status` | String | `SUCCESS` or `FAILED` | Payment lifecycle status |
| `currency` | String | `INR` | Supported settlement currency |

### 2. Bank Settlements (`settlements.csv`)
| Column Name | Type | Example | Description |
|---|---|---|---|
| `settlement_id` | String | `SET-202611-0001` | Unique bank settlement record identifier |
| `transaction_id` | String | `TXN-202611-0001` | Platform transaction reference |
| `settlement_date` | Date (YYYY-MM-DD) | `2026-11-07` | Date bank cleared the funds |
| `amount` | Decimal | `1250.50` | Net settled funds |
| `transaction_type` | String | `PAYMENT` or `REFUND` | Nature of bank settlement line |
| `original_transaction_id` | String | `TXN-202611-ORIG01` | Required for `REFUND`; blank for `PAYMENT` |

---

## 🎯 Mandatory Anomalies & Reconciliation Methodology

### A. Late Settlement (Timing Difference)
- **Problem**: Platform transaction authorized on November 29, 2026; bank clears funds on December 2, 2026.
- **Engine Logic**: Checks settlement date against month-end cutoff (`2026-11-30`). Classified as `Late settlement` (timing difference).
- **Accounting Treatment**: Documented as an in-transit month-end asset; not flagged as a loss or missing funds.

### B. Rounding Difference & Aggregate Accumulation
- **Problem**: Individual differences of ₹0.01 to ₹0.02 arise due to fee deductions or gateway truncation.
- **Engine Logic**: Configurable tolerance (default `₹0.05`). Variances $\le \text{tolerance}$ are marked as `Aggregate rounding discrepancy`.
- **Accounting Treatment**: Summed into an aggregate rounding variance line item for ledger posting.

### C. Duplicate Settlement Prevention
- **Problem**: Bank settlement file contains two records for the same transaction ID (`SET-DUP-01A` and `SET-DUP-01B`).
- **Engine Logic**: First occurrence is treated as primary; subsequent records are flagged as `Duplicate settlement`.
- **Accounting Treatment**: Duplicate amount is explicitly excluded from `actual_valid_settlement_amount` to prevent artificial revenue inflation.

### D. Unmatched Orphan Refund
- **Problem**: Bank settlement contains a `REFUND` referencing an `original_transaction_id` that is absent from platform records.
- **Engine Logic**: Cross-references platform transaction log; flags missing parent as `Unmatched refund`.
- **Accounting Treatment**: Segregated into an operational escalation queue for partner bank inquiry.

---

## ☁️ Production Deployment & CI/CD

### 1. GitHub Setup & Streamlit Community Cloud

The local repository is already initialized on branch `main` with all files committed.

#### Step 1: Create a GitHub Repository
1. Go to [github.com/new](https://github.com/new) and create a repository (e.g. `payrecon` or `PayRecon`). Choose **Public** or **Private**.
2. Run the following commands in your terminal:
   ```bash
   git remote add origin https://github.com/<your-username>/payrecon.git
   git branch -M main
   git push -u origin main
   ```

#### Step 2: Deploy to Streamlit Community Cloud
1. Sign in to [share.streamlit.io](https://share.streamlit.io/) with your GitHub account.
2. Click **New app**.
3. Select your repository: `<your-username>/payrecon`.
4. Branch: `main`.
5. Main file path: `app.py`.
6. Click **Deploy!**
Streamlit Cloud automatically reads `.streamlit/config.toml` and `requirements.txt`, builds the container, and serves your live dashboard.

---

### 2. Docker & Containerized Self-Hosted Deployment

PayRecon includes production-grade containerization with non-root security and built-in healthchecks.

#### Option A: Run with Docker Compose (Recommended)
Build and launch the container in the background with persistent data volume:
```bash
docker compose up --build -d
```
- App URL: `http://localhost:8501`
- Stop container: `docker compose down`
- View logs: `docker compose logs -f`

#### Option B: Run with Docker CLI
```bash
# Build image
docker build -t payrecon:latest .

# Run container
docker run -d --name payrecon-app -p 8501:8501 payrecon:latest
```

---

### 3. Automated CI/CD Pipeline (GitHub Actions)

Every `git push` or pull request automatically triggers the `.github/workflows/ci.yml` pipeline:
- Matrices across **Python 3.10, 3.11, and 3.12**.
- Verifies module byte-compilation.
- Executes the full **21-test Pytest suite**.
- Validates synthetic data generation and the 4 assessment anomalies.
- Guarantees financial math and report export integrity prior to deployment.

---

## ⚠️ Known Limitations & Future Work

1. **Single Currency Focus**: Currently optimized for `INR`. Multi-currency FX conversions with date-adjusted spot rates can be added.
2. **Partial Split Settlements**: Multiple partial bank clearing records for a single platform transaction are flagged as amount variances unless tied to a parent batch identifier.
3. **Instant UPI T+0 Webhooks**: Modeled on standard T+1/T+2 clearing files; streaming webhook reconciliation can be integrated via Kafka or WebSocket connectors.

---

## 📜 License
This project is open-source and distributed under the MIT License.

