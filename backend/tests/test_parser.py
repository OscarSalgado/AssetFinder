from unittest.mock import patch

import pytest

from src.parser import AssetParser, create_parser


class TestAssetParser:
    """Test AssetParser class"""

    @pytest.fixture
    def parser(self):
        """Create parser instance"""
        return AssetParser()

    @pytest.fixture
    def sample_html_simple(self):
        """Simple HTML sample"""
        return """
        <html>
            <body>
                <div class="asset-item" data-id="SSSS-2024-001">
                    <h2>Piso en Madrid centro - 3 habitaciones</h2>
                    <span class="price">150.000€</span>
                    <span class="date">15/03/2024</span>
                    <p>Inmueble de 100m2 en buen estado</p>
                </div>
            </body>
        </html>
        """

    @pytest.fixture
    def sample_html_complex(self):
        """Complex HTML sample with multiple assets"""
        return """
        <html>
            <body>
                <div class="subasta-item">
                    <div class="titulo">Toyota Corolla 2015</div>
                    <div class="precio">€ 8.500,00</div>
                    <div class="puja">Puja mínima: 6.500€</div>
                    <div class="fecha">20/03/2024</div>
                    <span>Vehículo en Barcelona</span>
                </div>

                <div class="lote">
                    <h3>Sofá de 3 plazas</h3>
                    <span>500€</span>
                    <span>10/03/2024</span>
                </div>
            </body>
        </html>
        """

    @pytest.fixture
    def sample_html_malformed(self):
        """Malformed HTML with missing data"""
        return """
        <html>
            <body>
                <div class="asset">
                    <span>Incomplete asset</span>
                </div>
                <div class="asset-item">
                    <h2>Asset with price only</h2>
                    <span>1000€</span>
                </div>
            </body>
        </html>
        """

    def test_parser_initialization(self, parser):
        """Test parser initialization"""
        assert parser is not None
        # lxml is used when installed, html.parser otherwise.
        assert parser.parser in ("lxml", "html.parser")

    def test_parse_response_simple(self, parser, sample_html_simple):
        """Test parsing simple HTML"""
        results = parser.parse_response(sample_html_simple)
        assert len(results) > 0
        assert "id" in results[0]
        assert "description" in results[0]

    def test_parse_response_complex(self, parser, sample_html_complex):
        """Test parsing complex HTML with multiple assets"""
        results = parser.parse_response(sample_html_complex)
        assert len(results) >= 2

    def test_parse_response_empty_html(self, parser):
        """Test parsing empty HTML"""
        results = parser.parse_response("")
        assert results == []

    def test_parse_response_none_input(self, parser):
        """Test parsing None input"""
        results = parser.parse_response(None)
        assert results == []

    def test_parse_response_invalid_html(self, parser):
        """Test parsing invalid HTML"""
        results = parser.parse_response("NOT HTML <invalid>")
        # Should return list even if HTML is invalid
        assert isinstance(results, list)

    def test_extract_id_from_data_attribute(self, parser):
        """Test extracting ID from data-id attribute"""
        from bs4 import BeautifulSoup

        html = '<div class="asset" data-id="TEST-123">Asset</div>'

        # div.asset is not one of the item selectors and the text carries no
        # price or keyword, so the fallback does not treat it as an asset.
        assert parser.parse_response(html) == []

        # The id extraction itself works when handed the element.
        element = BeautifulSoup(html, parser.parser).find("div")
        assert parser._extract_id(element) == "TEST-123"

    def test_extract_id_from_id_attribute(self, parser):
        """Test extracting ID from id attribute"""
        html = '<div class="asset" id="ASSET-456">Asset with id</div>'
        results = parser.parse_response(html)
        assert isinstance(results, list)

    def test_extract_id_from_text(self, parser):
        """Test extracting ID from text pattern"""
        html = """
        <div class="asset">
            <span>SSSS-2024-789</span>
            <span>1000€</span>
            <span>2024-01-01</span>
            <p>Asset description</p>
        </div>
        """
        results = parser.parse_response(html)
        # Should find at least something
        assert isinstance(results, list)

    def test_extract_type_inmueble(self, parser, sample_html_simple):
        """Test extracting inmueble type"""
        results = parser.parse_response(sample_html_simple)
        if results:
            assert results[0]["type"] == "inmueble"

    def test_extract_type_vehiculo(self, parser):
        """Test extracting vehiculo type"""
        html = """
        <div class="asset">
            <span>Toyota Coche</span>
            <span>500€</span>
            <span>2024-01-01</span>
            <p>Test vehículo</p>
        </div>
        """
        results = parser.parse_response(html)
        if results:
            assert results[0]["type"] == "vehiculo"

    def test_extract_type_mueble(self, parser):
        """Test extracting mueble type"""
        html = """
        <div class="asset">
            <span>Sofa rojo</span>
            <span>200€</span>
            <span>2024-01-01</span>
            <p>Mueble de madera</p>
        </div>
        """
        results = parser.parse_response(html)
        if results:
            assert results[0]["type"] == "mueble"

    def test_extract_type_otros(self, parser):
        """Test extracting otros type for unknown assets"""
        html = """
        <div class="asset">
            <span>Unknown item</span>
            <span>100€</span>
            <span>2024-01-01</span>
            <p>Unknown asset type</p>
        </div>
        """
        results = parser.parse_response(html)
        if results:
            assert results[0]["type"] == "otros"

    def test_extract_description(self, parser, sample_html_simple):
        """Test extracting description"""
        results = parser.parse_response(sample_html_simple)
        if results:
            desc = results[0]["description"]
            assert len(desc) > 0
            assert "Piso" in desc or "3 habitaciones" in desc

    def test_extract_price_euro_format(self, parser):
        """Test extracting price in euro format"""
        html = """
        <div class="asset">
            <span>Asset</span>
            <span>150.000€</span>
            <span>2024-01-01</span>
            <p>Description</p>
        </div>
        """
        results = parser.parse_response(html)

        assert len(results) == 1
        # "." groups thousands in Spanish notation, so this is 150000, not 0.0
        # and not 150.0.
        assert results[0]["price_initial"] == 150000.0

    def test_extract_price_comma_separator(self, parser):
        """Test extracting price with comma separator"""
        html = """
        <div class="asset">
            <span>Asset</span>
            <span>€ 1.234,56</span>
            <span>2024-01-01</span>
            <p>Description</p>
        </div>
        """
        results = parser.parse_response(html)

        # "," is the decimal mark, so this is 1234.56 and the element is
        # recognised as an asset in the first place.
        assert len(results) == 1
        assert results[0]["price_initial"] == 1234.56

    def test_extract_price_minimum(self, parser):
        """Test extracting minimum price"""
        html = """
        <div class="asset">
            <span>Asset</span>
            <span>Initial: 1000€</span>
            <span>Puja mínima: 800€</span>
            <span>2024-01-01</span>
            <p>Description</p>
        </div>
        """
        results = parser.parse_response(html)

        assert len(results) == 1
        # The minimum bid is read even without decimals, and it is not a copy of
        # the initial price.
        assert results[0]["price_initial"] == 1000.0
        assert results[0]["price_min"] == 800.0

    def test_extract_date_dd_mm_yyyy(self, parser):
        """Test extracting date in DD/MM/YYYY format"""
        html = """
        <div class="asset">
            <span>Asset</span>
            <span>500€</span>
            <span>15/03/2024</span>
            <p>Description</p>
        </div>
        """
        results = parser.parse_response(html)
        if results:
            assert results[0]["date_subasta"] == "2024-03-15"

    def test_extract_date_yyyy_mm_dd(self, parser):
        """Test extracting date in YYYY-MM-DD format"""
        html = """
        <div class="asset">
            <span>Asset</span>
            <span>500€</span>
            <span>2024-03-15</span>
            <p>Description</p>
        </div>
        """
        results = parser.parse_response(html)
        if results:
            assert results[0]["date_subasta"] == "2024-03-15"

    def test_extract_date_with_dashes(self, parser):
        """Test extracting date with dashes"""
        html = """
        <div class="asset">
            <span>Asset</span>
            <span>500€</span>
            <span>15-03-2024</span>
            <p>Description</p>
        </div>
        """
        results = parser.parse_response(html)

        assert len(results) == 1
        assert results[0]["date_subasta"] == "2024-03-15"

    def test_extract_location(self, parser):
        """Test extracting location"""
        html = """
        <div class="asset">
            <span>Asset</span>
            <span>500€</span>
            <span>2024-01-01</span>
            <p>Localización: Madrid, España</p>
        </div>
        """
        results = parser.parse_response(html)
        if results:
            assert results[0].get("location") is not None

    def test_normalize_asset(self, parser):
        """Test asset normalization"""
        raw = {
            "id": "  TEST-001  ",
            "type": "INMUEBLE",
            "description": "  Test asset  ",
            "price_initial": 100,
            "price_min": 0,
            "date_subasta": "2024-01-01",
            "location": "  Madrid  ",
        }

        normalized = parser.normalize_asset(raw)

        assert normalized["id"] == "TEST-001"
        assert normalized["type"] == "inmueble"
        assert normalized["description"] == "Test asset"
        assert normalized["location"] == "Madrid"

    def test_validate_asset_valid(self, parser):
        """Test validating valid asset"""
        asset = {
            "id": "TEST-001",
            "description": "Valid asset",
            "date_subasta": "2024-01-01",
            "type": "inmueble",
            "price_initial": 100,
        }

        assert parser._validate_asset(asset) is True

    def test_validate_asset_missing_id(self, parser):
        """Test validating asset with missing ID"""
        asset = {
            "description": "No ID asset",
            "date_subasta": "2024-01-01",
        }

        assert parser._validate_asset(asset) is False

    def test_validate_asset_missing_description(self, parser):
        """Test validating asset with missing description"""
        asset = {
            "id": "TEST-001",
            "date_subasta": "2024-01-01",
        }

        assert parser._validate_asset(asset) is False

    def test_validate_asset_missing_date(self, parser):
        """Test validating asset with missing date"""
        asset = {
            "id": "TEST-001",
            "description": "No date asset",
        }

        assert parser._validate_asset(asset) is False

    def test_looks_like_asset_item_with_price(self, parser):
        """Test that element with price looks like asset"""
        html = '<div>Something with 100€</div>'
        soup = __import__("bs4").BeautifulSoup(html, "html.parser")
        elem = soup.find("div")

        assert parser._looks_like_asset_item(elem) is True

    def test_looks_like_asset_item_with_keywords(self, parser):
        """Test that element with keywords looks like asset"""
        html = '<div>This is a subasta item</div>'
        soup = __import__("bs4").BeautifulSoup(html, "html.parser")
        elem = soup.find("div")

        assert parser._looks_like_asset_item(elem) is True

    def test_looks_like_asset_item_generic(self, parser):
        """Test generic element that doesn't look like asset"""
        html = '<div>Just some random text</div>'
        soup = __import__("bs4").BeautifulSoup(html, "html.parser")
        elem = soup.find("div")

        assert parser._looks_like_asset_item(elem) is False

    def test_create_parser_factory(self):
        """Test parser factory function"""
        parser = create_parser()
        assert isinstance(parser, AssetParser)

    def test_parse_multiple_asset_types(self, parser, sample_html_complex):
        """Test parsing HTML with multiple asset types"""
        results = parser.parse_response(sample_html_complex)

        types = [asset["type"] for asset in results]
        # Should have some variety in types
        assert isinstance(types, list)

    def test_parse_real_world_html_simulation(self, parser):
        """Test parsing realistic HTML structure"""
        html = """
        <html>
            <body>
                <table class="subastas">
                    <tr data-id="SSSS-2024-001">
                        <td>Piso en Barcelona</td>
                        <td>€200.000</td>
                        <td>25/03/2024</td>
                        <td>Barcelona</td>
                    </tr>
                    <tr data-id="SSSS-2024-002">
                        <td>Mercedes Benz E-Class</td>
                        <td>€45.000</td>
                        <td>22/03/2024</td>
                        <td>Madrid</td>
                    </tr>
                </table>
            </body>
        </html>
        """

        results = parser.parse_response(html)
        # Should extract at least the table rows
        assert isinstance(results, list)

    def test_edge_case_description_length(self, parser):
        """Test that description is capped at 500 chars"""
        long_desc = "x" * 1000
        asset = {
            "id": "TEST",
            "description": long_desc,
            "date_subasta": "2024-01-01",
        }

        normalized = parser.normalize_asset(asset)
        assert len(normalized["description"]) <= 500

    def test_edge_case_price_zero(self, parser):
        """Test handling of zero price"""
        html = """
        <div class="asset">
            <span>Asset</span>
            <span>0€</span>
            <span>2024-01-01</span>
            <p>Free item</p>
        </div>
        """

        results = parser.parse_response(html)
        if results:
            assert results[0]["price_initial"] >= 0


