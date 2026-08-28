"""Grade a licence-compliance audit against the determinations in the
author's DATA_SOURCES.md for the-light.

The graded axis is a single boolean per source: may this ARTIFACT be embedded
and redistributed under a permissive, no-share-alike policy. The traps are all
one family — the status of the WORK is not the licence of the ARTIFACT.
"""
import json
from pathlib import Path
import pytest

OUTPUT = Path("/app/audit.json")

# id -> (embeddable, why the author decided that)
TRUTH = {
    1:  (False, "getBible kjv.json: PD text but the artifact self-labels distribution_license=GPL and getBible asks it not be redistributed"),
    2:  (False, "getBible web.json: same GPL-labelled artifact problem"),
    3:  (False, "getBible almeida.json: PD text, GPL-labelled artifact"),
    4:  (True,  "scrollmapper ASV: public domain, per-translation licence field says so"),
    5:  (True,  "scrollmapper YLT: public domain"),
    6:  (False, "scrollmapper AKJV: licence is per-translation, AKJV is non-commercial only"),
    7:  (True,  "OpenBible cross references via scrollmapper mirror: CC-BY, attribution to OpenBible"),
    8:  (False, "bibleapi-bibles-json: text is PD but the repo carries no LICENSE at all, so no legal basis"),
    9:  (True,  "aruljohn/Bible-kjv: public domain KJV"),
    10: (True,  "wldeh/bible-api en-kjv only: that translation is public domain"),
    11: (False, "damarals JFAA: copyrighted"),
    12: (False, "open-bibles por-almeida.usfx.xml: copyrighted"),
    13: (False, "thiagobodruk aa.json: copyrighted content inside a CC-licensed wrapper; the wrapper does not launder it"),
    14: (False, "gratis-bible pt/port.xml: rights tag is empty, zero licence evidence"),
    15: (False, "gratis-bible pt/acf.xml: copyrighted (Trinitarian Bible Society)"),
}


@pytest.fixture(scope="session")
def verdicts():
    if not OUTPUT.exists():
        pytest.fail(f"{OUTPUT} was never written")
    data = json.loads(OUTPUT.read_text())
    out = {}
    for entry in data.get("verdicts", []):
        out[int(entry["id"])] = bool(entry["embeddable"])
    return out


def test_every_source_received_a_verdict(verdicts):
    missing = sorted(set(TRUTH) - set(verdicts))
    assert not missing, f"no verdict for ids {missing}"


def test_every_verdict_is_correct(verdicts):
    wrong = []
    for sid, (expected, why) in TRUTH.items():
        got = verdicts.get(sid)
        if got is None:
            continue
        if got != expected:
            wrong.append(f"  id {sid}: said {got}, correct is {expected} — {why}")
    assert not wrong, (
        f"{len(wrong)} of {len(TRUTH)} verdicts wrong:\n" + "\n".join(wrong)
    )
