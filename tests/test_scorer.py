from filingsignal.models import Direction, Magnitude, Perspective
from filingsignal.scorer import score_quarter


def test_point_in_time_excludes_future_filings(uni, make_effect):
    base = [make_effect("FCX", "Copper", Perspective.producer, Direction.increase, Magnitude.large,
                        "2026-05-01", "2026-07-01", "2026-09-30")]
    future = base + [make_effect("HBM", "Copper", Perspective.producer, Direction.increase, Magnitude.large,
                                 "2026-08-01", "2026-07-01", "2026-09-30")]  # filed AFTER Q3 start
    cu_base = [r for r in score_quarter(base, (2026, 3), uni) if r.material_id == "copper"][0].combined
    cu_future = [r for r in score_quarter(future, (2026, 3), uni) if r.material_id == "copper"][0].combined
    assert abs(cu_base - cu_future) < 1e-9  # no look-ahead


def test_decrease_scores_negative(uni, make_effect):
    rows = score_quarter(
        [make_effect("NUE", "Steel", Perspective.producer, Direction.decrease, Magnitude.moderate,
                     "2026-06-10", "2026-07-01", "2026-09-30")], (2026, 3), uni)
    steel = [r for r in rows if r.material_id == "steel"][0]
    assert steel.combined < 0  # bearish signal must not be zeroed by the breadth gate


def test_producer_only_material_has_null_consumer(uni, make_effect):
    rows = score_quarter(
        [make_effect("NEM", "Gold", Perspective.producer, Direction.increase, Magnitude.small,
                     "2026-05-15", "2026-07-01", "2026-09-30")], (2026, 3), uni)
    gold = [r for r in rows if r.material_id == "gold"][0]
    assert gold.consumer_score is None


def test_cross_perspective_and_ranking(uni, make_effect):
    effects = [
        make_effect("FCX", "Copper", Perspective.producer, Direction.increase, Magnitude.large, "2026-05-01", "2026-07-01", "2026-09-30"),
        make_effect("SCCO", "Copper", Perspective.producer, Direction.increase, Magnitude.moderate, "2026-06-01", "2026-07-01", "2026-09-30"),
        make_effect("ETN", "Copper", Perspective.consumer, Direction.increase, Magnitude.large, "2026-05-30", "2026-07-01", "2026-09-30"),
    ]
    rows = score_quarter(effects, (2026, 3), uni)
    assert rows[0].material_id == "copper" and rows[0].rank == 1
    assert rows[0].z > 0 and rows[0].consumer_score > 0
