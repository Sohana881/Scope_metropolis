# SCOPE Person 2 — PTXPhish transaction-risk workpack

## What is included
- `SCOPE_PTXPhish_Risk_Model.ipynb`: single notebook that fetches public Ethereum transaction/receipt data, builds transaction-payload features, trains/evaluates candidate models, and exports a model bundle only after data validation.
- `data/ptxphish_labeled_transaction_hashes.csv`: 18,555 labelled transaction hashes extracted from the supplied PTXPHISH.xlsx.
- `data/audit_report.json`: audit findings.
- `integration_contract.md`: how to integrate safely with SCOPE.

## Important limitation
This environment cannot reach an Ethereum RPC endpoint, so the on-chain feature extraction and model training were **not executed here**. Run the notebook on your Windows machine with internet access. The notebook checkpoints downloaded records and can resume. It does not fabricate performance numbers.

## Run on Windows
Open a terminal in this folder, activate your SCOPE `.venv` if desired, then install notebook dependencies:
```bat
python -m pip install pandas numpy scikit-learn joblib requests matplotlib openpyxl jupyter
python -m jupyter notebook SCOPE_PTXPhish_Risk_Model.ipynb
```
Run cells from top to bottom. In the config cell, `MAX_TRANSACTIONS = None` means all available labelled hashes; set it to `100` for a quick connectivity smoke test only. The public RPC can rate-limit or reject requests; the notebook checkpoints every batch.

## Interpreting metrics
PTXPhish labels describe categories of transaction examples. Accuracy alone is not enough because classes are imbalanced and source categories can correlate with selectors. Review phishing precision/recall, F1, confusion matrix and the unseen-selector stress test. Never claim 98–99% until the run actually demonstrates it on an appropriate holdout.
