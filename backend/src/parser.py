import hashlib
import re
from typing import Any

from bs4 import BeautifulSoup

from .timeutils import utc_now

# Patterns are compiled once at import instead of on every call.

# Amount in Spanish notation: "." groups thousands in runs of three and "," is
# the decimal mark, so "1.234.567,89" is one million two hundred thousand and
# not one point something. Deliberately no \b: adjacent text nodes are joined by
# get_text, and a word boundary would miss the amount in "...amplio800€".
AMOUNT = r"\d{1,3}(?:\.\d{3})+(?:,\d{1,2})?|\d+(?:,\d{1,2})?"

# The euro sign is required, so plain figures such as "120.000 km" or
# "3 habitaciones" are never mistaken for a price.
RE_AMOUNT_EUR = re.compile(rf"({AMOUNT})\s*€|€\s*({AMOUNT})")

# Decides whether an element looks like an asset at all; same notation, so a
# price written as "€ 1.234,56" is recognised.
RE_PRICE_HINT = re.compile(rf"(?:{AMOUNT})\s*€|€\s*(?:{AMOUNT})")

# Minimum bid. The gap after the keyword excludes digits (so the match cannot
# skip over another figure) and also "." and ";" (so it cannot cross a sentence
# boundary and pick up an amount belonging to a different statement, as in
# "Puja mínima no publicada. Otros lotes desde 5.000€").
RE_PUJA = re.compile(
    rf"(?:puja|tipo de subasta)[^\d.;]{{0,30}}({AMOUNT})\s*€", re.IGNORECASE
)

RE_ID_CODE = re.compile(r"[A-Z]+-\d{4}-\d{3,}")
RE_ID_DIGITS = re.compile(r"\b(\d{6,})\b")
RE_DATES = (
    re.compile(r"(\d{1,2})[/-](\d{1,2})[/-](\d{4})"),
    re.compile(r"(\d{4})[/-](\d{1,2})[/-](\d{1,2})"),
)

# Spanish place names carry accents and often several words ("A Coruña",
# "San Sebastián"), which an [A-Z][a-z]+ pattern misses entirely.
# The first word may be a single letter ("A Coruña") and later words must be
# capitalised too, which stops the match from running through ordinary lowercase
# prose such as "Piso en Madrid".
PLACE = r"[A-ZÁÉÍÓÚÑ][^\W\d_]*(?:[ -][A-ZÁÉÍÓÚÑ][^\W\d_]*){0,3}"

RE_LOCATIONS = (
    # Stop at a digit or a comma: without that bound, joined text nodes make
    # "Localización: Madrid 15/03/2024" capture the date as part of the place.
    re.compile(rf"Localizaci[óo]n:\s*({PLACE})"),
    re.compile(rf"Ubicaci[óo]n:\s*({PLACE})"),
    re.compile(rf"Provincia:\s*({PLACE})"),
    re.compile(rf"({PLACE}),\s*España"),
)


def parse_amount(raw: str) -> float:
    """Convert a Spanish-formatted amount into a float."""
    return float(raw.replace(".", "").replace(",", "."))


def content_fingerprint(*parts: Any) -> str:
    """
    Deterministic id derived from a listing's own content.

    Used when a listing exposes no usable identifier. The previous fallback was
    built from the clock, so the same listing got a different id on every
    scrape: INSERT OR REPLACE never matched and each sync appended duplicate
    rows instead of updating them. A content hash keeps the id stable across
    runs while still separating genuinely different listings.
    """
    joined = "|".join("" if part is None else str(part) for part in parts)
    digest = hashlib.sha256(joined.encode("utf-8")).hexdigest()
    return f"SSSS-{digest[:16]}"

ASSET_KEYWORDS = (
    "subasta",
    "embargo",
    "bien",
    "lote",
    "precio",
    "puja",
    "inmueble",
    "vehículo",
)

# Checked in order, so the first matching family wins. The vocabulary comes from
# what auction listings actually say; the previous list classified 8 of 10 real
# items as "otros", which made the type filter useless on real data. Accented and
# unaccented spellings are both listed because listings use either.
TYPE_KEYWORDS = (
    (
        "inmueble",
        (
            "piso", "casa", "inmueble", "apartamento", "terreno", "propiedad",
            "vivienda", "nave", "local", "garaje", "solar", "finca", "parcela",
            "chalet", "chalé", "trastero", "oficina", "duplex", "dúplex",
            "atico", "ático", "rustica", "rústica", "urbana",
        ),
    ),
    (
        "vehiculo",
        (
            "coche", "carro", "vehículo", "vehiculo", "auto", "moto",
            "bicicleta", "camión", "camion", "furgoneta", "furgon", "furgón",
            "remolque", "tractor", "motocicleta", "turismo", "ciclomotor",
            "autocaravana", "caravana", "quad",
        ),
    ),
    (
        "mueble",
        (
            "mueble", "mobiliario", "sofa", "sofá", "silla", "mesa",
            "escritorio", "cama", "armario", "estanteria", "estantería",
            "butaca", "comoda", "cómoda", "aparador", "electrodomestico",
            "electrodoméstico", "lavadora", "nevera",
        ),
    ),
)

