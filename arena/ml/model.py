"""The label model: evidence features -> P(true), P(false), P(unsure).

A multinomial logistic regression over one-hot features, in plain Python so
the image needs no numeric library. It is trained by eval/train_model.py on
out-of-fold features (each practice row described by a base and an
extractor that never saw its page) and saved to arena/ml/model.json.
"""

import json
import math
import os

LABELS = ("true", "false", "unsure")
MODEL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "model.json")

_STATUS_RANK = {"contradicted": 0, "unknown": 1, "supported": 2}


def _score_bin(s):
    if s is None:
        return "known"
    return "neg" if s < 0 else "low" if s < 2 else "mid" if s < 6 else "high"


def featurize(row, extraction, checks):
    """One-hot features of a row from its extraction and fact checks."""
    facts = extraction.get("facts") or []
    scores = extraction.get("scores") or []
    issues = extraction.get("issues") or []
    f = {"bias": 1.0}
    f[f"n_facts={min(len(facts), 3)}"] = 1.0
    f[f"complete={bool(extraction.get('complete'))}"] = 1.0
    for i in issues:
        key = i.split(":")[0]
        f[f"issue={key}"] = 1.0
    if not facts:
        f["no_facts"] = 1.0
        return f
    sc = [s for s in scores if s is not None]
    f[f"min_score={_score_bin(min(sc) if sc else None)}"] = 1.0
    statuses = [c["status"] for c in checks]
    for st in ("contradicted", "unknown", "supported"):
        n = statuses.count(st)
        f[f"n_{st}={min(n, 2)}"] = 1.0
    # the weakest fact describes the row
    order = sorted(range(len(checks)), key=lambda i: (_STATUS_RANK.get(checks[i]["status"], 1),
                                                      checks[i].get("confidence") or 0))
    w = checks[order[0]]
    f[f"case={w.get('case')}"] = 1.0
    feats = w.get("features") or {}
    for k, v in feats.items():
        f[f"w.{k}={v}"] = 1.0
    kind = feats.get("kind")
    f[f"case×kind={w.get('case')}|{kind}"] = 1.0
    f[f"case×seen={w.get('case')}|{feats.get('seen_pos')}|{feats.get('seen_neg')}"] = 1.0
    f[f"trend×kind={feats.get('trend')}|{kind}"] = 1.0
    if order[0] < len(scores):
        f[f"w.score={_score_bin(scores[order[0]])}"] = 1.0
    return f


class LogReg:
    def __init__(self, weights=None, l2=1.0):
        self.w = weights or {}      # feature -> [w_true, w_false, w_unsure]
        self.l2 = l2

    def probs(self, feats):
        z = [0.0] * len(LABELS)
        for k, x in feats.items():
            ws = self.w.get(k)
            if ws:
                for j in range(len(LABELS)):
                    z[j] += ws[j] * x
        m = max(z)
        e = [math.exp(v - m) for v in z]
        t = sum(e)
        return {LABELS[j]: e[j] / t for j in range(len(LABELS))}

    def fit(self, X, y, epochs=300, lr=0.5):
        """Full-batch gradient descent with L2 (not on the bias)."""
        n = len(X)
        keys = sorted({k for x in X for k in x})
        self.w = {k: [0.0] * len(LABELS) for k in keys}
        idx = [LABELS.index(t) for t in y]
        for ep in range(epochs):
            grad = {k: [0.0] * len(LABELS) for k in keys}
            for x, t in zip(X, idx):
                p = self.probs(x)
                for j, lab in enumerate(LABELS):
                    g = p[lab] - (1.0 if j == t else 0.0)
                    if g:
                        for k, v in x.items():
                            grad[k][j] += g * v
            step = lr / (1 + ep / 100)
            for k in keys:
                ws, gs = self.w[k], grad[k]
                reg = 0.0 if k == "bias" else self.l2
                for j in range(len(LABELS)):
                    ws[j] -= step * (gs[j] + reg * ws[j]) / n
        return self

    def save(self, path=MODEL_PATH, meta=None):
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"labels": LABELS, "l2": self.l2, "meta": meta or {},
                       "weights": {k: [round(v, 6) for v in ws] for k, ws in self.w.items()}},
                      f, indent=0, sort_keys=True)

    @classmethod
    def load(cls, path=MODEL_PATH):
        if not os.path.exists(path):
            return None
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        return cls(d["weights"], d.get("l2", 1.0))


def decide(probs, unsure_below=0.0):
    """Label and confidence from the model's probabilities.

    The label is the likeliest of true and false; it becomes unsure when
    unsure is likelier still, or when the firm label's probability is below
    unsure_below. A firm label's confidence is its probability, at least 0.5."""
    firm = max(("true", "false"), key=lambda k: probs[k])
    if probs["unsure"] > probs[firm] or probs[firm] < unsure_below:
        return "unsure", None
    return firm, round(max(0.5, min(1.0, probs[firm])), 3)
