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
PASS2_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "model_pass2.json")

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


class Boost:
    """Gradient-boosted trees on one-hot features, false against the rest.

    Each tree splits on whether a feature is present, so it learns
    combinations ("never seen, above the all-time max, and near a change")
    the linear model needs by hand. P(unsure) is the training base rate."""

    def __init__(self, trees=None, base=0.0, p_unsure=0.02, rounds=150, depth=3,
                 rate=0.1, l2=1.0, min_hess=4.0):
        self.trees, self.base, self.p_unsure = trees or [], base, p_unsure
        self.rounds, self.depth, self.rate, self.l2, self.min_hess = rounds, depth, rate, l2, min_hess

    @staticmethod
    def _leaf(tree, feats):
        while "leaf" not in tree:
            tree = tree["yes"] if tree["f"] in feats else tree["no"]
        return tree["leaf"]

    def margin(self, feats):
        return self.base + sum(self._leaf(t, feats) for t in self.trees)

    def probs(self, feats):
        p = 1 / (1 + math.exp(-max(-30.0, min(30.0, self.margin(feats)))))
        rest = 1 - self.p_unsure
        return {"true": (1 - p) * rest, "false": p * rest, "unsure": self.p_unsure}

    def _grow(self, X, idx, g, h, depth):
        G, H = sum(g[i] for i in idx), sum(h[i] for i in idx)
        leaf = {"leaf": -G / (H + self.l2) * self.rate}
        if depth == 0 or H < 2 * self.min_hess:
            return leaf
        sg, sh = {}, {}
        for i in idx:
            for k in X[i]:
                sg[k] = sg.get(k, 0.0) + g[i]
                sh[k] = sh.get(k, 0.0) + h[i]
        parent = G * G / (H + self.l2)
        best, best_gain = None, 1e-6
        for k, gy in sg.items():
            hy = sh[k]
            hn = H - hy
            if hy < self.min_hess or hn < self.min_hess:
                continue
            gn = G - gy
            gain = gy * gy / (hy + self.l2) + gn * gn / (hn + self.l2) - parent
            if gain > best_gain:
                best, best_gain = k, gain
        if best is None:
            return leaf
        yes = [i for i in idx if best in X[i]]
        no = [i for i in idx if best not in X[i]]
        return {"f": best, "yes": self._grow(X, yes, g, h, depth - 1),
                "no": self._grow(X, no, g, h, depth - 1)}

    def fit(self, X, y):
        t = [1.0 if lab == "false" else 0.0 for lab in y]
        pos = min(max(sum(t), 1.0), len(t) - 1.0)
        self.base = math.log(pos / (len(t) - pos))
        self.p_unsure = max(0.001, sum(1 for lab in y if lab == "unsure") / len(y))
        m = [self.base] * len(X)
        idx = list(range(len(X)))
        self.trees = []
        for _ in range(self.rounds):
            p = [1 / (1 + math.exp(-v)) for v in m]
            g = [pi - ti for pi, ti in zip(p, t)]
            h = [max(pi * (1 - pi), 1e-6) for pi in p]
            tree = self._grow(X, idx, g, h, self.depth)
            self.trees.append(tree)
            for i in idx:
                m[i] += self._leaf(tree, X[i])
        return self

    def save(self, path=MODEL_PATH, meta=None):
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"type": "boost", "labels": LABELS, "base": self.base,
                       "p_unsure": self.p_unsure, "meta": meta or {}, "trees": self.trees}, f)


def load_model(path=MODEL_PATH):
    """The saved label model (logistic regression or boosted trees), or None."""
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        d = json.load(f)
    if d.get("type") == "boost":
        return Boost(d["trees"], d["base"], d.get("p_unsure", 0.02))
    return LogReg(d["weights"], d.get("l2", 1.0))


def decide(probs, unsure_below=0.0):
    """Label and confidence from the model's probabilities.

    The label is the likeliest of true and false; it becomes unsure when
    unsure is likelier still, or when the firm label's probability is below
    unsure_below. A firm label's confidence is its probability, at least 0.5."""
    firm = max(("true", "false"), key=lambda k: probs[k])
    if probs["unsure"] > probs[firm] or probs[firm] < unsure_below:
        return "unsure", None
    return firm, round(max(0.5, min(1.0, probs[firm])), 3)