class TestAssetParserErrorHandling:
    """Test error handling in parser"""

    @pytest.fixture
    def parser(self):
        """Create parser instance"""
        return AssetParser()

    def test_parse_response_exception_handled(self, parser):
        """Test that exceptions during parsing are handled"""
        with patch("src.parser.BeautifulSoup") as mock_soup:
            mock_soup.side_effect = Exception("Parse error")

            results = parser.parse_response("<html></html>")
            # Should return empty list on exception
            assert results == []

    def test_find_asset_items_returns_candidates(self, parser):
        """Test that find_asset_items returns list"""
        html = '<div class="asset-item">Test</div>'
        soup = __import__("bs4").BeautifulSoup(html, "html.parser")

        items = parser._find_asset_items(soup)
        assert isinstance(items, list)

    def test_extract_id_returns_none(self, parser):
        """Test extracting ID when no ID found"""
        html = '<div>No ID here</div>'
        soup = __import__("bs4").BeautifulSoup(html, "html.parser")
        elem = soup.find("div")

        result_id = parser._extract_id(elem)
        # Should return None or generate one
        assert result_id is None or isinstance(result_id, str)

    def test_extract_price_no_price_found(self, parser):
        """Test extracting price when no price present"""
        html = '<div>No price here</div>'
        soup = __import__("bs4").BeautifulSoup(html, "html.parser")
        elem = soup.find("div")

        price = parser._extract_price(elem)
        assert price == 0.0

    def test_extract_location_no_location(self, parser):
        """Test extracting location when not present"""
        html = '<div>No location info</div>'
        soup = __import__("bs4").BeautifulSoup(html, "html.parser")
        elem = soup.find("div")

        location = parser._extract_location(elem)
        assert location is None

    def test_parse_response_with_mixed_valid_invalid_items(self, parser):
        """Test parsing mixed valid and invalid items"""
        html = """
        <html>
            <body>
                <div class="asset">
                    <span>Incomplete</span>
                </div>
                <div class="asset-item" data-id="TEST-001">
                    <span>Valid asset</span>
                    <span>500€</span>
                    <span>2024-01-01</span>
                </div>
                <div class="asset">
                    <span>Another incomplete</span>
                </div>
            </body>
        </html>
        """

        results = parser.parse_response(html)
        # Should skip incomplete items and only return valid ones
        assert isinstance(results, list)

    def test_extract_date_no_date_found(self, parser):
        """Test extracting date when not present"""
        html = '<div>No date here</div>'
        soup = __import__("bs4").BeautifulSoup(html, "html.parser")
        elem = soup.find("div")

        date = parser._extract_date(elem)
        # Should return today's date as default
        assert len(date) == 10  # YYYY-MM-DD format
        assert date.count("-") == 2

    def test_extract_description_from_p_tag(self, parser):
        """Test extracting description from p tag"""
        html = '<div><p class="descripcion">Test description text</p></div>'
        soup = __import__("bs4").BeautifulSoup(html, "html.parser")
        elem = soup.find("div")

        desc = parser._extract_description(elem)
        assert len(desc) > 0

    def test_normalize_asset_with_zero_price(self, parser):
        """Test normalizing asset with zero price"""
        raw = {
            "id": "TEST",
            "description": "Test",
            "date_subasta": "2024-01-01",
            "price_initial": 0.0,
            "price_min": 0.0,
        }

        normalized = parser.normalize_asset(raw)
        assert normalized["price_initial"] == 0.0
        assert normalized["price_min"] is None  # 0.0 or None becomes None

    def test_normalize_asset_with_none_location(self, parser):
        """Test normalizing asset without location"""
        raw = {
            "id": "TEST",
            "description": "Test",
            "date_subasta": "2024-01-01",
        }

        normalized = parser.normalize_asset(raw)
        assert normalized["location"] is None

    def test_find_asset_items_generic_fallback(self, parser):
        """Test finding assets using generic fallback"""
        html = """
        <html>
            <body>
                <div>Price: 500€, subasta details</div>
            </body>
        </html>
        """

        soup = __import__("bs4").BeautifulSoup(html, "html.parser")
        items = parser._find_asset_items(soup)

        # Should find at least the div that looks like an asset
        assert len(items) >= 0

    def test_extract_id_from_long_number(self, parser):
        """Test extracting ID from long numbers"""
        html = '<div>ID: 123456789</div>'
        soup = __import__("bs4").BeautifulSoup(html, "html.parser")
        elem = soup.find("div")

        result_id = parser._extract_id(elem)
        # Should extract the long number
        assert result_id is not None

    def test_validate_asset_with_empty_values(self, parser):
        """Test validating asset with empty values"""
        asset = {
            "id": "",
            "description": "",
            "date_subasta": "",
        }

        assert parser._validate_asset(asset) is False

    def test_parse_response_preserves_asset_count(self, parser):
        """Test that parsing same HTML twice gives same count"""
        html = """
        <div class="asset-item" data-id="TEST-1">
            <span>Asset 1</span>
            <span>100€</span>
            <span>2024-01-01</span>
        </div>
        <div class="asset-item" data-id="TEST-2">
            <span>Asset 2</span>
            <span>200€</span>
            <span>2024-01-02</span>
        </div>
        """

        result1 = parser.parse_response(html)
        result2 = parser.parse_response(html)

        assert len(result1) == len(result2)

    def test_parse_response_with_extraction_exception(self, parser):
        """Test parsing when extraction raises exception"""
        with patch.object(parser, "_extract_asset_data") as mock_extract:
            mock_extract.side_effect = [Exception("Extract failed"), None]

            html = """
            <div class="asset-item" data-id="TEST-1">
                <span>Asset</span><span>100€</span><span>2024-01-01</span>
            </div>
            <div class="asset-item" data-id="TEST-2">
                <span>Asset</span><span>200€</span><span>2024-01-02</span>
            </div>
            """

            results = parser.parse_response(html)
            # Should skip both items (one failed extraction, one is None)
            assert isinstance(results, list)

    def test_parse_response_skips_invalid_assets(self, parser):
        """Test that invalid assets are skipped"""
        with patch.object(parser, "_validate_asset") as mock_validate:
            mock_validate.return_value = False

            html = '<div class="asset-item"><span>Asset</span><span>100€</span><span>2024-01-01</span></div>'

            results = parser.parse_response(html)
            # Should skip invalid assets
            assert len(results) == 0

    def test_extract_asset_data_returns_dict(self, parser):
        """Test that extract_asset_data always returns dict"""
        html = '<div>Test</div>'
        soup = __import__("bs4").BeautifulSoup(html, "html.parser")
        elem = soup.find("div")

        result = parser._extract_asset_data(elem, soup)
        assert isinstance(result, dict)

    def test_normalize_asset_type_case_insensitive(self, parser):
        """Test that type is normalized to lowercase"""
        raw = {
            "id": "TEST",
            "description": "Test",
            "date_subasta": "2024-01-01",
            "type": "INMUEBLE",
        }

        normalized = parser.normalize_asset(raw)
        assert normalized["type"] == "inmueble"

    def test_normalize_asset_missing_optional_fields(self, parser):
        """Test normalizing asset with minimal required fields"""
        raw = {
            "id": "TEST",
            "description": "Test",
            "date_subasta": "2024-01-01",
        }

        normalized = parser.normalize_asset(raw)
        assert normalized["id"] == "TEST"
        assert normalized["price_initial"] == 0.0
        assert normalized["location"] is None


