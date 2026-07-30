from typing import List, Dict, Optional, Any
import re
from bs4 import BeautifulSoup

from .timeutils import utc_now

# Patterns are compiled once at import instead of on every call.
RE_PRICE_HINT = re.compile(r"\d{2,}\s*€|€\s*\d{2,}")
RE_ID_CODE = re.compile(r"[A-Z]+-\d{4}-\d{3,}")
RE_ID_DIGITS = re.compile(r"\b(\d{6,})\b")
RE_PUJA = re.compile(r"puja.*?(\d+)[.,](\d{2})", re.IGNORECASE)
RE_PRICES = (
    re.compile(r"(\d+)[.,](\d{2})\s*€"),
    re.compile(r"€\s*(\d+)[.,](\d{2})"),
    re.compile(r"\b(\d{3,})\s*€"),
)
RE_DATES = (
    re.compile(r"(\d{1,2})[/-](\d{1,2})[/-](\d{4})"),
    re.compile(r"(\d{4})[/-](\d{1,2})[/-](\d{1,2})"),
)
RE_LOCATIONS = (
    re.compile(r"Localización:\s*([^,\n]+)"),
    re.compile(r"Ubicación:\s*([^,\n]+)"),
    re.compile(r"Provincia:\s*([^,\n]+)"),
    re.compile(r"([A-Z][a-z]+),\s*España"),
)

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

TYPE_KEYWORDS = (
    ("inmueble", ("piso", "casa", "inmueble", "apartamento", "terreno", "propiedad")),
    ("vehiculo", ("coche", "carro", "vehículo", "auto", "vehiculo", "moto", "bicicleta")),
    ("mueble", ("mueble", "sofa", "silla", "mesa", "escritorio", "cama")),
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

    def parse_response(self, html_content: str) -> List[Dict[str, Any]]:
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
        text = element.get_text()

        # Check for price patterns or asset keywords
        has_price = bool(RE_PRICE_HINT.search(text))
        if has_price:
            return True

        lowered = text.lower()
        return any(keyword in lowered for keyword in ASSET_KEYWORDS)

    def _extract_asset_data(self, item, full_soup: BeautifulSoup) -> Optional[Dict[str, Any]]:
        """Extract asset data from item element"""
        asset = {}

        # get_text() walks the whole subtree, so it is read once here and reused
        # for every field instead of once per field.
        text = item.get_text()

        # Extract ID
        asset["id"] = self._id_from(text, item) or f"SSSS-{utc_now().timestamp()}"

        # Extract type
        asset["type"] = self._type_from(text)

        # Extract description
        asset["description"] = self._description_from(text, item)

        # Extract prices
        asset["price_initial"] = self._price_from(text, "inicial")
        asset["price_min"] = self._price_from(text, "min")

        # Extract dates
        asset["date_subasta"] = self._date_from(text)

        # Extract location
        asset["location"] = self._location_from(text)

        return asset

    # ------------------------------------------------------------------
    # Field extraction from already-read text. The _extract_* wrappers below
    # keep the element-based API for callers that hold only an element.
    # ------------------------------------------------------------------

    def _id_from(self, text: str, element) -> Optional[str]:
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
                selector_text = elem.get_text().strip()
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

    def _price_from(self, text: str, price_type: str = "inicial") -> float:
        """Extract price from text"""
        # Prioritize based on price_type
        if price_type.lower() == "min":
            # Look for minimum/puja
            min_section = RE_PUJA.search(text)
            if min_section:
                return float(min_section.group(1).replace(",", "."))

        for pattern in RE_PRICES:
            match = pattern.search(text)
            if match:
                # Handle both comma and dot as decimal separator
                groups = match.groups()
                if len(groups) >= 2:
                    return float(f"{groups[0]}.{groups[1]}")
                else:
                    return float(groups[0].replace(".", ""))

        return 0.0

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
                else:
                    # DD/MM/YYYY format
                    day, month, year = groups
                    return f"{year}-{month:>02}-{day:>02}"

        # Default to today
        return utc_now().strftime("%Y-%m-%d")

    def _location_from(self, text: str) -> Optional[str]:
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

    def _extract_id(self, element) -> Optional[str]:
        """Extract unique ID from asset element"""
        return self._id_from(element.get_text(), element)

    def _extract_type(self, element) -> str:
        """Extract asset type (inmueble, vehiculo, mueble, otros)"""
        return self._type_from(element.get_text())

    def _extract_description(self, element) -> str:
        """Extract asset description"""
        return self._description_from(element.get_text(), element)

    def _extract_price(self, element, price_type: str = "inicial") -> float:
        """Extract price from asset element"""
        return self._price_from(element.get_text(), price_type)

    def _extract_date(self, element) -> str:
        """Extract subasta date from element"""
        return self._date_from(element.get_text())

    def _extract_location(self, element) -> Optional[str]:
        """Extract location from element"""
        return self._location_from(element.get_text())

    def _validate_asset(self, asset: Dict[str, Any]) -> bool:
        """Validate that asset has required fields"""
        required = ["id", "description", "date_subasta"]

        return all(
            field in asset and asset[field] for field in required
        )

    def normalize_asset(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
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
