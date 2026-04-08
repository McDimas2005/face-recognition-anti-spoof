from types import SimpleNamespace

from app.models.domain import EnrollmentBatchStatus
from app.services.enrollment import evaluate_batch


def test_evaluate_batch_requires_all_diversity_tags_and_minimum_count():
    samples = [
        SimpleNamespace(quality_passed=True, diversity_tag="frontal_neutral"),
        SimpleNamespace(quality_passed=True, diversity_tag="left_yaw"),
        SimpleNamespace(quality_passed=True, diversity_tag="right_yaw"),
        SimpleNamespace(quality_passed=True, diversity_tag="expression"),
        SimpleNamespace(quality_passed=True, diversity_tag="lighting"),
    ]
    batch = SimpleNamespace(samples=samples)

    diversity_status, quality_summary, status = evaluate_batch(batch)

    assert all(diversity_status.values())
    assert quality_summary["accepted_samples"] == 5
    assert status == EnrollmentBatchStatus.ready


def test_evaluate_batch_stays_incomplete_when_tag_missing():
    samples = [
        SimpleNamespace(quality_passed=True, diversity_tag="frontal_neutral"),
        SimpleNamespace(quality_passed=True, diversity_tag="left_yaw"),
        SimpleNamespace(quality_passed=True, diversity_tag="right_yaw"),
        SimpleNamespace(quality_passed=True, diversity_tag="expression"),
        SimpleNamespace(quality_passed=False, diversity_tag="lighting"),
    ]
    batch = SimpleNamespace(samples=samples)

    diversity_status, _, status = evaluate_batch(batch)

    assert diversity_status["lighting"] is False
    assert status == EnrollmentBatchStatus.incomplete