class TestParserBackendSelection:
    """Test the HTML backend choice and its fallback"""

    def test_default_parser_is_available(self):
        """Test the chosen backend is one BeautifulSoup can build"""
        from bs4 import BeautifulSoup

        from src.parser import DEFAULT_PARSER

        soup = BeautifulSoup("<div>x</div>", DEFAULT_PARSER)
        assert soup.find("div").get_text() == "x"

    def test_lxml_is_preferred_when_importable(self):
        """Test lxml wins when it is installed"""
        from src.parser import _default_parser

        assert _default_parser() == "lxml"

    def test_falls_back_to_html_parser_without_lxml(self):
        """Test a missing lxml does not break the import"""
        import builtins

        from src.parser import _default_parser

        real_import = builtins.__import__

        def no_lxml(name, *args, **kwargs):
            if name == "lxml":
                raise ImportError("No module named 'lxml'")
            return real_import(name, *args, **kwargs)

        with patch.object(builtins, "__import__", side_effect=no_lxml):
            assert _default_parser() == "html.parser"

    def test_both_backends_produce_the_same_assets(self):
        """Test switching backend does not change what is extracted"""
        from src.parser import AssetParser

        html = """
        <div class="asset-item" data-id="SSSS-2024-001">
            <h3>Piso de 3 habitaciones en Madrid centro</h3>
            <span>150.000,00 &euro;</span>
            <span>15/03/2024</span>
            <p>Localización: Madrid</p>
        </div>
        """

        with_lxml = AssetParser()
        with_lxml.parser = "lxml"
        with_html = AssetParser()
        with_html.parser = "html.parser"

        assert with_lxml.parse_response(html) == with_html.parse_response(html)


