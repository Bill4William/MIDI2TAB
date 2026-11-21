"""
Generate golden test data for the Android port of the theory engine.

The Kotlin engine (android/app/src/main/java/.../theory/MusicTheory.kt) must
reproduce src/music_theory.py exactly; its unit tests compare against the
JSON this script writes. Re-run after changing src/music_theory.py:

    python tools/gen_theory_golden.py
"""

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import music_theory as mt  # noqa: E402

TUNINGS = {
    "guitar6": [64, 59, 55, 50, 45, 40],
    "bass4": [43, 38, 33, 28],
    "dadgad": [62, 57, 55, 50, 45, 38],
    "guitar7": [64, 59, 55, 50, 45, 40, 35],
    "uke": [69, 64, 60, 67],
}


def main() -> None:
    out = {"scales": [], "diatonic": [], "chords": [], "voicings": []}

    for fam in mt.SCALE_FAMILIES.values():
        for mi, mode in enumerate(fam.mode_names):
            ivs = mt.mode_intervals(fam.name, mi)
            for root in range(12):
                out["scales"].append({
                    "family": fam.name, "mode": mi, "root": root,
                    "intervals": ivs,
                    "names": mt.spell_scale(root, ivs),
                    "degrees": mt.degree_labels(ivs),
                })
                if len(ivs) == 7:
                    for sev in (False, True):
                        out["diatonic"].append({
                            "family": fam.name, "mode": mi, "root": root,
                            "sevenths": sev,
                            "chords": [[num, pc, c.name if c else None]
                                       for num, pc, c in
                                       mt.diatonic_chords(root, ivs, sev)],
                        })

    for c in mt.CHORD_TYPES.values():
        for root in range(12):
            sp = mt.spell_chord(root, c)
            out["chords"].append({
                "type": c.name, "root": root,
                "spelled": {str(k): v for k, v in sp.items()},
            })

    cases = []
    for tname in ("guitar6", "bass4", "dadgad"):
        for c in mt.CHORD_TYPES.values():
            for root in range(12):
                cases.append((tname, root, c.name, 4, True))
    for c in mt.CHORD_TYPES.values():
        for root in (0, 4, 7, 9):
            cases.append(("guitar6", root, c.name, 4, False))
            cases.append(("guitar6", root, c.name, 3, True))
            cases.append(("guitar7", root, c.name, 4, True))
            cases.append(("uke", root, c.name, 4, True))
    for tname, root, cname, span, rib in cases:
        vs = mt.find_voicings(TUNINGS[tname], root, mt.CHORD_TYPES[cname],
                              max_span=span, root_in_bass=rib)
        out["voicings"].append({
            "tuning": TUNINGS[tname], "root": root, "type": cname,
            "span": span, "rootInBass": rib,
            "shapes": [v.shape() for v in vs],
            "scores": [round(v.score, 6) for v in vs],
            "best": mt.best_voicing_index(vs),
        })

    path = os.path.join(ROOT, "android", "app", "src", "test", "resources",
                        "theory_golden.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, separators=(",", ":"))
    print(f"wrote {path}: {len(out['scales'])} scales, "
          f"{len(out['diatonic'])} diatonic sets, {len(out['chords'])} chords, "
          f"{len(out['voicings'])} voicing searches")


if __name__ == "__main__":
    main()
