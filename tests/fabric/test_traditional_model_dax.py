from fabric import report_model


def test_operational_dax_does_not_use_reserved_dataset_variable_name():
    for measure in report_model.measures()["OperationalRecords"].values():
        assert "VAR Dataset " not in measure.expression
