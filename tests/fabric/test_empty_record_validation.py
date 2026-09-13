"""Regression for the live Power BI empty-invalid-set validation failure.

DAX COUNTROWS(empty table) is BLANK, not a strict-equal integer zero. Native
executeQueries reproduced both Stock/Orders Rows Valid=0 with complete valid
records; query-local COALESCE corrected both to 1 without changing source data.
"""

from fabric.report_model import CC, measures


def test_empty_invalid_record_set_is_explicitly_zero_in_every_validation():
    definitions = measures()[CC]
    affected = {
        name: value.expression
        for name, value in definitions.items()
        if 'FILTER(SavedRecords,SavedRecords[record_state] <> "available")'
        in value.expression
    }
    assert {"Stock Rows Valid", "Orders Rows Valid"} <= affected.keys()
    assert len(affected) == 3  # includes the traditional/overview stock validator
    for name, expression in affected.items():
        assert (
            'COALESCE(COUNTROWS(FILTER(SavedRecords,SavedRecords[record_state] <> "available")),0) == 0'
            in expression
        ), name
        # Still reject missing/all-empty record sets and preserve exact identities.
        assert "COUNTROWS(SavedRecords)>0" in expression
        assert "SavedRecords[case_key]" in expression
        assert "SavedRecords[analysis_key]" in expression
