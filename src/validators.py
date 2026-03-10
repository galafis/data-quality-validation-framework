"""
Data Quality Validators Module
Schema validation, null checks, type checks, range validation, uniqueness, and custom rules.
"""

import re
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union


class ValidationResult:
    """Result of a validation check."""

    def __init__(self, is_valid: bool, rule: str, column: str = "",
                 message: str = "", failed_rows: Optional[List[int]] = None):
        self.is_valid = is_valid
        self.rule = rule
        self.column = column
        self.message = message
        self.failed_rows = failed_rows or []

    def to_dict(self) -> Dict:
        return {
            "is_valid": self.is_valid,
            "rule": self.rule,
            "column": self.column,
            "message": self.message,
            "failed_count": len(self.failed_rows),
        }


class SchemaValidator:
    """Validates data against a schema definition."""

    def __init__(self, schema: Dict[str, Dict]):
        """
        Args:
            schema: Dict mapping column names to their specs.
                    Each spec can have: type, required, min, max, pattern, allowed_values
        """
        self.schema = schema

    def validate(self, data: List[Dict]) -> List[ValidationResult]:
        """Validate a list of records against the schema."""
        results = []
        if not data:
            return [ValidationResult(False, "non_empty", message="Dataset is empty")]

        # Check required columns exist
        columns_present = set(data[0].keys())
        for col, spec in self.schema.items():
            if spec.get("required", False) and col not in columns_present:
                results.append(ValidationResult(
                    False, "required_column", col,
                    f"Required column '{col}' is missing"
                ))

        # Validate each row
        for col, spec in self.schema.items():
            if col not in columns_present:
                continue

            failed_rows = []
            for i, row in enumerate(data):
                value = row.get(col)
                if not self._validate_value(value, spec):
                    failed_rows.append(i)

            is_valid = len(failed_rows) == 0
            results.append(ValidationResult(
                is_valid, "schema_validation", col,
                f"{'Passed' if is_valid else f'{len(failed_rows)} rows failed'} schema validation",
                failed_rows
            ))

        return results

    def _validate_value(self, value: Any, spec: Dict) -> bool:
        """Validate a single value against its spec."""
        # Null check
        if value is None or value == "":
            return not spec.get("required", False)

        # Type check
        expected_type = spec.get("type")
        if expected_type:
            if expected_type == "int" and not isinstance(value, int):
                try:
                    int(value)
                except (ValueError, TypeError):
                    return False
            elif expected_type == "float" and not isinstance(value, (int, float)):
                try:
                    float(value)
                except (ValueError, TypeError):
                    return False
            elif expected_type == "str" and not isinstance(value, str):
                return False

        # Range check
        if "min" in spec and value is not None:
            try:
                if float(value) < spec["min"]:
                    return False
            except (ValueError, TypeError):
                pass

        if "max" in spec and value is not None:
            try:
                if float(value) > spec["max"]:
                    return False
            except (ValueError, TypeError):
                pass

        # Pattern check
        if "pattern" in spec and isinstance(value, str):
            if not re.match(spec["pattern"], value):
                return False

        # Allowed values
        if "allowed_values" in spec:
            if value not in spec["allowed_values"]:
                return False

        return True


class NullChecker:
    """Checks for null/missing values."""

    def check(self, data: List[Dict], columns: Optional[List[str]] = None) -> List[ValidationResult]:
        """Check for nulls in specified columns."""
        if not data:
            return []

        columns = columns or list(data[0].keys())
        results = []

        for col in columns:
            failed = [i for i, row in enumerate(data)
                      if row.get(col) is None or row.get(col) == ""]
            null_rate = len(failed) / len(data) if data else 0
            results.append(ValidationResult(
                len(failed) == 0, "null_check", col,
                f"Null rate: {null_rate:.2%} ({len(failed)}/{len(data)})",
                failed
            ))

        return results


class TypeChecker:
    """Validates data types of columns."""

    TYPE_MAP = {
        "int": int,
        "float": (int, float),
        "str": str,
        "bool": bool,
    }

    def check(self, data: List[Dict], type_specs: Dict[str, str]) -> List[ValidationResult]:
        """
        Check column types.
        Args:
            type_specs: Dict mapping column names to expected types.
        """
        results = []
        for col, expected_type in type_specs.items():
            failed = []
            for i, row in enumerate(data):
                value = row.get(col)
                if value is None:
                    continue
                expected = self.TYPE_MAP.get(expected_type)
                if expected and not isinstance(value, expected):
                    try:
                        if expected_type == "int":
                            int(value)
                        elif expected_type == "float":
                            float(value)
                        else:
                            failed.append(i)
                    except (ValueError, TypeError):
                        failed.append(i)

            results.append(ValidationResult(
                len(failed) == 0, "type_check", col,
                f"Type check for '{expected_type}': {len(failed)} failures",
                failed
            ))

        return results


