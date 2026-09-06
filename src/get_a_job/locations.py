from __future__ import annotations

import re
from collections.abc import Iterable


COUNTRY_NAMES: dict[str, tuple[str, ...]] = {
    "US": ("united states", "united states of america", "usa", "u.s.", "u.s.a."),
    "CA": ("canada",),
    "MX": ("mexico",),
    "IE": ("ireland",),
    "CN": ("china",),
    "GB": ("united kingdom", "uk", "england", "northern ireland"),
    "DE": ("germany",),
    "ES": ("spain",),
    "FR": ("france",),
    "AT": ("austria",),
    "BE": ("belgium",),
    "BG": ("bulgaria",),
    "HR": ("croatia",),
    "CY": ("cyprus",),
    "CZ": ("czechia", "czech republic"),
    "DK": ("denmark",),
    "FI": ("finland",),
    "GR": ("greece",),
    "HU": ("hungary",),
    "LT": ("lithuania",),
    "LU": ("luxembourg",),
    "LV": ("latvia",),
    "MT": ("malta",),
    "RO": ("romania",),
    "SI": ("slovenia",),
    "SK": ("slovakia",),
    "AU": ("australia",),
    "IN": ("india",),
    "JP": ("japan",),
    "SG": ("singapore",),
    "IT": ("italy",),
    "NL": ("netherlands",),
    "SE": ("sweden",),
    "CH": ("switzerland",),
    "PL": ("poland",),
    "PT": ("portugal",),
    "BR": ("brazil",),
    "AR": ("argentina",),
    "CO": ("colombia",),
    "EE": ("estonia",),
    "KR": ("south korea",),
    "IL": ("israel",),
    "NZ": ("new zealand",),
    "ZA": ("south africa",),
    "AE": ("united arab emirates",),
    "AD": ("andorra",),
    "AF": ("afghanistan",),
    "AL": ("albania",),
    "AO": ("angola",),
    "BA": ("bosnia and herzegovina", "bosnia"),
    "BD": ("bangladesh",),
    "BH": ("bahrain",),
    "BJ": ("benin",),
    "BN": ("brunei",),
    "BO": ("bolivia",),
    "BT": ("bhutan",),
    "BW": ("botswana",),
    "BY": ("belarus",),
    "BZ": ("belize",),
    "BF": ("burkina faso",),
    "BI": ("burundi",),
    "CD": ("democratic republic of the congo", "dr congo", "drc"),
    "CF": ("central african republic",),
    "CG": ("republic of the congo", "congo republic"),
    "CI": ("cote d'ivoire", "côte d’ivoire", "ivory coast"),
    "CL": ("chile",),
    "CM": ("cameroon",),
    "CR": ("costa rica",),
    "CU": ("cuba",),
    "CV": ("cabo verde", "cape verde"),
    "DJ": ("djibouti",),
    "DO": ("dominican republic",),
    "DZ": ("algeria",),
    "EC": ("ecuador",),
    "EG": ("egypt",),
    "ER": ("eritrea",),
    "ET": ("ethiopia",),
    "FJ": ("fiji",),
    "GA": ("gabon",),
    "GF": ("french guiana",),
    "GH": ("ghana",),
    "GM": ("gambia", "the gambia"),
    "GN": ("guinea",),
    "GQ": ("equatorial guinea",),
    "GT": ("guatemala",),
    "GW": ("guinea-bissau", "guinea bissau"),
    "GY": ("guyana",),
    "HK": ("hong kong",),
    "HN": ("honduras",),
    "HT": ("haiti",),
    "ID": ("indonesia",),
    "IQ": ("iraq",),
    "IR": ("iran",),
    "IS": ("iceland",),
    "JM": ("jamaica",),
    "JO": ("jordan",),
    "KE": ("kenya",),
    "KG": ("kyrgyzstan",),
    "KH": ("cambodia",),
    "KI": ("kiribati",),
    "KM": ("comoros",),
    "KZ": ("kazakhstan",),
    "KW": ("kuwait",),
    "LA": ("laos", "lao people's democratic republic"),
    "LB": ("lebanon",),
    "LK": ("sri lanka",),
    "LR": ("liberia",),
    "LS": ("lesotho",),
    "LY": ("libya",),
    "MA": ("morocco",),
    "MC": ("monaco",),
    "MD": ("moldova",),
    "ME": ("montenegro",),
    "MG": ("madagascar",),
    "MH": ("marshall islands",),
    "MK": ("north macedonia", "macedonia"),
    "ML": ("mali",),
    "MM": ("myanmar", "burma"),
    "MN": ("mongolia",),
    "MR": ("mauritania",),
    "MU": ("mauritius",),
    "MV": ("maldives",),
    "MW": ("malawi",),
    "MY": ("malaysia",),
    "MZ": ("mozambique",),
    "NA": ("namibia",),
    "NE": ("niger",),
    "NG": ("nigeria",),
    "NI": ("nicaragua",),
    "NO": ("norway",),
    "NP": ("nepal",),
    "NR": ("nauru",),
    "OM": ("oman",),
    "PA": ("panama",),
    "PE": ("peru",),
    "PG": ("papua new guinea",),
    "PH": ("philippines",),
    "PK": ("pakistan",),
    "PR": ("puerto rico",),
    "PS": ("palestine", "palestinian territories"),
    "PY": ("paraguay",),
    "QA": ("qatar",),
    "RS": ("serbia",),
    "RU": ("russia", "russian federation"),
    "RW": ("rwanda",),
    "SA": ("saudi arabia",),
    "SB": ("solomon islands",),
    "SC": ("seychelles",),
    "SD": ("sudan",),
    "SL": ("sierra leone",),
    "SM": ("san marino",),
    "SN": ("senegal",),
    "SO": ("somalia",),
    "SR": ("suriname",),
    "SS": ("south sudan",),
    "ST": ("sao tome and principe", "são tomé and príncipe"),
    "SV": ("el salvador",),
    "SZ": ("eswatini", "swaziland"),
    "SY": ("syria",),
    "TD": ("chad",),
    "TG": ("togo",),
    "TH": ("thailand",),
    "TJ": ("tajikistan",),
    "TL": ("timor-leste", "east timor"),
    "TM": ("turkmenistan",),
    "TN": ("tunisia",),
    "TO": ("tonga",),
    "TR": ("turkey", "türkiye"),
    "TV": ("tuvalu",),
    "TW": ("taiwan",),
    "TZ": ("tanzania",),
    "UA": ("ukraine",),
    "UG": ("uganda",),
    "UY": ("uruguay",),
    "UZ": ("uzbekistan",),
    "VA": ("vatican city",),
    "VE": ("venezuela",),
    "VN": ("vietnam", "viet nam"),
    "VU": ("vanuatu",),
    "WS": ("samoa",),
    "YE": ("yemen",),
    "ZM": ("zambia",),
    "ZW": ("zimbabwe",),
    "FM": ("micronesia", "federated states of micronesia"),
    "LI": ("liechtenstein",),
    "XK": ("kosovo",),
}

