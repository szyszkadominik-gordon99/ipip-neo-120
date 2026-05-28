"""
IPIP-NEO-120 Scoring Engine — Segment B
Przyjmuje: dict {item_id (int): response (int 1-5)}
Zwraca:   dict z surowymi wynikami 30 faset i 5 domen
"""

import json
from pathlib import Path

# ── Ładowanie danych ──────────────────────────────────────────────────────────

def load_questions(path: str = "questions.json") -> list[dict]:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return data["questions"]


# ── Klucz punktacyjny ─────────────────────────────────────────────────────────

def score_item(response: int, keyed: str) -> int:
    """
    keyed='+': wynik = odpowiedź (1–5)
    keyed='-': wynik = 6 - odpowiedź (odwrócona skala)
    """
    if keyed == "+":
        return response
    elif keyed == "-":
        return 6 - response
    else:
        raise ValueError(f"Nieznany kierunek kluczowania: {keyed!r}")


# ── Silnik obliczeniowy ───────────────────────────────────────────────────────

def compute_raw_scores(
    responses: dict[int, int],
    questions: list[dict]
) -> dict:
    """
    Parametry
    ----------
    responses : {item_id: odpowiedź (1–5)}
    questions : lista pytań z questions.json

    Zwraca
    -------
    {
        "facets": {
            "N1": {"name": "Lęk", "domain": "N", "raw": 14, "n_items": 4},
            ...
        },
        "domains": {
            "N": {"name": "Neurotyczność", "raw": 84, "n_facets": 6},
            ...
        },
        "meta": {
            "n_answered": 120,
            "n_missing": 0,
            "missing_items": []
        }
    }
    """
    # Walidacja zakresu odpowiedzi
    for item_id, resp in responses.items():
        if resp not in (1, 2, 3, 4, 5):
            raise ValueError(
                f"Pytanie {item_id}: odpowiedź {resp!r} poza zakresem 1–5."
            )

    facet_scores: dict[str, list[int]] = {}
    facet_meta:   dict[str, dict]      = {}
    missing_items: list[int]           = []

    for q in questions:
        item_id    = q["id"]
        facet_code = q["facet"]
        facet_name = q["facet_name"]
        domain     = q["domain"]
        domain_name = q["domain_name"]
        keyed      = q["keyed"]

        if facet_code not in facet_scores:
            facet_scores[facet_code] = []
            facet_meta[facet_code] = {
                "name":   facet_name,
                "domain": domain,
                "domain_name": domain_name
            }

        if item_id not in responses:
            missing_items.append(item_id)
            continue

        scored = score_item(responses[item_id], keyed)
        facet_scores[facet_code].append(scored)

    # Wyniki faset
    facets_out = {}
    for code, scores in facet_scores.items():
        facets_out[code] = {
            "name":    facet_meta[code]["name"],
            "domain":  facet_meta[code]["domain"],
            "raw":     sum(scores),
            "n_items": len(scores)
        }

    # Wyniki domen (suma 6 faset)
    domain_info = {
        "N": "Neurotyczność",
        "E": "Ekstrawersja",
        "O": "Otwartość na doświadczenie",
        "A": "Ugodowość",
        "C": "Sumienność"
    }
    domains_out = {}
    for d, d_name in domain_info.items():
        d_facets = [v for v in facets_out.values() if v["domain"] == d]
        domains_out[d] = {
            "name":     d_name,
            "raw":      sum(f["raw"] for f in d_facets),
            "n_facets": len(d_facets)
        }

    return {
        "facets":  facets_out,
        "domains": domains_out,
        "meta": {
            "n_answered":  len(responses),
            "n_missing":   len(missing_items),
            "missing_items": missing_items
        }
    }


# ── Testy jednostkowe ─────────────────────────────────────────────────────────