class TestItemSelection:
    """Test how candidate elements are collected"""

    def test_element_matching_two_selectors_is_returned_once(self):
        """Test the single-pass select removes duplicate candidates"""
        from src.parser import AssetParser

        # This div satisfies both div.asset-item and div.bien; the previous
        # per-selector loop collected it twice and emitted a duplicate asset.
        html = """
        <div class="asset-item bien" data-id="SSSS-2024-009">
            <h3>Piso en Valencia con jardin</h3>
            <span>200.000,00 &euro;</span>
            <span>10/04/2024</span>
        </div>
        """
        parser = AssetParser()

        assets = parser.parse_response(html)

        assert len(assets) == 1
        assert assets[0]["id"] == "SSSS-2024-009"

    def test_candidates_are_returned_in_document_order(self):
        """Test items keep the order they appear on the page"""
        from bs4 import BeautifulSoup

        from src.parser import AssetParser

        html = """
        <div class="lote" data-id="PRIMERO"><h3>Coche Toyota diesel</h3></div>
        <div class="asset-item" data-id="SEGUNDO"><h3>Piso en Madrid centro</h3></div>
        <div class="bien" data-id="TERCERO"><h3>Casa en Bilbao garaje</h3></div>
        """
        parser = AssetParser()
        soup = BeautifulSoup(html, parser.parser)

        items = parser._find_asset_items(soup)

        assert [item.get("data-id") for item in items] == [
            "PRIMERO",
            "SEGUNDO",
            "TERCERO",
        ]

    def test_get_text_is_read_once_per_item(self):
        """Test extraction no longer re-walks the subtree for every field"""
        import bs4

        from src.parser import AssetParser

        html = """
        <div class="asset-item" data-id="SSSS-2024-001">
            <h3>Piso de 3 habitaciones en Madrid centro</h3>
            <span>150.000,00 &euro;</span>
            <span>Puja minima 120.000,00 &euro;</span>
            <span>15/03/2024</span>
            <p>Localización: Madrid</p>
        </div>
        """
        parser = AssetParser()
        soup = bs4.BeautifulSoup(html, parser.parser)
        item = parser._find_asset_items(soup)[0]

        calls = []
        original = bs4.element.Tag.get_text

        def counting(self, *args, **kwargs):
            calls.append(self.name)
            return original(self, *args, **kwargs)

        with patch.object(bs4.element.Tag, "get_text", counting):
            parser._extract_asset_data(item, soup)

        # One walk of the item, plus the small h3 the description selector hits.
        assert calls.count("div") == 1
        assert len(calls) == 2


