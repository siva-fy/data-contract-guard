import json
from pathlib import Path
from contracts import check_csv, timestamp

root = Path(__file__).parent / "examples"
contract = json.loads((root / "orders.contract.json").read_text())
now = timestamp("2026-01-02T12:00:00Z")
good = check_csv(root / "orders.csv", contract, now)
bad = check_csv(root / "broken_orders.csv", contract, now)
assert good["passed"] and bad["issue_count"] == 6
print(json.dumps({"valid_dataset": good, "broken_dataset": bad}, indent=2))
