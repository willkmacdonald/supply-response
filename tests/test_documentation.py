from pathlib import Path


def test_recon_report_is_clearly_bounded_to_its_historical_snapshot():
    report = (
        Path(__file__).parents[1] / "docs" / "codebase-recon-report.md"
    ).read_text()

    assert "historical snapshot" in report.lower()
    assert "83bf7f6" in report
    assert "current branch status" in report.lower()