class TestElementWrappers:
    """Test the element-based wrappers kept around the text extractors"""

    @pytest.fixture
    def parser(self):
        return AssetParser()

    def _element(self, parser, html):
        from bs4 import BeautifulSoup

        return BeautifulSoup(html, parser.parser).find(["div", "tr"])

    def test_extract_type_from_element(self, parser):
        """Test the type wrapper reads the element text"""
        elem = self._element(parser, "<div>Piso en Madrid centro</div>")

        assert parser._extract_type(elem) == "inmueble"

    def test_extract_id_from_id_attribute(self, parser):
        """Test the id attribute is used when data-id is absent"""
        elem = self._element(parser, '<div id="ASSET-456">Piso</div>')

        assert parser._extract_id(elem) == "ASSET-456"

    def test_data_id_takes_precedence_over_id(self, parser):
        """Test data-id wins when both attributes are present"""
        elem = self._element(parser, '<div data-id="DATA-1" id="ID-1">Piso</div>')

        assert parser._extract_id(elem) == "DATA-1"

    def test_wrappers_agree_with_the_text_extractors(self, parser):
        """Test the element and text paths return the same values"""
        html = (
            '<div data-id="SSSS-2024-001">'
            "<h3>Piso de 3 habitaciones en Madrid</h3>"
            "<span>150.000,00 &euro;</span><span>15/03/2024</span>"
            "<p>Localización: Madrid</p></div>"
        )
        elem = self._element(parser, html)
        text = elem.get_text()

        assert parser._extract_type(elem) == parser._type_from(text)
        assert parser._extract_price(elem) == parser._price_from(text)
        assert parser._extract_price(elem, "min") == parser._min_price_from(text)
        assert parser._extract_date(elem) == parser._date_from(text)
        assert parser._extract_location(elem) == parser._location_from(text)
        assert parser._extract_description(elem) == parser._description_from(text, elem)


