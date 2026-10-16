SCOPE P2 ML NOTEBOOK — FIXED VERSION

Contents:
- SCOPE_P2_ML_Risk_Engine.ipynb: complete notebook; no separate ML .py file.

How to run in VS Code:
1. Extract this ZIP to a new folder.
2. Open the .ipynb file in VS Code and select a Python 3.11+ kernel.
3. Click Run All. Cell 1 installs dependencies; Cell 3 downloads the public BLTE CSV.
4. Outputs are saved under data/raw/, artifacts/, and reports/.

The notebook was corrected to use the dataset's actual text label column, attack (Normal/Phishing/Scamming), and to exclude attack_encoded and Scam from input features to prevent leakage.

IMPORTANT: This is an address-reputation research model, not a direct transaction/action classifier. It does not promise 99% accuracy. Keep SCOPE deterministic hard-deny rules authoritative.