REGION_NAMES: dict[str, tuple[str, ...]] = {
    "EU": ("eu", "european union"),
    "EUROPE": ("europe",),
    "EMEA": ("emea", "europe, middle east and africa"),
    "LATAM": ("latam", "latin america", "latin america and the caribbean"),
    "APAC": ("apac", "asia pacific", "asia-pacific"),
}

EU_COUNTRIES = {
    "AT", "BE", "BG", "HR", "CY", "CZ", "DE", "DK", "EE", "ES", "FI",
    "FR", "GR", "HU", "IE", "IT", "LT", "LU", "LV", "MT", "NL", "PL",
    "PT", "RO", "SE", "SI", "SK",
}
EUROPE_COUNTRIES = EU_COUNTRIES | {
    "AD", "AL", "BA", "BY", "CH", "GB", "IS", "LI", "MC", "MD", "ME",
    "MK", "NO", "RS", "RU", "SM", "TR", "UA", "VA", "XK",
}
MIDDLE_EAST_COUNTRIES = {
    "AE", "BH", "EG", "IL", "IQ", "IR", "JO", "KW", "LB", "OM", "PS",
    "QA", "SA", "SY", "YE",
}
AFRICA_COUNTRIES = {
    "AO", "BF", "BI", "BJ", "BW", "CD", "CF", "CG", "CI", "CM", "CV",
    "DJ", "DZ", "EG", "ER", "ET", "GA", "GH", "GM", "GN", "GQ", "GW",
    "KE", "KM", "LR", "LS", "LY", "MA", "MG", "ML", "MR", "MU", "MW",
    "MZ", "NA", "NE", "NG", "RW", "SC", "SD", "SL", "SN", "SO", "SS",
    "ST", "SZ", "TD", "TG", "TN", "TZ", "UG", "ZA", "ZM", "ZW",
}
LATAM_COUNTRIES = {
    "AR", "BO", "BR", "BZ", "CL", "CO", "CR", "CU", "DO", "EC", "GF",
    "GT", "GY", "HN", "HT", "MX", "NI", "PA", "PE", "PR", "PY", "SR",
    "SV", "UY", "VE",
}
APAC_COUNTRIES = {
    "AF", "AU", "BD", "BN", "BT", "CN", "FJ", "FM", "HK", "ID", "IN",
    "JP", "KG", "KH", "KI", "KR", "KZ", "LA", "LK", "MH", "MM", "MN",
    "MV", "MY", "NP", "NR", "NZ", "PG", "PH", "PK", "SB", "SG", "TH",
    "TJ", "TL", "TM", "TO", "TV", "TW", "UZ", "VN", "VU", "WS",
}
REGION_COUNTRIES = {
    "EU": EU_COUNTRIES,
    "EUROPE": EUROPE_COUNTRIES,
    "EMEA": EUROPE_COUNTRIES | MIDDLE_EAST_COUNTRIES | AFRICA_COUNTRIES,
    "LATAM": LATAM_COUNTRIES,
    "APAC": APAC_COUNTRIES,
}

