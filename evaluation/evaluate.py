"""Compare the original quick-answer rules with the new ones on a hand-labelled set of messages.

    python evaluation/evaluate.py

Needs no API key and makes no model calls. Writes results.json and cases.csv to evaluation/results/.
"""
import csv
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))
from cases import CASES  # noqa: E402
from legacy_intents import legacy_classify  # noqa: E402

from chatbot import intents  # noqa: E402

NOW = datetime(2026, 11, 1, 10, 5, tzinfo=timezone.utc)


def new_classify(message):
    q = intents.quick_answer(message, None, None, NOW)
    if q is None:
        return "model"
    if q.name and q.reply is None:
        return f"name+model:{q.name}"
    if q.name:
        return f"name:{q.name}"
    if q.reply and q.reply.startswith("It's "):
        return "time"
    if q.reply and q.reply.startswith("Today is"):
        return "date"
    if q.reply and "live weather" in q.reply:
        return "weather"
    return "other"


def old_label(message):
    kind = legacy_classify(message)
    return f"name:{kind[1]}" if kind[0] == "name" else kind[0]


def category(expected):
    return expected.split(":")[0]


def pct(a, b):
    return round(100 * a / b, 1)


def main():
    rows, tallies = [], {"old": defaultdict(lambda: [0, 0]), "new": defaultdict(lambda: [0, 0])}
    false_intercepts = {"old": 0, "new": 0}
    for message, expected in CASES:
        got = {"old": old_label(message), "new": new_classify(message)}
        row = {"message": message, "expected": expected, "old": got["old"], "new": got["new"]}
        for which in ("old", "new"):
            ok = got[which] == expected
            row[f"{which}_ok"] = ok
            tallies[which][category(expected)][0] += ok
            tallies[which][category(expected)][1] += 1
            tallies[which]["all"][0] += ok
            tallies[which]["all"][1] += 1
            if expected == "model" and got[which] != "model":
                false_intercepts[which] += 1
        rows.append(row)

    results = {"messages": len(CASES), "models_calls_made": 0,
               "note": "small hand-written set; shows the kinds of mistakes, not a rate for real traffic"}
    for which in ("old", "new"):
        results[which] = {"correct": tallies[which]["all"][0], "accuracy_pct": pct(*tallies[which]["all"]),
                          "by_kind": {k: f"{c}/{n}" for k, (c, n) in sorted(tallies[which].items()) if k != "all"},
                          "questions_wrongly_taken_from_the_model": false_intercepts[which]}
    out = HERE / "results"
    out.mkdir(exist_ok=True)
    (out / "results.json").write_text(json.dumps(results, indent=2))
    with open(out / "cases.csv", "w", newline="") as f:
        w = csv.DictWriter(f, ["message", "expected", "old", "new", "old_ok", "new_ok"])
        w.writeheader()
        w.writerows(rows)
    print(json.dumps(results, indent=2))
    print("\nstill wrong with the new rules:")
    for r in rows:
        if not r["new_ok"]:
            print(f"  {r['message']!r}: expected {r['expected']}, got {r['new']}")


if __name__ == "__main__":
    main()
