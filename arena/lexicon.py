"""The lexicon: subjects, their aliases and attributes, and the events.

Names match as whole words, in any case and spacing, longest first, so
"Hooly AI Pro" names the plan and not the company Hooly.
"""

import re

from arena.values import norm_name


def _name_pattern(surface):
    words = surface.split()
    body = r"\s*".join(re.escape(w) for w in words)
    # "Hooly Android 16.0" names Hooly Android with version 16.0, not Android 16
    return rf"(?<![\w]){body}(?![\w]|\.\d)"


class Lexicon:
    def __init__(self, lexicon, value_names=()):
        """lexicon: the official lexicon.json dict.

        value_names: names that appear as values but are no subject, such as
        cities and people the practice forms name (Nimbus Cloud, Berlin)."""
        self.raw = lexicon
        self.subjects = {}
        self.events = set(lexicon.get("events", []))
        self._canon = {}
        for s in lexicon.get("subjects", []):
            self.subjects[s["name"]] = {"aliases": list(s.get("aliases", [])),
                                        "attributes": list(s.get("attributes", []))}
            for n in [s["name"]] + list(s.get("aliases", [])):
                self._canon.setdefault(norm_name(n), s["name"])
        for e in self.events:
            self._canon.setdefault(norm_name(e), e)
        self.value_names = {}
        for n in value_names:
            if norm_name(n) not in self._canon:
                self.value_names.setdefault(norm_name(n), n)
        surfaces = []
        for s, info in self.subjects.items():
            for n in [s] + info["aliases"]:
                surfaces.append((n, s, True))
        for key, n in self.value_names.items():
            surfaces.append((n, n, False))
        surfaces.sort(key=lambda x: len(x[0]), reverse=True)
        self._surfaces = surfaces
        self._rx = re.compile("|".join(f"(?P<g{i}>{_name_pattern(n)})"
                                       for i, (n, _, _) in enumerate(surfaces)), re.I)

    def resolve(self, name):
        """The canonical subject a name or alias names, or None."""
        return self._canon.get(norm_name(name))

    def resolve_value_name(self, name):
        """The canonical spelling of a name value (subject or not)."""
        return self._canon.get(norm_name(name)) or self.value_names.get(norm_name(name))

    def attributes(self, subject):
        info = self.subjects.get(subject)
        return info["attributes"] if info else []

    def has_attribute(self, subject, attribute):
        return attribute in self.attributes(subject)

    def is_event(self, name):
        return name in self.events

    def mentions(self, text):
        """Name mentions, longest first and not overlapping, in reading order:
        [{"name", "start", "end", "surface", "is_subject"}]."""
        out = []
        for m in self._rx.finditer(text):
            i = int(m.lastgroup[1:])
            surface, canon, is_subject = self._surfaces[i]
            out.append({"name": canon, "start": m.start(), "end": m.end(),
                        "surface": m.group(0), "is_subject": is_subject})
        return out
