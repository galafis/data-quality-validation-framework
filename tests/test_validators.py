"""
Tests for the Data Quality Validation Framework.
"""

import sys
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from validators import (
    SchemaValidator, NullChecker, TypeChecker, RangeValidator,
    UniquenessChecker, ReferentialIntegrityChecker, CustomRulesEngine,
    ValidationReport, ValidationResult
)

SAMPLE_DATA = [
    {"id": 1, "name": "Alice", "age": 30, "email": "alice@example.com"},
    {"id": 2, "name": "Bob", "age": 25, "email": "bob@example.com"},
    {"id": 3, "name": "Charlie", "age": 35, "email": "charlie@example.com"},
]


class TestSchemaValidator:
    def test_valid_data(self):
        schema = {"id": {"type": "int", "required": True},
                  "name": {"type": "str", "required": True}}
        validator = SchemaValidator(schema)
        results = validator.validate(SAMPLE_DATA)
        assert all(r.is_valid for r in results)

    def test_missing_required_column(self):
        schema = {"missing_col": {"required": True}}
        validator = SchemaValidator(schema)
        results = validator.validate(SAMPLE_DATA)
        assert any(not r.is_valid for r in results)

    def test_empty_data(self):
        schema = {"id": {"required": True}}
        validator = SchemaValidator(schema)
        results = validator.validate([])
        assert any(not r.is_valid for r in results)

    def test_allowed_values(self):
        data = [{"status": "active"}, {"status": "inactive"}, {"status": "unknown"}]
        schema = {"status": {"allowed_values": ["active", "inactive"]}}
        validator = SchemaValidator(schema)
        results = validator.validate(data)
        assert any(not r.is_valid for r in results)

    def test_pattern_validation(self):
        data = [{"code": "AB123"}, {"code": "invalid!"}]
        schema = {"code": {"pattern": r"^[A-Z]{2}\d{3}$"}}
        validator = SchemaValidator(schema)
        results = validator.validate(data)
        assert any(not r.is_valid for r in results)


class TestNullChecker:
    def test_no_nulls(self):
        checker = NullChecker()
        results = checker.check(SAMPLE_DATA, ["name"])
        assert all(r.is_valid for r in results)

    def test_with_nulls(self):
        data = [{"name": "Alice"}, {"name": None}, {"name": ""}]
        checker = NullChecker()
        results = checker.check(data, ["name"])
        assert not results[0].is_valid
        assert len(results[0].failed_rows) == 2


class TestTypeChecker:
    def test_correct_types(self):
        checker = TypeChecker()
        results = checker.check(SAMPLE_DATA, {"age": "int"})
        assert all(r.is_valid for r in results)

    def test_wrong_type(self):
        data = [{"age": "not_a_number"}]
        checker = TypeChecker()
        results = checker.check(data, {"age": "int"})
        assert not results[0].is_valid


class TestRangeValidator:
    def test_in_range(self):
        validator = RangeValidator()
        results = validator.check(SAMPLE_DATA, {"age": (18, 65)})
        assert all(r.is_valid for r in results)

    def test_out_of_range(self):
        data = [{"age": 10}, {"age": 200}]
        validator = RangeValidator()
        results = validator.check(data, {"age": (18, 65)})
        assert not results[0].is_valid
        assert len(results[0].failed_rows) == 2


class TestUniquenessChecker:
    def test_unique(self):
        checker = UniquenessChecker()
        results = checker.check(SAMPLE_DATA, ["id"])
        assert all(r.is_valid for r in results)

    def test_duplicates(self):
        data = [{"id": 1}, {"id": 2}, {"id": 1}]
        checker = UniquenessChecker()
        results = checker.check(data, ["id"])
        assert not results[0].is_valid


class TestReferentialIntegrity:
    def test_valid_reference(self):
        ref_data = [{"id": 1}, {"id": 2}, {"id": 3}]
        data = [{"user_id": 1}, {"user_id": 2}]
        checker = ReferentialIntegrityChecker()
        result = checker.check(data, ref_data, "user_id", "id")
        assert result.is_valid

    def test_orphan_records(self):
        ref_data = [{"id": 1}, {"id": 2}]
        data = [{"user_id": 1}, {"user_id": 99}]
        checker = ReferentialIntegrityChecker()
        result = checker.check(data, ref_data, "user_id", "id")
        assert not result.is_valid


class TestCustomRulesEngine:
    def test_custom_rule_pass(self):
        engine = CustomRulesEngine()
        engine.add_rule("positive_age", "age", lambda v: v is not None and v > 0)
        results = engine.validate(SAMPLE_DATA)
        assert all(r.is_valid for r in results)

    def test_custom_rule_fail(self):
        data = [{"age": -5}, {"age": 25}]
        engine = CustomRulesEngine()
        engine.add_rule("positive_age", "age", lambda v: v is not None and v > 0)
        results = engine.validate(data)
        assert not results[0].is_valid


class TestValidationReport:
    def test_report_generation(self):
        results = [
            ValidationResult(True, "test1", "col1", "Passed"),
            ValidationResult(False, "test2", "col2", "Failed", [0, 1]),
        ]
        report = ValidationReport.generate(results)
        assert report["total_checks"] == 2
        assert report["passed"] == 1
        assert report["failed"] == 1

    def test_text_report(self):
        results = [ValidationResult(True, "test1", "col1", "OK")]
        text = ValidationReport.to_text(results)
        assert "PASS" in text
        assert "test1" in text


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