US_POSTAL_CODES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI", "ID",
    "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS",
    "MO", "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH", "OK",
    "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV",
    "WI", "WY", "DC",
}
SAFE_COUNTRY_CODES = set(COUNTRY_NAMES) - US_POSTAL_CODES

LOCATION_COUNTRY_HINTS = {
    "US": ("idaho", "california", "new york city", "san francisco", "washington, dc"),
    "IN": ("bengaluru", "karnataka"),
}


def _contains(text: str, phrase: str) -> bool:
    return re.search(
        r"(?<!\w)" + re.escape(phrase.lower()) + r"(?!\w)", text.lower()
    ) is not None


def normalize_country(value: str) -> str:
    """Normalize one user- or source-provided country name/code."""
    stripped = value.strip()
    upper = stripped.upper()
    if re.fullmatch(r"[A-Z]{2}", upper):
        return upper
    lowered = stripped.lower()
    return next(
        (
            code
            for code, aliases in COUNTRY_NAMES.items()
            if any(lowered == alias.lower() for alias in aliases)
        ),
        "",
    )


def normalize_region(value: str) -> str:
    stripped = value.strip()
    upper = stripped.upper()
    if upper in REGION_NAMES:
        return upper
    lowered = stripped.lower()
    return next(
        (
            region
            for region, aliases in REGION_NAMES.items()
            if any(lowered == alias.lower() for alias in aliases)
        ),
        "",
    )


def countries_from_text(value: str, *, structured: bool = False) -> list[str]:
    """Extract all explicit countries while avoiding US-state/code ambiguity."""
    text = value.strip()
    lowered_text = text.lower()
    found: set[str] = set()
    alias_matches: list[tuple[int, int, str]] = []
    for code, aliases in COUNTRY_NAMES.items():
        for alias in aliases:
            lowered_alias = alias.lower()
            if lowered_alias not in lowered_text:
                continue
            alias_matches.extend(
                (match.start(), match.end(), code)
                for match in re.finditer(
                    r"(?<!\w)" + re.escape(lowered_alias) + r"(?!\w)",
                    lowered_text,
                )
            )
    # Prefer the most specific overlapping country name. For example, South
    # Sudan must not also resolve as Sudan, and Papua New Guinea is not Guinea.
    accepted_spans: list[tuple[int, int]] = []
    for start, end, code in sorted(
        alias_matches,
        key=lambda match: (match[1] - match[0]),
        reverse=True,
    ):
        if any(
            start < accepted_end and accepted_start < end
            for accepted_start, accepted_end in accepted_spans
        ):
            continue
        accepted_spans.append((start, end))
        found.add(code)
    for code, hints in LOCATION_COUNTRY_HINTS.items():
        if any(_contains(text, hint) for hint in hints):
            found.add(code)

    tokens = set(re.findall(r"(?<![A-Z])[A-Z]{2}(?![A-Z])", text.upper()))
    found.update(tokens & SAFE_COUNTRY_CODES)
    if structured:
        # ATS location lists use slash/semicolon/parenthetical standalone codes.
        # Do not interpret comma-delimited address components such as CA or IN.
        found.update(
            re.findall(
                r"(?:^|[/;(])\s*([A-Z]{2})\s*(?=$|[/;)])",
                text.upper(),
            )
        )
    known_order = [code for code in COUNTRY_NAMES if code in found]
    return [*known_order, *sorted(found - set(known_order))]


def regions_from_text(value: str) -> list[str]:
    return [
        region
        for region, aliases in REGION_NAMES.items()
        if any(_contains(value, alias) for alias in aliases)
    ]


def eligible_targets_match(
    eligible_values: Iterable[str],
    job_countries: Iterable[str],
    job_regions: Iterable[str],
) -> bool | None:
    """Return whether any job country/region accepts the candidate's target area.

    ``None`` means the posting did not provide enough location scope to verify.
    """
    allowed_countries = {
        country for value in eligible_values if (country := normalize_country(value))
    }
    allowed_regions = {
        region for value in eligible_values if (region := normalize_region(value))
    }
    countries = {country.upper() for country in job_countries if country}
    regions = {region.upper() for region in job_regions if region}
    if not countries and not regions:
        return None
    if countries & allowed_countries:
        return True
    if any(
        country in REGION_COUNTRIES.get(region, set())
        for country in countries
        for region in allowed_regions
    ):
        return True
    if any(
        country in REGION_COUNTRIES.get(region, set())
        for country in allowed_countries
        for region in regions
    ):
        return True
    if any(
        REGION_COUNTRIES.get(allowed, set()) & REGION_COUNTRIES.get(offered, set())
        for allowed in allowed_regions
        for offered in regions
    ):
        return True
    return False


def primary_country(countries: Iterable[str]) -> str:
    values = list(countries)
    return "US" if "US" in values else values[0] if values else ""
