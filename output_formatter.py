"""
IPIP-NEO-120 Output Formatter
Przyjmuje: output z normalization_engine.compute_percentiles()
Zwraca:   sformatowany tekst gotowy do wklejenia do LLM
"""

from datetime import datetime


def detect_dissociations(facets: dict, threshold: int = 40) -> list[dict]:
    """Wykrywa dysocjacje wewnątrzdomenowe (rozstęp percentyli >= threshold)."""
    result = []
    for d in ["N", "E", "O", "A", "C"]:
        d_facets = {k: v for k, v in facets.items() if v["domain"] == d}
        pcts = {k: v["percentile"] for k, v in d_facets.items()}
        spread = max(pcts.values()) - min(pcts.values())
        if spread >= threshold:
            result.append({
                "domain":    d,
                "spread":    spread,
                "max_facet": max(pcts, key=pcts.get),
                "max_pct":   max(pcts.values()),
                "min_facet": min(pcts, key=pcts.get),
                "min_pct":   min(pcts.values()),
            })
    return result


def format_for_llm(results: dict, include_prompt_template: bool = True) -> str:
    facets  = results["facets"]
    domains = results["domains"]

    lines = []
    lines.append("=" * 62)
    lines.append("PROFIL OSOBOWOŚCI — IPIP-NEO-120")
    lines.append(f"Data:  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("Norma: próba internetowa N=619,150 (Johnson, 2014, Table 2)")
    lines.append("=" * 62)

    # Domeny
    lines.append("\nWYNIKI DOMENOWE  (proxy = mediana percentyli 6 faset)")
    lines.append("-" * 62)
    for d in ["N", "E", "O", "A", "C"]:
        dom = domains[d]
        bar = _bar(dom["percentile_proxy"])
        lines.append(
            f"  {d}  {dom['name']:<30s}  {dom['percentile_proxy']:>3d}. centyl  {bar}"
        )

    # Fasety
    lines.append("\nWYNIKI FASETOWE  (30 faset)")
    lines.append("-" * 62)
    for d in ["N", "E", "O", "A", "C"]:
        lines.append(f"\n  {d} — {domains[d]['name']}")
        for code, fdata in facets.items():
            if fdata["domain"] == d:
                bar = _bar(fdata["percentile"])
                lines.append(
                    f"    {code}  {fdata['name']:<28s}"
                    f"  {fdata['percentile']:>3d}. centyl  {bar}"
                    f"  (raw={fdata['raw']:2d}, z={fdata['z']:+.2f})"
                )

    # Dysocjacje
    diss = detect_dissociations(facets, threshold=40)
    if diss:
        lines.append("\nDYSOCJACJE WEWNĄTRZDOMENOWE  (rozstęp ≥ 40 pp)")
        lines.append("-" * 62)
        lines.append("  Wynik domenowy jest mniej informatywny — patrz fasety.")
        for d in diss:
            max_name = facets[d["max_facet"]]["name"]
            min_name = facets[d["min_facet"]]["name"]
            lines.append(
                f"  {d['domain']}:  {d['max_facet']} {max_name} = {d['max_pct']}. centyl"
                f"  vs  {d['min_facet']} {min_name} = {d['min_pct']}. centyl"
                f"  (rozstęp: {d['spread']} pp)"
            )

    # Ekstrema
    all_pcts = {k: v["percentile"] for k, v in facets.items()}
    very_high = {k: v for k, v in all_pcts.items() if v >= 85}
    very_low  = {k: v for k, v in all_pcts.items() if v <= 15}

    if very_high:
        lines.append("\nFASETY BARDZO WYSOKIE  (≥ 85. centyl)")
        lines.append("-" * 62)
        for code, pct in sorted(very_high.items(), key=lambda x: -x[1]):
            lines.append(f"  {code}  {facets[code]['name']:<28s}  {pct:>3d}. centyl")

    if very_low:
        lines.append("\nFASETY BARDZO NISKIE  (≤ 15. centyl)")
        lines.append("-" * 62)
        for code, pct in sorted(very_low.items(), key=lambda x: x[1]):
            lines.append(f"  {code}  {facets[code]['name']:<28s}  {pct:>3d}. centyl")

    # Braki w normach
    missing = results["meta"].get("missing_facet_norms", [])
    if missing:
        lines.append(f"\nUWAGA: brak norm dla faset: {', '.join(missing)}")

    if include_prompt_template:
        lines.append("\n" + "=" * 62)
        lines.append("SUGEROWANY PROMPT DLA LLM")
        lines.append("=" * 62)
        lines.append(
            "Powyżej znajduje się mój profil osobowości z testu IPIP-NEO-120 "
            "(120-pytaniowy inwentarz oparty na modelu Wielkiej Piątki, Big Five). "
            "Wyniki podane są w percentylach względem próby internetowej N=619,150 "
            "(Johnson, 2014). Percentyl 50 = wynik przeciętny dla tej populacji.\n"
            "\n"
            "Proszę o:\n"
            "1. Interpretację psychologiczną profilu — ze szczególnym uwzględnieniem "
            "dysocjacji wewnątrzdomenowych i wzorców nieoczywistych "
            "(np. wysokie dążenie do osiągnięć przy niskiej samodyscyplinie).\n"
            "2. Wskazanie 3-5 obszarów zawodowych / ścieżek kariery spójnych "
            "z profilem z uzasadnieniem.\n"
            "3. Wskazanie 2-3 obszarów zawodowych wyraźnie niespójnych z profilem.\n"
            "4. Hipotezy rozwojowe lub kliniczne wynikające z profilu "
            "(bez diagnozowania — jako punkty do refleksji własnej)."
        )

    return "\n".join(lines)


def _bar(pct: int, width: int = 20) -> str:
    """Mini pasek tekstowy reprezentujący percentyl."""
    filled = round(pct / 100 * width)
    return "[" + "█" * filled + "░" * (width - filled) + "]"
