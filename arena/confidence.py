"""Layer 3, the confidence model: how likely is the engine's answer to be right?

EXPERIMENT, NOT IN THE RUN. Measured (scripts/train_confidence.py, scripts/shift_test.py --layer3):
on rows like the practice data it calibrates far better (out of fold ECE 0.044 -> 0.005; random
pages 0.062 -> 0.016 with the control), but when the data shifts it is over-confident, even with
the run-time control after it (latest pages 0.034 -> 0.055). The run keeps the engine's confidence.

A small logistic regression on signs the run has for every answer: the engine's
probabilities, whether its two passes agree, what kind of verdict it is (supported,
contradicted, unknown, not understood), how much evidence agreed or disagreed, and how
well the sentence was read. It is trained by scripts/train_confidence.py only on answers
the engine gave for rows it never learned from, so what it learns is how often answers
like these are right on unseen rows.

Its probability becomes the answer's confidence. A `false` answer it thinks is more
likely wrong than right becomes `true`, with the complementary confidence: on rows with
little evidence the engine says `false` more often than it is right.
"""
import json
import math
import os

MODEL_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "reports", "confidence_model.json")
KINDS = ("supported", "contradicted", "unknown", "not_understood")
VALUE_KINDS = ("date", "money", "quantity", "percent", "duration", "version", "name", "boolean")
L2 = 1.0
FLIP_BELOW = 0.5


def features(p):
    """The signs of one prediction, as {name: number}. Only what the run has."""
    probs = p.get("probs") or {}
    label = p.get("label")
    is_false = 1.0 if label == "false" else 0.0
    p_true, p_false = float(probs.get("true", 0.5)), float(probs.get("false", 0.5))
    first = p.get("first_pass") or {}
    ex = p.get("extraction") or {}
    checks = p.get("checks") or []
    feats = [c.get("features") or {} for c in checks]
    cases = [c.get("case") or "" for c in checks]
    n_pos = [float(f.get("n_pos", 0)) for f in feats] or [0.0]
    n_neg = [float(f.get("n_neg", 0)) for f in feats] or [0.0]
    f = {
        "bias": 1.0,
        "is_false": is_false,
        "p_answer": p_false if is_false else p_true,
        "margin": abs(p_true - p_false),
        "p_unsure": float(probs.get("unsure", 0.0)),
        "passes_agree": 1.0 if first.get("label", label) == label else 0.0,
        "pass_shift": float(p.get("confidence") or 0.5) - float(first.get("confidence") or p.get("confidence") or 0.5),
        "complete": 1.0 if ex.get("complete") else 0.0,
        "facts": min(len(ex.get("facts") or []), 4) / 4,
        "subject_from_context": 1.0 if "subject from context" in (ex.get("issues") or []) else 0.0,
        "log_evidence_for": math.log1p(min(n_pos)),
        "log_evidence_against": math.log1p(max(n_neg)),
        "no_evidence": 1.0 if (not checks or "no_evidence" in cases) else 0.0,
        "any_mismatch": 1.0 if any("mismatch" in c for c in cases) else 0.0,
        "any_unlabelled_support": 1.0 if any(f_.get("u_any") for f_ in feats) else 0.0,
    }
    for k in KINDS:
        f[f"kind_{k}"] = 1.0 if p.get("kind") == k else 0.0
        f[f"false_x_kind_{k}"] = is_false * f[f"kind_{k}"]
    kinds = {f_.get("kind") for f_ in feats}
    for k in VALUE_KINDS:
        f[f"value_{k}"] = 1.0 if k in kinds else 0.0
    for k in ("no_evidence", "log_evidence_for", "log_evidence_against", "p_answer", "complete"):
        f[f"false_x_{k}"] = is_false * f[k]
    return f


def _sigmoid(z):
    return 1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, z))))


class ConfidenceModel:
    """Binary logistic regression with L2, by batch gradient descent. Pure Python."""

    def __init__(self, weights=None, meta=None):
        self.w = dict(weights or {})
        self.meta = dict(meta or {})

    def prob(self, f):
        return _sigmoid(sum(self.w.get(k, 0.0) * v for k, v in f.items()))

    def fit(self, X, y, l2=L2, epochs=600, lr=0.5):
        keys = sorted({k for x in X for k in x})
        self.w = {k: 0.0 for k in keys}
        n = len(X)
        for _ in range(epochs):
            grad = {k: 0.0 for k in keys}
            for x, t in zip(X, y):
                err = self.prob(x) - t
                for k, v in x.items():
                    grad[k] += err * v
            for k in keys:
                reg = 0.0 if k == "bias" else l2 * self.w[k]
                self.w[k] -= lr * (grad[k] + reg) / n
        return self

    def save(self, path=MODEL_PATH):
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"weights": {k: round(v, 6) for k, v in sorted(self.w.items())}, "meta": self.meta}, f, indent=1)
            f.write("\n")

    @classmethod
    def load(cls, path=MODEL_PATH):
        try:
            with open(path, encoding="utf-8") as f:
                d = json.load(f)
        except (OSError, ValueError):
            return None
        return cls(d["weights"], d.get("meta"))


def decide(p, model):
    """(label, confidence, layer report) for one engine prediction. Unsure answers pass through."""
    label = p.get("label")
    if model is None or label not in ("true", "false") or not p.get("probs"):
        return label, p.get("confidence"), None  # nothing to judge it on: the engine's answer stands
    f = features(p)
    right = model.prob(f)
    report = {"engine": p.get("confidence"), "model": round(right, 3), "flipped": False}
    if label == "false" and right < FLIP_BELOW:
        report["flipped"] = True
        return "true", round(min(1.0, max(0.5, 1.0 - right)), 3), report
    return label, round(min(1.0, max(0.5, right)), 3), report


def apply(predictions, model):
    """Layer 3 on engine predictions ({id: prediction} or a list), in place."""
    items = predictions.values() if isinstance(predictions, dict) else predictions
    flips = 0
    for p in items:
        label, conf, report = decide(p, model)
        if report is None:
            continue
        flips += report["flipped"]
        p["label"], p["confidence"], p["confidence_layer"] = label, conf, report
    return flips
