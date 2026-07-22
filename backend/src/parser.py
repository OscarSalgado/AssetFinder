from typing import List, Dict, Optional, Any
from datetime import datetime
import re
from bs4 import BeautifulSoup


class AssetParser:
    """Parse HTML from SSSS embargos portal"""

    def __init__(self):
        self.parser = "html.parser"

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
        candidates = []

        # Strategy 1: Look for common asset container classes
        selectors = [
            "div.asset-item",
            "div.subasta-item",
            "div.bien",
            "div.lote",
            "tr[data-id]",
            "article.asset",
            "div.product",
            "div.item-subasta",
            "li.asset",
        ]

        for selector in selectors:
            items = soup.select(selector)
            if items:
                candidates.extend(items)

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
        has_price = bool(re.search(r"\d{2,}\s*€|€\s*\d{2,}", text))
        has_asset_keywords = any(
            keyword in text.lower()
            for keyword in [
                "subasta",
                "embargo",
                "bien",
                "lote",
                "precio",
                "puja",
                "inmueble",
                "vehículo",
            ]
        )

        return has_price or has_asset_keywords

    def _extract_asset_data(self, item, full_soup: BeautifulSoup) -> Optional[Dict[str, Any]]:
        """Extract asset data from item element"""
        asset = {}

        # Extract ID
        asset["id"] = self._extract_id(item) or f"SSSS-{datetime.utcnow().timestamp()}"

        # Extract type
        asset["type"] = self._extract_type(item)

        # Extract description
        asset["description"] = self._extract_description(item)

        # Extract prices
        asset["price_initial"] = self._extract_price(item, "inicial")
        asset["price_min"] = self._extract_price(item, "min")

        # Extract dates
        asset["date_subasta"] = self._extract_date(item)

        # Extract location
        asset["location"] = self._extract_location(item)

        return asset

    def _extract_id(self, element) -> Optional[str]:
        """Extract unique ID from asset element"""
        # Try data-id attribute
        if element.has_attr("data-id"):
            return element.get("data-id")

        # Try id attribute
        if element.has_attr("id"):
            return element.get("id")

        # Try to extract from text
        text = element.get_text()
        match = re.search(r"[A-Z]+-\d{4}-\d{3,}", text)
        if match:
            return match.group(0)

        match = re.search(r"\b(\d{6,})\b", text)
        if match:
            return f"SSSS-{match.group(1)}"

        return None

    def _extract_type(self, element) -> str:
        """Extract asset type (inmueble, vehiculo, mueble, otros)"""
        text = element.get_text().lower()

        # Check for specific keywords
        if any(keyword in text for keyword in ["piso", "casa", "inmueble", "apartamento", "terreno", "propiedad"]):
            return "inmueble"

        if any(keyword in text for keyword in ["coche", "carro", "vehículo", "auto", "vehiculo", "moto", "bicicleta"]):
            return "vehiculo"

        if any(keyword in text for keyword in ["mueble", "sofa", "silla", "mesa", "escritorio", "cama"]):
            return "mueble"

        # Default
        return "otros"

    def _extract_description(self, element) -> str:
        """Extract asset description"""
        descriptions = []

        # Try common description selectors
        selectors = [
            "h2",
            "h3",
            "span.title",
            "span.description",
            "a.asset-link",
            "div.titulo",
            "p.descripcion",
        ]

        for selector in selectors:
            elem = element.select_one(selector)
            if elem:
                text = elem.get_text().strip()
                if text and len(text) > 5:
                    descriptions.append(text)

        # If no specific selector found, get all text
        if not descriptions:
            text = element.get_text().strip()
            # Clean up text
            lines = [line.strip() for line in text.split("\n") if line.strip()]
            if lines:
                descriptions.append(" ".join(lines[:3]))

        return " ".join(descriptions)[:500] if descriptions else "Asset without description"

    def _extract_price(self, element, price_type: str = "inicial") -> float:
        """Extract price from asset element"""
        text = element.get_text()

        # Patterns to match prices
        patterns = [
            r"(\d+)[.,](\d{2})\s*€",
            r"€\s*(\d+)[.,](\d{2})",
            r"\b(\d{3,})\s*€",
        ]

        # Prioritize based on price_type
        if price_type.lower() == "min":
            # Look for minimum/puja
            min_section = re.search(r"puja.*?(\d+)[.,](\d{2})", text, re.IGNORECASE)
            if min_section:
                return float(min_section.group(1).replace(",", "."))

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                # Handle both comma and dot as decimal separator
                groups = match.groups()
                if len(groups) >= 2:
                    return float(f"{groups[0]}.{groups[1]}")
                else:
                    return float(groups[0].replace(".", ""))

        return 0.0

    def _extract_date(self, element) -> str:
        """Extract subasta date from element"""
        text = element.get_text()

        # Look for date patterns: DD/MM/YYYY or YYYY-MM-DD
        patterns = [
            r"(\d{1,2})[/-](\d{1,2})[/-](\d{4})",
            r"(\d{4})[/-](\d{1,2})[/-](\d{1,2})",
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
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
        return datetime.utcnow().strftime("%Y-%m-%d")

    def _extract_location(self, element) -> Optional[str]:
        """Extract location from element"""
        text = element.get_text()

        # Look for common location patterns
        patterns = [
            r"Localización:\s*([^,\n]+)",
            r"Ubicación:\s*([^,\n]+)",
            r"Provincia:\s*([^,\n]+)",
            r"([A-Z][a-z]+),\s*España",
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1).strip()

        return None

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
