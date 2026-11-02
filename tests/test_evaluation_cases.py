import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "evaluation"))

import evaluate  # noqa: E402
from cases import CASES  # noqa: E402
from legacy_intents import legacy_classify  # noqa: E402


def test_the_new_rules_handle_almost_all_labelled_messages_and_beat_the_old_ones():
    new = sum(evaluate.new_classify(m) == want for m, want in CASES)
    old = sum(evaluate.old_label(m) == want for m, want in CASES)
    assert new >= 0.95 * len(CASES) and new > old + 40


def test_the_old_rules_are_reproduced_as_they_were():
    assert legacy_classify("My name is Sam") == ("name", "My name is Sam")            # capital M: the split found nothing
    assert legacy_classify("what time did Rome fall") == ("time",)
    assert legacy_classify("how do weather balloons work") == ("weather",)