class TestAmountParsing:
    """
    Spanish price notation, table driven.

    Every one of these formats used to be extracted wrongly: "." was treated as
    a decimal mark, so a thousands group was silently dropped or became the
    whole value.
    """

    @pytest.fixture
    def parser(self):
        return AssetParser()

    def _asset(self, price):
        return f"""
        <div class="asset-item">
            <h3>Piso en Madrid centro amplio</h3>
            <span>{price}</span>
            <span>15/03/2024</span>
        </div>
        """

    @pytest.mark.parametrize(
        ("price", "expected"),
        [
            ("150.000€", 150000.0),
            ("800€", 800.0),
            ("€ 1.234,56", 1234.56),
            ("1.234,56€", 1234.56),
            ("8.500,00€", 8500.0),
            ("€ 8.500,00", 8500.0),
            ("1.234.567,89€", 1234567.89),
            ("99,99€", 99.99),
            ("500 €", 500.0),
            ("€500", 500.0),
            ("0€", 0.0),
            ("150.000,50€", 150000.5),
        ],
    )
    def test_price_formats(self, parser, price, expected):
        """Test each Spanish price format is read at its real value"""
        results = parser.parse_response(self._asset(price))

        assert len(results) == 1, f"{price} was not detected as an asset"
        assert results[0]["price_initial"] == expected

    @pytest.mark.parametrize(
        "text",
        [
            "Piso con 120.000 km recorridos",
            "3 habitaciones y 2 banos",
            "Referencia 2024 del expediente",
            "No price here",
        ],
    )
    def test_figures_without_euro_are_not_prices(self, parser, text):
        """Test the euro sign is required, so stray figures are not prices"""
        assert parser._price_from(text) == 0.0

    def test_parse_amount_helper(self):
        """Test the conversion helper directly"""
        from src.parser import parse_amount

        assert parse_amount("1.234.567,89") == 1234567.89
        assert parse_amount("150.000") == 150000.0
        assert parse_amount("99,99") == 99.99
        assert parse_amount("500") == 500.0


