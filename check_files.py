import os, sys
need = [
    "server.py", "engine.py", "engine.cpp", "formula.py", "rules.py",
    "pipeline.py", "normalize.py", "schema.py", "merge_engine.py",
    "export.py", "validate_engine.py", "requirements.txt",
    "static/index.html", "static/login.html"
]
miss = [f for f in need if not os.path.exists(f)]
if miss:
    print("THIEU FILE: " + ", ".join(miss))
    print("Hay tai du TOAN BO file trong goi datadesk len GitHub (nho ca thu muc static), roi deploy lai.")
    sys.exit(1)
print("Du file.")