DESCRIPTION_SELECTORS = (
    "h2",
    "h3",
    "span.title",
    "span.description",
    "a.asset-link",
    "div.titulo",
    "p.descripcion",
)

ITEM_SELECTORS = (
    "div.asset-item",
    "div.subasta-item",
    "div.bien",
    "div.lote",
    "tr[data-id]",
    "article.asset",
    "div.product",
    "div.item-subasta",
    "li.asset",
)

# One comma-separated selector instead of nine separate select() calls over the
# whole document. Matching elements come back in document order and each appears
# once, even when it satisfies several of the selectors.
ITEM_SELECTOR = ", ".join(ITEM_SELECTORS)


def _default_parser() -> str:
    """
    Pick the fastest available HTML parser.

    lxml is measurably quicker than html.parser but is an optional binary
    dependency, so its absence must not break the import.
    """
    try:
        import lxml  # noqa: F401

        return "lxml"
    except ImportError:  # pragma: no cover - depends on the environment
        return "html.parser"


DEFAULT_PARSER = _default_parser()


class AssetParser:
    """Parse HTML from SSSS embargos portal"""

    def __init__(self):
        self.parser = DEFAULT_PARSER

    def parse_response(self, html_content: str) -> list[dict[str, Any]]:
        """
        Parse HTML response from SSSS portal and extract assets

        Args:
            html_content: Raw HTML content from portal

        Returns:
            List of normalized asset dictionaries
        """
        if not html_content or not isinstance(html_content, str):
            return []

        try:
            soup = BeautifulSoup(html_content, self.parser)
            assets = []

            # Try different selectors for asset items
            # SSSS portal structure varies, so we try multiple strategies
            asset_items = self._find_asset_items(soup)

            for item in asset_items:
                try:
                    asset = self._extract_asset_data(item, soup)
                    if asset and self._validate_asset(asset):
                        assets.append(asset)
                except Exception:
                    # Skip malformed items, continue with next
                    continue

            return assets

        except Exception:
            return []

    def _find_asset_items(self, soup: BeautifulSoup) -> list:
        """Find asset item elements in HTML"""
        # Strategy 1: Look for common asset container classes. Selecting them in
        # a single pass also removes the duplicates the previous per-selector
        # loop produced for an element matching more than one selector.
        candidates = soup.select(ITEM_SELECTOR)

        # If no specific selectors found, try generic divs with certain structures
        if not candidates:
            for div in soup.find_all("div", recursive=True):
                if self._looks_like_asset_item(div):
                    candidates.append(div)

        return candidates

    def _looks_like_asset_item(self, element) -> bool:
        """Check if element looks like an asset item"""
        text = element.get_text(" ", strip=True)

        # Check for price patterns or asset keywords
        has_price = bool(RE_PRICE_HINT.search(text))
        if has_price:
            return True

        lowered = text.lower()
        return any(keyword in lowered for keyword in ASSET_KEYWORDS)

    def _extract_asset_data(self, item, full_soup: BeautifulSoup) -> dict[str, Any] | None:
        """Extract asset data from item element"""
        asset = {}

        # get_text() walks the whole subtree, so it is read once here and reused
        # for every field instead of once per field. The separator matters: with
        # the default, adjacent text nodes are glued together, which produced
        # descriptions like "PisoDescripcion" and made the location swallow the
        # date that followed it.
        text = item.get_text(" ", strip=True)

        # Extract type
        asset["type"] = self._type_from(text)

        # Extract description
        asset["description"] = self._description_from(text, item)

        # Extract prices
        asset["price_initial"] = self._price_from(text)
        asset["price_min"] = self._min_price_from(text)

        # Extract dates
        asset["date_subasta"] = self._date_from(text)

        # Extract location
        asset["location"] = self._location_from(text)

        # Extract ID last: the fallback fingerprints the fields above, so it has
        # to run once they are known.
        asset["id"] = self._id_from(text, item) or content_fingerprint(
            asset["description"],
            asset["price_initial"],
            asset["date_subasta"],
            asset["location"],
            asset["type"],
        )

        return asset

    # ------------------------------------------------------------------
    # Field extraction from already-read text. The _extract_* wrappers below
    # keep the element-based API for callers that hold only an element.
    # ------------------------------------------------------------------

    def _id_from(self, text: str, element) -> str | None:
        """Extract unique ID from text, falling back to element attributes"""
        # Try data-id attribute
        if element.has_attr("data-id"):
            return element.get("data-id")

        # Try id attribute
        if element.has_attr("id"):
            return element.get("id")

        # Try to extract from text
        match = RE_ID_CODE.search(text)
        if match:
            return match.group(0)

        match = RE_ID_DIGITS.search(text)
        if match:
            return f"SSSS-{match.group(1)}"

        return None

    def _type_from(self, text: str) -> str:
        """Extract asset type (inmueble, vehiculo, mueble, otros)"""
        lowered = text.lower()

        for asset_type, keywords in TYPE_KEYWORDS:
            if any(keyword in lowered for keyword in keywords):
                return asset_type

        # Default
        return "otros"

    def _description_from(self, text: str, element) -> str:
        """Extract asset description"""
        descriptions = []

        # Try common description selectors
        for selector in DESCRIPTION_SELECTORS:
            elem = element.select_one(selector)
            if elem:
                selector_text = elem.get_text(" ", strip=True)
                if selector_text and len(selector_text) > 5:
                    descriptions.append(selector_text)

        # If no specific selector found, get all text
        if not descriptions:
            stripped = text.strip()
            # Clean up text
            lines = [line.strip() for line in stripped.split("\n") if line.strip()]
            if lines:
                descriptions.append(" ".join(lines[:3]))

        return " ".join(descriptions)[:500] if descriptions else "Asset without description"

    def _price_from(self, text: str) -> float:
        """
        Extract the initial price from text.

        Returns 0.0 when the text carries no euro amount.
        """
        match = RE_AMOUNT_EUR.search(text)
        if not match:
            return 0.0

        # Exactly one of the two alternatives captures.
        return parse_amount(match.group(1) or match.group(2))

    def _min_price_from(self, text: str) -> float | None:
        """
        Extract the minimum bid from text.

        Returns None when the listing states no minimum bid. It deliberately
        does not fall back to the generic price patterns: doing so made
        price_min a copy of price_initial, asserting a figure the portal never
        published.
        """
        match = RE_PUJA.search(text)
        if not match:
            return None

        return parse_amount(match.group(1))

    def _date_from(self, text: str) -> str:
        """Extract subasta date from text"""
        # Look for date patterns: DD/MM/YYYY or YYYY-MM-DD
        for pattern in RE_DATES:
            match = pattern.search(text)
            if match:
                groups = match.groups()
                # Normalize to YYYY-MM-DD
                if len(groups[0]) == 4:
                    # Already YYYY-MM-DD format
                    return f"{groups[0]}-{groups[1]:>02}-{groups[2]:>02}"
                # DD/MM/YYYY format
                day, month, year = groups
                return f"{year}-{month:>02}-{day:>02}"

        # Default to today
        return utc_now().strftime("%Y-%m-%d")

    def _location_from(self, text: str) -> str | None:
        """Extract location from text"""
        # Look for common location patterns
        for pattern in RE_LOCATIONS:
            match = pattern.search(text)
            if match:
                return match.group(1).strip()

        return None

    # ------------------------------------------------------------------
    # Element-based wrappers
    # ------------------------------------------------------------------

    def _extract_id(self, element) -> str | None:
        """Extract unique ID from asset element"""
        return self._id_from(element.get_text(" ", strip=True), element)

    def _extract_type(self, element) -> str:
        """Extract asset type (inmueble, vehiculo, mueble, otros)"""
        return self._type_from(element.get_text(" ", strip=True))

    def _extract_description(self, element) -> str:
        """Extract asset description"""
        return self._description_from(element.get_text(" ", strip=True), element)

    def _extract_price(self, element, price_type: str = "inicial"):
        """Extract price from asset element"""
        text = element.get_text(" ", strip=True)
        if price_type.lower() == "min":
            return self._min_price_from(text)
        return self._price_from(text)

    def _extract_date(self, element) -> str:
        """Extract subasta date from element"""
        return self._date_from(element.get_text(" ", strip=True))

    def _extract_location(self, element) -> str | None:
        """Extract location from element"""
        return self._location_from(element.get_text(" ", strip=True))

    def _validate_asset(self, asset: dict[str, Any]) -> bool:
        """Validate that asset has required fields"""
        required = ["id", "description", "date_subasta"]

        return all(
            field in asset and asset[field] for field in required
        )

    def normalize_asset(self, raw_data: dict[str, Any]) -> dict[str, Any]:
        """Normalize raw asset data"""
        description = str(raw_data.get("description", "")).strip()
        # Cap description at 500 characters
        if len(description) > 500:
            description = description[:500]

        return {
            "id": str(raw_data.get("id", "")).strip(),
            "type": str(raw_data.get("type", "otros")).lower(),
            "description": description,
            "price_initial": float(raw_data.get("price_initial", 0.0)),
            "price_min": float(raw_data.get("price_min", 0.0)) or None,
            "date_subasta": str(raw_data.get("date_subasta", "")),
            "location": (
                str(raw_data.get("location", "")).strip()
                if raw_data.get("location")
                else None
            ),
        }


def create_parser() -> AssetParser:
    """Factory function to create parser instance"""
    return AssetParser()