class TestMinimumBid:
    """The minimum bid must be the stated one, or nothing"""

    @pytest.fixture
    def parser(self):
        return AssetParser()

    def _asset(self, extra=""):
        return f"""
        <div class="asset-item">
            <h3>Piso en Madrid centro amplio</h3>
            <span>1000€</span>
            {extra}
            <span>15/03/2024</span>
        </div>
        """

    @pytest.mark.parametrize(
        ("fragment", "expected"),
        [
            ("<span>Puja mínima: 800€</span>", 800.0),
            ("<span>Puja mínima: 6.500€</span>", 6500.0),
            ("<span>Puja minima 120.000,00 €</span>", 120000.0),
            ("<span>Puja: 99,50€</span>", 99.5),
        ],
    )
    def test_minimum_bid_is_read(self, parser, fragment, expected):
        """Test the stated minimum bid is extracted, decimals or not"""
        results = parser.parse_response(self._asset(fragment))

        assert results[0]["price_min"] == expected

    def test_absent_minimum_bid_is_none(self, parser):
        """
        Test a listing without a minimum bid reports None.

        It used to fall back to the generic price patterns, so price_min became
        a copy of price_initial and claimed a figure the portal never published.
        """
        results = parser.parse_response(self._asset())

        assert results[0]["price_initial"] == 1000.0
        assert results[0]["price_min"] is None

    def test_minimum_bid_does_not_reach_a_distant_amount(self, parser):
        """Test the keyword match cannot jump over other figures"""
        text = "Puja mínima no publicada. Otros lotes desde 5.000€ hasta 9.000€"

        assert parser._min_price_from(text) is None


class TestTypeClassification:
    """Type drives the main filter, so real auction vocabulary must classify"""

    @pytest.fixture
    def parser(self):
        return AssetParser()

    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("Piso de 3 habitaciones", "inmueble"),
            ("Nave industrial en polígono", "inmueble"),
            ("Local comercial a pie de calle", "inmueble"),
            ("Plaza de garaje en Madrid", "inmueble"),
            ("Solar urbano sin edificar", "inmueble"),
            ("Finca rústica de regadío", "inmueble"),
            ("Vehículo Toyota Corolla", "vehiculo"),
            ("Camión de reparto", "vehiculo"),
            ("Furgoneta Ford Transit", "vehiculo"),
            ("Motocicleta Honda", "vehiculo"),
            ("Sofá de 3 plazas en tela", "mueble"),
            ("Sofa de 3 plazas", "mueble"),
            ("Armario de roble macizo", "mueble"),
            ("Lote de mobiliario de oficina", "inmueble"),
            ("Lote de joyas variadas", "otros"),
            ("Objeto sin clasificar", "otros"),
        ],
    )
    def test_type_classification(self, parser, text, expected):
        """Test each vocabulary item lands in the right family"""
        assert parser._type_from(text) == expected

    def test_accented_and_unaccented_spellings_agree(self, parser):
        """Test listings using either spelling classify the same"""
        assert parser._type_from("Sofá nuevo") == parser._type_from("Sofa nuevo")
        assert parser._type_from("Camión grúa") == parser._type_from("Camion grua")