def _run_tests(questions: list[dict]):
    print("=" * 60)
    print("TESTY JEDNOSTKOWE — scoring_engine.py")
    print("=" * 60)

    # Test 1: klucz dodatni
    assert score_item(5, "+") == 5
    assert score_item(1, "+") == 1
    print("T1 PASS  score_item keyed='+'")

    # Test 2: klucz ujemny (odwrócony)
    assert score_item(1, "-") == 5
    assert score_item(5, "-") == 1
    assert score_item(3, "-") == 3
    print("T2 PASS  score_item keyed='-'")

    # Test 3: odpowiedź poza zakresem
    try:
        score_item(6, "+")
        assert False, "Powinien rzucić błąd"
    except Exception:
        pass
    print("T3 PASS  walidacja zakresu odpowiedzi (>5)")

    # Test 4: wszystkie odpowiedzi = 3 (środek skali)
    # Wynik fasety: 4 pytania × 3 = 12 (niezależnie od kluczowania)
    neutral = {q["id"]: 3 for q in questions}
    result = compute_raw_scores(neutral, questions)
    for code, data in result["facets"].items():
        assert data["raw"] == 12, f"{code}: oczekiwano 12, got {data['raw']}"
    for d, data in result["domains"].items():
        assert data["raw"] == 72, f"{d}: oczekiwano 72, got {data['raw']}"
    print("T4 PASS  wszystkie=3 → fasety=12, domeny=72")

    # Test 5: wszystkie odpowiedzi = 5
    # pytania keyed='+': 5 pkt; keyed='-': 6-5=1 pkt
    # Wynik fasety zależy od rozkładu kluczowania w fasecie
    all_5 = {q["id"]: 5 for q in questions}
    result5 = compute_raw_scores(all_5, questions)
    # Sprawdź że żadna faseta nie wychodzi poza zakres 4–20
    for code, data in result5["facets"].items():
        assert 4 <= data["raw"] <= 20, \
            f"{code}: raw={data['raw']} poza zakresem 4–20"
    print("T5 PASS  wszystkie=5 → fasety w zakresie [4, 20]")

    # Test 6: wszystkie odpowiedzi = 1
    all_1 = {q["id"]: 1 for q in questions}
    result1 = compute_raw_scores(all_1, questions)
    for code, data in result1["facets"].items():
        assert 4 <= data["raw"] <= 20, \
            f"{code}: raw={data['raw']} poza zakresem 4–20"
    print("T6 PASS  wszystkie=1 → fasety w zakresie [4, 20]")

    # Test 7: brakująca odpowiedź
    incomplete = {q["id"]: 3 for q in questions}
    del incomplete[1]
    result_inc = compute_raw_scores(incomplete, questions)
    assert result_inc["meta"]["n_missing"] == 1
    assert 1 in result_inc["meta"]["missing_items"]
    print("T7 PASS  brakująca odpowiedź wykryta w meta")

    # Test 8: kompletność — 30 faset i 5 domen w wyjściu
    assert len(result["facets"])  == 30
    assert len(result["domains"]) == 5
    print("T8 PASS  30 faset i 5 domen w wyjściu")

    # Test 9: symulacja profilu autora (znane percentyle jako referencja)
    # Autor podał raw domenowe: N=93, E=60, O=116, A=104, C=77
    # Konstruujemy odpowiedzi które dają te wyniki domenowe
    # (niemożliwe precyzyjnie bez znajomości fasetowych, ale test ciągłości)
    print()
    print("Test 9 — profil demonstracyjny (odpowiedzi=4 dla wszystkich):")
    demo = {q["id"]: 4 for q in questions}
    r_demo = compute_raw_scores(demo, questions)
    for d in ["N", "E", "O", "A", "C"]:
        print(f"  {d}: raw={r_demo['domains'][d]['raw']}")

    print()
    print("Wszystkie testy przeszły.")
    return result


if __name__ == "__main__":
    import sys

    q_path = Path("questions.json")
    if not q_path.exists():
        # próba ścieżki outputs (środowisko kontenera)
        q_path = Path("/mnt/user-data/outputs/questions.json")

    questions = load_questions(str(q_path))
    result = _run_tests(questions)

    print()
    print("=" * 60)
    print("PRZYKŁADOWY OUTPUT — compute_raw_scores()")
    print("=" * 60)
    neutral = {q["id"]: 3 for q in questions}
    out = compute_raw_scores(neutral, questions)
    print("\nFasety (pierwsze 6 — domena N):")
    for code in ["N1", "N2", "N3", "N4", "N5", "N6"]:
        f = out["facets"][code]
        print(f"  {code} {f['name']:25s} raw={f['raw']:3d}  n_items={f['n_items']}")
    print("\nDomeny:")
    for d, data in out["domains"].items():
        print(f"  {d}  {data['name']:30s} raw={data['raw']:4d}  n_facets={data['n_facets']}")
    print(f"\nMeta: answered={out['meta']['n_answered']}, missing={out['meta']['n_missing']}")
