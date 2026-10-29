"""Every example of contracts/claim-forms.md and contracts/value-forms.md, read from the files
themselves: the referee tests the same examples ("Every phrase and example on this page is a
test in our repository"), so ours must read each one as the page shows it."""
import json
import os
import re

import pytest

from arena.values import has_negation, parse_values, values_equal
from tests.test_validate import AT, CHANGE, CMP, DATES, PRICE, REL, SOC2_NO, V

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONTRACTS = os.path.join(ROOT, "contracts")

# The form each "In these examples ..." paragraph of claim-forms.md describes.
SECTIONS = [
    ("Hooly AI Pro's price, and the value", "fact", PRICE),
    ("SOC 2 certification", "fact", SOC2_NO),
    ("left fact is Hooly Workspace's price", "compare", CMP),
    ("left fact is the date of Hooly I/O 2026", "compare", DATES),
    ("from €49 per month to €59 per month", "change", CHANGE),
    ("Hooly Gemini's languages", "at_event", AT),
    ("the link is Hooly's CTO", "relation", REL),
]


def _cells(line):
    return [c.strip() for c in line.strip().strip("|").split("|")]


def claim_examples():
    out, current = [], None
    with open(os.path.join(CONTRACTS, "claim-forms.md"), encoding="utf-8") as f:
        for line in f:
            if line.startswith("In these examples"):
                current = next((t, form) for key, t, form in SECTIONS if key in line)
            elif line.startswith("## "):
                current = None
            elif current and line.startswith("| `"):
                cells = _cells(line)
                t, form = current
                if len(cells) == 3:  # Text | op | Read
                    form = {**form, "op": cells[1].strip("`")}
                out.append(pytest.param(t, form, cells[0].strip("`"), cells[-1].startswith("yes"),
                                        id=cells[0].strip("`")[:60]))
    return out


def value_examples():
    """(written, value, states): states is False in the "Does not state" table."""
    out, states = [], True
    with open(os.path.join(CONTRACTS, "value-forms.md"), encoding="utf-8") as f:
        for line in f:
            if line.startswith("| Written |"):
                states = "Does not state" not in line
            m = re.match(r"\| `(.+?)` \| `(\{.+?\})` \|", line)
            if m:
                out.append(pytest.param(m.group(1), json.loads(m.group(2)), states,
                                        id=f"{'' if states else 'NOT '}{m.group(1)} -> {m.group(2)}"[:80]))
    return out


def reads(written, value):
    """Whether our reading of `written` states `value` exactly, as the referee would."""
    if value["kind"] == "boolean":  # the polarity of the passage
        return has_negation(written) != value["value"]
    if value["kind"] == "name":  # names are read through the lexicon, by the validator
        form = {"subject": "Hooly", "attribute": "founders", "value": value}
        return V.text_issues("fact", form, f"Hooly was {written}.") == []
    return any(values_equal(v["value"], value) for v in parse_values(written)
               if not (v["approx"] or v["range"] or v["negated"])
               and v["value"].get("op", "eq") == value.get("op", "eq"))


CLAIMS = claim_examples()
VALUES = value_examples()


def test_every_table_was_read():
    assert len(CLAIMS) >= 70 and len(VALUES) >= 90


@pytest.mark.parametrize("t, form, text, valid", CLAIMS)
def test_claim_form_example(t, form, text, valid):
    issues = V.text_issues(t, form, text)
    assert (issues == []) == valid, issues


@pytest.mark.parametrize("written, value, states", VALUES)
def test_value_form_example(written, value, states):
    assert reads(written, value) == states, parse_values(written)
