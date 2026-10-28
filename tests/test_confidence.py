from arena import confidence

ENGINE_ANSWER = {
    "id": "x", "label": "false", "confidence": 0.62, "kind": "supported",
    "probs": {"true": 0.40, "false": 0.58, "unsure": 0.02},
    "first_pass": {"label": "true", "confidence": 0.55},
    "extraction": {"complete": True, "facts": [{}], "issues": []},
    "checks": [{"case": "stable_match", "features": {"kind": "quantity", "n_pos": 3, "n_neg": 0}}],
}


def test_the_run_does_not_use_layer_3():
    """An experiment: measured worse under shift (arena/confidence.py), so neither the run nor the API loads it."""
    import inspect
    import api.main
    from arena import runner
    assert "ConfidenceModel" not in inspect.getsource(runner) + inspect.getsource(api.main)


def test_answers_without_the_engines_probabilities_pass_through():
    model = confidence.ConfidenceModel.load()
    p = {"id": "x", "label": "true", "confidence": 0.9}
    assert confidence.decide(p, model) == ("true", 0.9, None)


def test_unsure_and_no_model_pass_through():
    assert confidence.decide({**ENGINE_ANSWER, "label": "unsure", "confidence": None},
                             confidence.ConfidenceModel.load()) == ("unsure", None, None)
    assert confidence.decide(ENGINE_ANSWER, None) == ("false", 0.62, None)


def test_confidence_stays_in_range_and_the_flip_only_makes_true():
    model = confidence.ConfidenceModel({"bias": -3.0})  # thinks every answer is wrong
    label, conf, report = confidence.decide(ENGINE_ANSWER, model)
    assert (label, report["flipped"]) == ("true", True) and 0.5 <= conf <= 1
    label, conf, report = confidence.decide({**ENGINE_ANSWER, "label": "true"}, model)
    assert label == "true" and conf == 0.5 and not report["flipped"]  # a true answer is never flipped


def test_apply_reports_each_layer():
    preds = [dict(ENGINE_ANSWER)]
    confidence.apply(preds, confidence.ConfidenceModel({"bias": 2.0}))
    layer = preds[0]["confidence_layer"]
    assert layer["engine"] == 0.62 and 0.5 <= layer["model"] <= 1 and preds[0]["label"] == "false"


def test_the_fit_learns_a_plain_signal():
    X = [{"bias": 1.0, "margin": m / 10} for m in range(10)] * 20
    y = [1.0 if x["margin"] >= 0.5 else 0.0 for x in X]
    model = confidence.ConfidenceModel().fit(X, y)
    assert model.prob({"bias": 1.0, "margin": 0.9}) > 0.8 > 0.2 > model.prob({"bias": 1.0, "margin": 0.0})


def test_the_experiment_measured_better_than_the_engine_out_of_fold():
    model = confidence.ConfidenceModel.load()
    assert model is not None, "reports/confidence_model.json is missing: run scripts/train_confidence.py"
    engine, nested = model.meta["engine"], model.meta["nested"]
    assert nested["brier"] < engine["brier"] and nested["ece"] < engine["ece"]
    assert nested["accuracy"] >= engine["accuracy"] - 0.005
