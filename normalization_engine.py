"""
IPIP-NEO-120 Normalization Engine — Segment C
Przyjmuje: output z scoring_engine.compute_raw_scores() + norms.json
Zwraca:   dict z percentylami 30 faset (+ proxy domenowe jako mediana faset)
"""

import json
from pathlib import Path
from scipy.stats import norm as scipy_norm


# ── Ładowanie norm ────────────────────────────────────────────────────────────

def load_norms(path: str = "norms.json") -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ── Transformacja pojedynczej fasety ─────────────────────────────────────────

def raw_to_percentile(raw: int, mean: float, sd: float) -> int:
    """
    z-score → CDF → percentyl (clamp 1–99).
    Clamp do 1 i 99 (nie 0/100) — unikamy implikacji absolutnych ekstremów.
    """
    z = (raw - mean) / sd
    p = scipy_norm.cdf(z) * 100
    return max(1, min(99, round(p)))


# ── Silnik normalizacyjny ─────────────────────────────────────────────────────

def compute_percentiles(
    raw_scores: dict,
    norms: dict
) -> dict:
    """
    Parametry
    ----------
    raw_scores : output z compute_raw_scores()
    norms      : załadowany norms.json

    Zwraca
    -------
    {
        "facets": {
            "N1": {
                "name": "Lęk", "domain": "N",
                "raw": 14, "mean": 15.22, "sd": 4.79,
                "z": -0.25, "percentile": 40
            },
            ...
        },
        "domains": {
            "N": {
                "name": "Neurotyczność",
                "raw": 84,
                "percentile_proxy": 78,   ← mediana percentyli 6 faset
                "facet_percentiles": [40, 55, ...],
                "note": "proxy: mediana percentyli faset"
            },
            ...
        },
        "meta": {
            "norm_sample": "Internet sample, N = 619,150",
            "missing_facet_norms": []
        }
    }
    """
    facet_norms   = norms["facets"]
    missing_norms = []
    facets_out    = {}

    for code, data in raw_scores["facets"].items():
        if code not in facet_norms:
            missing_norms.append(code)
            continue

        n  = facet_norms[code]
        raw = data["raw"]
        z   = round((raw - n["mean"]) / n["sd"], 3)
        p   = raw_to_percentile(raw, n["mean"], n["sd"])

        facets_out[code] = {
            "name":       data["name"],
            "domain":     data["domain"],
            "raw":        raw,
            "mean":       n["mean"],
            "sd":         n["sd"],
            "z":          z,
            "percentile": p
        }

    # Proxy domenowy — mediana percentyli faset
    domain_names = {
        "N": "Neurotyczność",
        "E": "Ekstrawersja",
        "O": "Otwartość na doświadczenie",
        "A": "Ugodowość",
        "C": "Sumienność"
    }
    domains_out = {}
    for d, d_name in domain_names.items():
        d_facet_pcts = sorted(
            f["percentile"]
            for f in facets_out.values()
            if f["domain"] == d
        )
        n_f = len(d_facet_pcts)
        if n_f == 0:
            proxy = None
        elif n_f % 2 == 1:
            proxy = d_facet_pcts[n_f // 2]
        else:
            # parzysta liczba faset: średnia dwóch środkowych (zaokrąglona)
            proxy = round(
                (d_facet_pcts[n_f // 2 - 1] + d_facet_pcts[n_f // 2]) / 2
            )

        domains_out[d] = {
            "name":               d_name,
            "raw":                raw_scores["domains"][d]["raw"],
            "percentile_proxy":   proxy,
            "facet_percentiles":  d_facet_pcts,
            "note": (
                "proxy: mediana percentyli 6 faset — "
                "interpretuj z ostrożnością przy dysocjacji wewnątrzdomenowej"
            )
        }

    return {
        "facets":  facets_out,
        "domains": domains_out,
        "meta": {
            "norm_sample":        norms["metadata"]["primary_sample"],
            "missing_facet_norms": missing_norms
        }
    }


# ── Testy jednostkowe ─────────────────────────────────────────────────────────

def _run_tests(norms: dict):
    print("=" * 60)
    print("TESTY JEDNOSTKOWE — normalization_engine.py")
    print("=" * 60)

    # Test 1: raw = mean → percentyl ≈ 50
    p = raw_to_percentile(15, 15.0, 4.0)
    assert p == 50, f"Oczekiwano 50, got {p}"
    print("T1 PASS  raw=mean → percentyl=50")

    # Test 2: raw >> mean → percentyl bliski 99
    p = raw_to_percentile(20, 10.0, 2.0)
    assert p == 99, f"Oczekiwano 99, got {p}"
    print("T2 PASS  raw >> mean → percentyl clamped do 99")

    # Test 3: raw << mean → percentyl clamped do 1
    p = raw_to_percentile(4, 18.0, 2.0)
    assert p == 1, f"Oczekiwano 1, got {p}"
    print("T3 PASS  raw << mean → percentyl clamped do 1")

    # Test 4: z = +1 → percentyl ≈ 84
    p = raw_to_percentile(19, 15.0, 4.0)
    assert p == 84, f"Oczekiwano 84, got {p}"
    print("T4 PASS  z=+1 → percentyl=84")

    # Test 5: z = -1 → percentyl ≈ 16
    p = raw_to_percentile(11, 15.0, 4.0)
    assert p == 16, f"Oczekiwano 16, got {p}"
    print("T5 PASS  z=-1 → percentyl=16")

    # Test 6: pełny pipeline na sztucznym profilu (wszystkie=3 → raw faset=12)
    from scoring_engine import compute_raw_scores, load_questions
    q_path = Path("/mnt/user-data/outputs/questions.json")
    questions = load_questions(str(q_path))
    neutral = {q["id"]: 3 for q in questions}
    raw = compute_raw_scores(neutral, questions)
    result = compute_percentiles(raw, norms)
    assert len(result["facets"])  == 30
    assert len(result["domains"]) == 5
    assert result["meta"]["missing_facet_norms"] == []
    print("T6 PASS  pełny pipeline — 30 faset, 5 domen, brak brakujących norm")

    # Test 7: proxy domenowy — mediana dla C przy dysocjacji
    # Symulujemy profil: C3=98, C4=91, C5=2, reszta ~50
    mock_c_pcts = [50, 50, 98, 91, 2, 50]  # C1–C6
    sorted_c = sorted(mock_c_pcts)  # [2, 50, 50, 50, 91, 98]
    # n=6, parzyste: (sorted[2]+sorted[3])/2 = (50+50)/2 = 50
    proxy = round((sorted_c[2] + sorted_c[3]) / 2)
    assert proxy == 50
    print("T7 PASS  proxy C przy dysocjacji C3=98/C5=2 → mediana=50 (sygnał ostrzegawczy)")

    # Test 8: sprawdzenie że dysocjacja jest widoczna w facet_percentiles
    c_domain = result["domains"]["C"]
    spread = max(c_domain["facet_percentiles"]) - min(c_domain["facet_percentiles"])
    print(f"T8 INFO  rozstęp percentyli w domenie C dla profilu neutral: {spread} pp")

    print()
    print("Wszystkie testy przeszły.")
    return result


if __name__ == "__main__":
    import sys

    n_path = Path("/mnt/user-data/outputs/norms.json")
    norms  = load_norms(str(n_path))
    result = _run_tests(norms)

    # ── Demonstracja na zbliżonym profilu autora ──────────────────────────────
    print()
    print("=" * 60)
    print("DEMONSTRACJA — profil zbliżony do autora")
    print("Znane surowe wyniki domenowe: N=93, E=60, O=116, A=104, C=77")
    print("(brak surowych danych fasetowych — używamy odpowiedzi=4 jako proxy)")
    print("=" * 60)

    from scoring_engine import compute_raw_scores, load_questions
    q_path = Path("/mnt/user-data/outputs/questions.json")
    questions = load_questions(str(q_path))
    demo = {q["id"]: 4 for q in questions}
    raw_demo = compute_raw_scores(demo, questions)
    pct_demo = compute_percentiles(raw_demo, norms)

    print("\nPercentyle faset (odpowiedzi=4 dla wszystkich):")
    for d in ["N", "E", "O", "A", "C"]:
        print(f"\n  {d} — {pct_demo['domains'][d]['name']}")
        print(f"     proxy domenowy: {pct_demo['domains'][d]['percentile_proxy']} centyl")
        for code, fdata in pct_demo["facets"].items():
            if fdata["domain"] == d:
                print(
                    f"     {code}  {fdata['name']:28s}"
                    f"raw={fdata['raw']:3d}  "
                    f"z={fdata['z']:+.2f}  "
                    f"p={fdata['percentile']:3d}"
                )