class RangeValidator:
    """Validates numeric values are within expected ranges."""

    def check(self, data: List[Dict], range_specs: Dict[str, Tuple[float, float]]) -> List[ValidationResult]:
        """
        Args:
            range_specs: Dict mapping column names to (min, max) tuples.
        """
        results = []
        for col, (min_val, max_val) in range_specs.items():
            failed = []
            for i, row in enumerate(data):
                value = row.get(col)
                if value is None:
                    continue
                try:
                    v = float(value)
                    if v < min_val or v > max_val:
                        failed.append(i)
                except (ValueError, TypeError):
                    failed.append(i)

            results.append(ValidationResult(
                len(failed) == 0, "range_check", col,
                f"Range [{min_val}, {max_val}]: {len(failed)} out of range",
                failed
            ))
        return results


class UniquenessChecker:
    """Checks for duplicate values."""

    def check(self, data: List[Dict], columns: List[str]) -> List[ValidationResult]:
        """Check uniqueness of specified columns."""
        results = []
        for col in columns:
            seen = {}
            duplicates = []
            for i, row in enumerate(data):
                value = row.get(col)
                if value in seen:
                    duplicates.append(i)
                else:
                    seen[value] = i

            results.append(ValidationResult(
                len(duplicates) == 0, "uniqueness_check", col,
                f"Duplicates: {len(duplicates)} found",
                duplicates
            ))
        return results


class ReferentialIntegrityChecker:
    """Checks referential integrity between datasets."""

    def check(self, data: List[Dict], ref_data: List[Dict],
              column: str, ref_column: str) -> ValidationResult:
        """Check that all values in column exist in ref_data's ref_column."""
        ref_values = {row.get(ref_column) for row in ref_data}
        failed = [i for i, row in enumerate(data)
                  if row.get(column) not in ref_values]

        return ValidationResult(
            len(failed) == 0, "referential_integrity",
            column,
            f"Referential integrity: {len(failed)} orphan records",
            failed
        )


class CustomRulesEngine:
    """Engine for custom validation rules."""

    def __init__(self):
        self.rules: List[Tuple[str, str, Callable]] = []

    def add_rule(self, name: str, column: str, rule_fn: Callable[[Any], bool]):
        """Add a custom validation rule."""
        self.rules.append((name, column, rule_fn))

    def validate(self, data: List[Dict]) -> List[ValidationResult]:
        """Run all custom rules against data."""
        results = []
        for name, column, rule_fn in self.rules:
            failed = []
            for i, row in enumerate(data):
                value = row.get(column)
                try:
                    if not rule_fn(value):
                        failed.append(i)
                except Exception:
                    failed.append(i)

            results.append(ValidationResult(
                len(failed) == 0, f"custom:{name}", column,
                f"Custom rule '{name}': {len(failed)} failures",
                failed
            ))
        return results


class ValidationReport:
    """Generates validation reports from results."""

    @staticmethod
    def generate(results: List[ValidationResult]) -> Dict:
        """Generate a summary report."""
        total = len(results)
        passed = sum(1 for r in results if r.is_valid)
        failed = total - passed

        return {
            "total_checks": total,
            "passed": passed,
            "failed": failed,
            "pass_rate": round(passed / total, 4) if total > 0 else 0,
            "details": [r.to_dict() for r in results],
        }

    @staticmethod
    def to_text(results: List[ValidationResult]) -> str:
        """Generate text report."""
        lines = ["=" * 60, "DATA QUALITY VALIDATION REPORT", "=" * 60]
        for r in results:
            status = "PASS" if r.is_valid else "FAIL"
            lines.append(f"[{status}] {r.rule} | {r.column} | {r.message}")
        total = len(results)
        passed = sum(1 for r in results if r.is_valid)
        lines.append("=" * 60)
        lines.append(f"Total: {total} | Passed: {passed} | Failed: {total - passed}")
        return "\n".join(lines)
