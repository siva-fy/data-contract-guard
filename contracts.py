"""Validate CSV datasets against a small explicit contract format."""
import argparse
import csv
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path


def timestamp(value):
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("timezone required")
    return result.astimezone(timezone.utc)


def validate_contract(contract):
    if not isinstance(contract, dict) or set(contract) - {"version", "columns", "allow_extra_columns"}:
        raise ValueError("unknown top-level contract field")
    if type(contract.get("version")) is not int or contract["version"] != 1:
        raise ValueError("contract version must be 1")
    if type(contract.get("allow_extra_columns", False)) is not bool:
        raise ValueError("allow_extra_columns must be boolean")
    if not isinstance(contract.get("columns"), dict) or not contract["columns"]:
        raise ValueError("columns must be a nonempty mapping")
    allowed = {"type", "nullable", "unique", "min", "max", "enum", "pattern", "max_age_hours"}
    for name, rule in contract["columns"].items():
        if not isinstance(rule, dict) or set(rule) - allowed:
            raise ValueError(f"unknown rule in column {name}")
        if rule.get("type") not in ("string", "integer", "number", "timestamp"):
            raise ValueError(f"unsupported type for {name}")
        for flag in ("nullable", "unique"):
            if flag in rule and type(rule[flag]) is not bool:
                raise ValueError(f"{flag} must be boolean")
        for bound in ("min", "max"):
            if bound in rule and (rule["type"] not in ("integer", "number")
                    or type(rule[bound]) not in (int, float) or not math.isfinite(rule[bound])):
                raise ValueError("min/max require a numeric column and finite numeric bounds")
        if "min" in rule and "max" in rule and rule["min"] > rule["max"]:
            raise ValueError("min must not exceed max")
        if "enum" in rule and (not isinstance(rule["enum"], list) or rule["type"] == "timestamp"):
            raise ValueError("enum requires a list and is unsupported for timestamps")
        if "pattern" in rule:
            re.compile(rule["pattern"])
        if "max_age_hours" in rule and (
            rule["type"] != "timestamp" or type(rule["max_age_hours"]) not in (int, float)
            or not math.isfinite(rule["max_age_hours"]) or rule["max_age_hours"] < 0
        ):
            raise ValueError("max_age_hours requires timestamp and nonnegative age")


def convert(value, kind):
    if kind == "integer":
        if not re.fullmatch(r"[+-]?\d+", value):
            raise ValueError("expected integer")
        return int(value)
    if kind == "number":
        number = float(value)
        if not math.isfinite(number):
            raise ValueError("expected finite number")
        return number
    if kind == "timestamp":
        return timestamp(value)
    return value


def check_csv(path, contract, now):
    validate_contract(contract)
    if now.tzinfo is None:
        raise ValueError("now must include timezone")
    rules = contract["columns"]
    issues, row_count = [], 0
    seen = {name: set() for name in rules}

    def issue(row, column, code):
        issues.append({"row": row, "column": column, "code": code})

    with Path(path).open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        headers = reader.fieldnames or []
        if len(headers) != len(set(headers)):
            issue(1, "*", "duplicate_header")
        for column in sorted(set(rules) - set(headers)):
            issue(1, column, "missing_column")
        if not contract.get("allow_extra_columns", False):
            for column in sorted(set(headers) - set(rules)):
                issue(1, column, "unexpected_column")
        for row_number, row in enumerate(reader, 2):
            row_count += 1
            if None in row or any(value is None for value in row.values()):
                issue(row_number, "*", "malformed_row")
            for name, rule in rules.items():
                raw = row.get(name)
                if raw is None or raw.strip() == "":
                    if not rule.get("nullable", False):
                        issue(row_number, name, "null")
                    continue
                try:
                    value = convert(raw, rule["type"])
                except (ValueError, OverflowError):
                    issue(row_number, name, "type")
                    continue
                if rule.get("unique"):
                    if value in seen[name]:
                        issue(row_number, name, "duplicate")
                    seen[name].add(value)
                if "enum" in rule and value not in rule["enum"]:
                    issue(row_number, name, "enum")
                if "pattern" in rule and not re.fullmatch(rule["pattern"], raw):
                    issue(row_number, name, "pattern")
                if "min" in rule and value < rule["min"]:
                    issue(row_number, name, "min")
                if "max" in rule and value > rule["max"]:
                    issue(row_number, name, "max")
                if "max_age_hours" in rule:
                    age = (now - value).total_seconds() / 3600
                    if age < 0:
                        issue(row_number, name, "future_timestamp")
                    elif age > rule["max_age_hours"]:
                        issue(row_number, name, "stale")
    if row_count == 0:
        issue(0, "*", "empty_dataset")
    return {"passed": not issues, "rows": row_count, "issue_count": len(issues), "issues": issues}


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("csv", type=Path)
    p.add_argument("contract", type=Path)
    p.add_argument("--now", required=True, help="ISO timestamp with timezone for reproducible checks")
    args = p.parse_args()
    result = check_csv(args.csv, json.loads(args.contract.read_text()), timestamp(args.now))
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["passed"] else 1)