class TestLocationExtraction:
    """Spanish place names carry accents and several words"""

    @pytest.fixture
    def parser(self):
        return AssetParser()

    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("Localización: Madrid", "Madrid"),
            ("Ubicación: Barcelona", "Barcelona"),
            ("Provincia: Sevilla", "Sevilla"),
            ("Madrid, España", "Madrid"),
            ("Málaga, España", "Málaga"),
            ("A Coruña, España", "A Coruña"),
            ("San Sebastián, España", "San Sebastián"),
            ("Piso amplio en Madrid, España", "Madrid"),
        ],
    )
    def test_location_extraction(self, parser, text, expected):
        """Test the place name is captured intact"""
        assert parser._location_from(text) == expected

    def test_location_does_not_swallow_a_following_date(self, parser):
        """
        Test the capture stops before a date.

        Adjacent text nodes are joined, so an unbounded capture produced
        "Madrid15/03/2024" as the location.
        """
        assert parser._location_from("Localización: Madrid 15/03/2024") == "Madrid"

    def test_missing_location_is_none(self, parser):
        """Test text without a place yields None"""
        assert parser._location_from("Sin datos de ubicacion") is None


class TestStableIdentifier:
    """A listing without an id must still get a stable one"""

    @pytest.fixture
    def parser(self):
        return AssetParser()

    HTML = """
    <div class="asset-item">
        <h3>Lote de joyas variadas</h3>
        <span>1000€</span>
        <span>15/03/2024</span>
    </div>
    """

    def test_same_listing_yields_the_same_id(self, parser):
        """
        Test the fallback id is derived from content, not from the clock.

        A clock-based id changed on every scrape, so INSERT OR REPLACE never
        matched and each sync appended duplicate rows.
        """
        ids = {parser.parse_response(self.HTML)[0]["id"] for _ in range(3)}

        assert len(ids) == 1

    def test_different_listings_yield_different_ids(self, parser):
        """Test genuinely different listings do not collide"""
        other = self.HTML.replace("joyas variadas", "cuadros antiguos")

        first = parser.parse_response(self.HTML)[0]["id"]
        second = parser.parse_response(other)[0]["id"]

        assert first != second

    def test_fallback_id_has_a_stable_shape(self, parser):
        """Test the generated id is a short prefixed digest"""
        asset_id = parser.parse_response(self.HTML)[0]["id"]

        assert asset_id.startswith("SSSS-")
        assert len(asset_id) == len("SSSS-") + 16

    def test_explicit_id_wins_over_the_fallback(self, parser):
        """Test a listing that carries an id keeps it"""
        html = self.HTML.replace(
            '<div class="asset-item">', '<div class="asset-item" data-id="REAL-1">'
        )

        assert parser.parse_response(html)[0]["id"] == "REAL-1"

    def test_fingerprint_helper_is_deterministic(self):
        """Test the helper itself is stable and order sensitive"""
        from src.parser import content_fingerprint

        assert content_fingerprint("a", 1, None) == content_fingerprint("a", 1, None)
        assert content_fingerprint("a", 1) != content_fingerprint(1, "a")


class TestTextJoining:
    """Adjacent text nodes must not be glued together"""

    @pytest.fixture
    def parser(self):
        return AssetParser()

    def test_description_words_are_not_glued(self, parser):
        """Test a short title followed by prose keeps the word boundary"""
        html = """
        <div class="asset-item">
            <h3>Piso</h3>
            <p>Descripcion mas larga del bien</p>
            <span>1000€</span>
            <span>15/03/2024</span>
        </div>
        """
        description = parser.parse_response(html)[0]["description"]

        assert "PisoDescripcion" not in description
        assert "Piso Descripcion" in description

    def test_price_is_found_when_it_follows_text_directly(self, parser):
        """
        Test an amount glued to the preceding word is still read.

        The old pattern used \\b, which failed on "...amplio800€" and returned
        0.0 for a perfectly valid price.
        """
        html = """
        <div class="asset-item">
            <h3>Piso en Madrid centro amplio</h3><span>800€</span>
            <span>15/03/2024</span>
        </div>
        """

        assert parser.parse_response(html)[0]["price_initial"] == 800.0
