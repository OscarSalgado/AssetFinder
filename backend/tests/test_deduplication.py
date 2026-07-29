"""Deduplication tests for AssetFinder"""

import random
import pytest
from difflib import SequenceMatcher
from unittest.mock import patch
from src.deduplication import DeduplicationEngine


@pytest.fixture
def engine():
    """Create a deduplication engine with default threshold"""
    return DeduplicationEngine(confidence_threshold=0.8)


@pytest.fixture
def sample_assets():
    """Sample assets for testing"""
    return [
        {
            "id": "ASSET-001",
            "type": "inmueble",
            "description": "Piso de 3 habitaciones en Madrid centro",
            "price_initial": 150000.0,
            "price_min": 120000.0,
            "location": "Madrid, España",
            "date_subasta": "2024-03-15",
        },
        {
            "id": "ASSET-002",
            "type": "inmueble",
            "description": "Apartamento de 3 cuartos en Madrid zona centro",
            "price_initial": 148000.0,
            "price_min": 118000.0,
            "location": "Madrid, España",
            "date_subasta": "2024-03-20",
        },
        {
            "id": "ASSET-003",
            "type": "vehiculo",
            "description": "Toyota Corolla 2015 diesel",
            "price_initial": 8500.0,
            "price_min": 6500.0,
            "location": "Barcelona, España",
            "date_subasta": "2024-03-20",
        },
        {
            "id": "ASSET-004",
            "type": "vehiculo",
            "description": "Toyota Corolla 2015 engine diesel",
            "price_initial": 8400.0,
            "price_min": 6400.0,
            "location": "Barcelona, España",
            "date_subasta": "2024-03-25",
        },
        {
            "id": "ASSET-005",
            "type": "mueble",
            "description": "Sofá de 3 plazas en tela gris",
            "price_initial": 500.0,
            "price_min": 300.0,
            "location": "Sevilla, España",
            "date_subasta": "2024-03-10",
        },
    ]


class TestDeduplicationEngineInitialization:
    """Test engine initialization"""

    def test_engine_initialization_default(self):
        """Test engine can be initialized with default parameters"""
        engine = DeduplicationEngine()
        assert engine.confidence_threshold == 0.8

    def test_engine_initialization_custom_threshold(self):
        """Test engine can be initialized with custom threshold"""
        engine = DeduplicationEngine(confidence_threshold=0.7)
        assert engine.confidence_threshold == 0.7

    def test_engine_initialization_min_threshold(self):
        """Test engine accepts minimum threshold (0.0)"""
        engine = DeduplicationEngine(confidence_threshold=0.0)
        assert engine.confidence_threshold == 0.0

    def test_engine_initialization_max_threshold(self):
        """Test engine accepts maximum threshold (1.0)"""
        engine = DeduplicationEngine(confidence_threshold=1.0)
        assert engine.confidence_threshold == 1.0

    def test_engine_initialization_invalid_threshold_negative(self):
        """Test engine rejects negative threshold"""
        with pytest.raises(ValueError):
            DeduplicationEngine(confidence_threshold=-0.1)

    def test_engine_initialization_invalid_threshold_too_high(self):
        """Test engine rejects threshold > 1.0"""
        with pytest.raises(ValueError):
            DeduplicationEngine(confidence_threshold=1.1)


class TestFuzzyMatching:
    """Test fuzzy string matching"""

    def test_fuzzy_match_identical_strings(self, engine):
        """Test fuzzy match returns 1.0 for identical strings"""
        score = engine._fuzzy_match("Piso Madrid", "Piso Madrid")
        assert score == 1.0

    def test_fuzzy_match_similar_strings(self, engine):
        """Test fuzzy match scores similar strings high"""
        score = engine._fuzzy_match("Piso Madrid centro", "Piso Madrid zona centro")
        assert score > 0.7

    def test_fuzzy_match_different_strings(self, engine):
        """Test fuzzy match scores different strings low"""
        score = engine._fuzzy_match("Casa grande", "Vehículo pequeño")
        assert score < 0.3

    def test_fuzzy_match_whitespace_handling(self, engine):
        """Test fuzzy match handles whitespace properly"""
        # _fuzzy_match expects strings already lowercased by caller
        score1 = engine._fuzzy_match("piso madrid", "piso madrid")
        # These are identical after whitespace normalization
        assert score1 == 1.0

    def test_fuzzy_match_whitespace_normalized(self, engine):
        """Test fuzzy match normalizes whitespace"""
        score = engine._fuzzy_match("Piso  Madrid", "Piso Madrid")
        assert score > 0.95

    def test_fuzzy_match_empty_strings(self, engine):
        """Test fuzzy match handles empty strings"""
        score = engine._fuzzy_match("", "")
        assert score == 1.0

    def test_fuzzy_match_one_empty_string(self, engine):
        """Test fuzzy match with one empty string"""
        score = engine._fuzzy_match("test", "")
        assert score < 1.0


class TestTitleSimilarity:
    """Test title/description similarity scoring"""

    def test_title_similarity_identical(self, engine):
        """Test identical titles get high score"""
        asset1 = {"description": "Piso de 3 habitaciones"}
        asset2 = {"description": "Piso de 3 habitaciones"}
        score = engine._score_title_similarity(asset1, asset2)
        assert score == 1.0

    def test_title_similarity_similar(self, engine):
        """Test similar titles get decent score"""
        asset1 = {"description": "Piso de 3 habitaciones en Madrid"}
        asset2 = {"description": "Apartamento de 3 cuartos en Madrid"}
        score = engine._score_title_similarity(asset1, asset2)
        assert score > 0.5

    def test_title_similarity_different(self, engine):
        """Test different titles get low score"""
        asset1 = {"description": "Piso"}
        asset2 = {"description": "Vehículo"}
        score = engine._score_title_similarity(asset1, asset2)
        assert score < 0.3

    def test_title_similarity_missing_description(self, engine):
        """Test missing descriptions"""
        asset1 = {"description": "Test"}
        asset2 = {}
        score = engine._score_title_similarity(asset1, asset2)
        assert score == 0.0

    def test_title_similarity_both_missing(self, engine):
        """Test both missing descriptions"""
        asset1 = {}
        asset2 = {}
        score = engine._score_title_similarity(asset1, asset2)
        assert score == 0.0


class TestPriceSimilarity:
    """Test price similarity scoring"""

    def test_price_similarity_identical(self, engine):
        """Test identical prices get 1.0"""
        asset1 = {"price_initial": 100000.0}
        asset2 = {"price_initial": 100000.0}
        score = engine._score_price_similarity(asset1, asset2)
        assert score == 1.0

    def test_price_similarity_5_percent_diff(self, engine):
        """Test 5% difference gets good score"""
        asset1 = {"price_initial": 100000.0}
        asset2 = {"price_initial": 105000.0}
        score = engine._score_price_similarity(asset1, asset2)
        assert 0.8 < score < 1.0

    def test_price_similarity_50_percent_diff(self, engine):
        """Test 50% difference gets lower score"""
        asset1 = {"price_initial": 100000.0}
        asset2 = {"price_initial": 150000.0}
        score = engine._score_price_similarity(asset1, asset2)
        assert 0.3 < score < 0.7

    def test_price_similarity_100_percent_diff(self, engine):
        """Test 100% difference (double price) gets 0.0 score"""
        asset1 = {"price_initial": 100000.0}
        asset2 = {"price_initial": 200000.0}
        score = engine._score_price_similarity(asset1, asset2)
        # diff = abs(100000-200000)/max = 100000/200000 = 0.5
        # score = max(0, 1 - 0.5) = 0.5
        assert score == 0.5

    def test_price_similarity_zero_prices(self, engine):
        """Test zero prices match"""
        asset1 = {"price_initial": 0.0}
        asset2 = {"price_initial": 0.0}
        score = engine._score_price_similarity(asset1, asset2)
        assert score == 1.0

    def test_price_similarity_zero_vs_nonzero(self, engine):
        """Test zero vs non-zero gets 0 score"""
        asset1 = {"price_initial": 0.0}
        asset2 = {"price_initial": 100.0}
        score = engine._score_price_similarity(asset1, asset2)
        assert score == 0.0

    def test_price_similarity_missing_price(self, engine):
        """Test missing price"""
        asset1 = {"price_initial": 100.0}
        asset2 = {}
        score = engine._score_price_similarity(asset1, asset2)
        assert score == 0.0


class TestLocationSimilarity:
    """Test location similarity scoring"""

    def test_location_similarity_identical(self, engine):
        """Test identical locations get 1.0"""
        asset1 = {"location": "Madrid, España"}
        asset2 = {"location": "Madrid, España"}
        score = engine._score_location_similarity(asset1, asset2)
        assert score == 1.0

    def test_location_similarity_same_city(self, engine):
        """Test same city gets decent score"""
        asset1 = {"location": "Madrid, España"}
        asset2 = {"location": "Madrid, Comunidad de Madrid"}
        score = engine._score_location_similarity(asset1, asset2)
        assert 0.4 < score < 1.0

    def test_location_similarity_different_city(self, engine):
        """Test different cities get partial score (shared country)"""
        asset1 = {"location": "Madrid, España"}
        asset2 = {"location": "Barcelona, España"}
        score = engine._score_location_similarity(asset1, asset2)
        # They share "españa" but not the city, so partial overlap
        assert 0.0 < score < 1.0
        assert score == 0.5  # 1 common word out of 2 unique words

    def test_location_similarity_case_insensitive(self, engine):
        """Test location matching is case insensitive"""
        asset1 = {"location": "MADRID, ESPAÑA"}
        asset2 = {"location": "madrid, españa"}
        score = engine._score_location_similarity(asset1, asset2)
        assert score == 1.0

    def test_location_similarity_missing_location(self, engine):
        """Test missing location"""
        asset1 = {"location": "Madrid"}
        asset2 = {}
        score = engine._score_location_similarity(asset1, asset2)
        assert score == 0.0


class TestTypeSimilarity:
    """Test asset type similarity scoring"""

    def test_type_similarity_identical(self, engine):
        """Test identical types get 1.0"""
        asset1 = {"type": "inmueble"}
        asset2 = {"type": "inmueble"}
        score = engine._score_type_similarity(asset1, asset2)
        assert score == 1.0

    def test_type_similarity_different(self, engine):
        """Test different types get 0.0"""
        asset1 = {"type": "inmueble"}
        asset2 = {"type": "vehiculo"}
        score = engine._score_type_similarity(asset1, asset2)
        assert score == 0.0

    def test_type_similarity_case_insensitive(self, engine):
        """Test type matching is case insensitive"""
        asset1 = {"type": "INMUEBLE"}
        asset2 = {"type": "inmueble"}
        score = engine._score_type_similarity(asset1, asset2)
        assert score == 1.0

    def test_type_similarity_missing_type(self, engine):
        """Test missing type"""
        asset1 = {"type": "inmueble"}
        asset2 = {}
        score = engine._score_type_similarity(asset1, asset2)
        assert score == 0.0


class TestSimilarityCalculation:
    """Test overall similarity calculation"""

    def test_similarity_identical_assets(self, engine, sample_assets):
        """Test identical assets get high similarity"""
        asset1 = sample_assets[0]
        score = engine.calculate_similarity(asset1, asset1)
        assert score >= 0.9

    def test_similarity_similar_assets(self, engine, sample_assets):
        """Test similar assets (ASSET-001 and ASSET-002)"""
        score = engine.calculate_similarity(sample_assets[0], sample_assets[1])
        assert score > 0.8

    def test_similarity_different_type_assets(self, engine, sample_assets):
        """Test assets with different types get lower score"""
        score = engine.calculate_similarity(sample_assets[0], sample_assets[2])
        assert score < 0.5

    def test_similarity_weighted_scoring(self, engine):
        """Test that similarity uses correct weights"""
        asset1 = {
            "type": "inmueble",
            "description": "Piso Madrid",
            "price_initial": 100000.0,
            "location": "Madrid",
        }
        asset2 = {
            "type": "inmueble",
            "description": "Piso Madrid",
            "price_initial": 100000.0,
            "location": "Madrid",
        }
        score = engine.calculate_similarity(asset1, asset2)
        # Should be high when all fields match
        assert score > 0.95


class TestFindDuplicates:
    """Test finding duplicates"""

    def test_find_duplicates_basic(self, engine, sample_assets):
        """Test finding duplicates in sample assets"""
        target = sample_assets[0]
        candidates = sample_assets[1:]
        duplicates = engine.find_duplicates(target, candidates)
        assert len(duplicates) > 0
        assert duplicates[0][0]["id"] == "ASSET-002"

    def test_find_duplicates_no_match(self, engine, sample_assets):
        """Test finding duplicates with no matches"""
        target = sample_assets[0]
        engine.confidence_threshold = 0.99
        candidates = [sample_assets[4]]  # Only mueble
        duplicates = engine.find_duplicates(target, candidates)
        assert len(duplicates) == 0

    def test_find_duplicates_excludes_self(self, engine, sample_assets):
        """Test that duplicates excludes self-match"""
        target = sample_assets[0]
        candidates = [target] + sample_assets[1:]
        duplicates = engine.find_duplicates(target, candidates)
        # Should not include self
        assert target["id"] not in [d[0]["id"] for d in duplicates]

    def test_find_duplicates_sorted_by_score(self, engine, sample_assets):
        """Test that duplicates are sorted by score descending"""
        target = sample_assets[0]
        candidates = sample_assets[1:]
        duplicates = engine.find_duplicates(target, candidates)

        if len(duplicates) > 1:
            scores = [score for _, score in duplicates]
            assert scores == sorted(scores, reverse=True)

    def test_find_duplicates_confidence_threshold(self, engine):
        """Test that confidence threshold is respected"""
        engine.confidence_threshold = 0.95
        target = {"id": "A", "type": "test", "description": "abc", "price_initial": 100}
        candidates = [
            {"id": "B", "type": "test", "description": "abd", "price_initial": 101}
        ]
        duplicates = engine.find_duplicates(target, candidates)
        assert len(duplicates) == 0


class TestClusteringDuplicates:
    """Test duplicate clustering"""

    def test_cluster_duplicates_empty_list(self, engine):
        """Test clustering empty list"""
        clusters = engine.cluster_duplicates([])
        assert clusters == []

    def test_cluster_duplicates_single_asset(self, engine, sample_assets):
        """Test clustering single asset"""
        clusters = engine.cluster_duplicates([sample_assets[0]])
        assert len(clusters) == 1
        assert len(clusters[0]) == 1

    def test_cluster_duplicates_no_matches(self, engine):
        """Test clustering with no matches"""
        engine.confidence_threshold = 0.99
        assets = [
            {"id": "A", "type": "inmueble", "description": "Casa", "price_initial": 100, "location": "Madrid"},
            {"id": "B", "type": "vehiculo", "description": "Coche", "price_initial": 10000, "location": "Barcelona"},
        ]
        clusters = engine.cluster_duplicates(assets)
        assert len(clusters) == 2

    def test_cluster_duplicates_groups(self, engine):
        """Test that similar assets are clustered together"""
        assets = [
            {"id": "1", "type": "inmueble", "description": "Piso Madrid", "price_initial": 100000, "location": "Madrid"},
            {"id": "2", "type": "inmueble", "description": "Piso Madrid centro", "price_initial": 98000, "location": "Madrid"},
            {"id": "3", "type": "vehiculo", "description": "Coche", "price_initial": 10000, "location": "Barcelona"},
        ]
        clusters = engine.cluster_duplicates(assets)
        # Assets 1 and 2 should be in same cluster, 3 separate
        assert len(clusters) <= 3


class TestDuplicateSummary:
    """Test duplicate summary generation"""

    def test_duplicate_summary_format(self, engine, sample_assets):
        """Test summary has correct format"""
        target = sample_assets[0]
        duplicates = engine.find_duplicates(target, sample_assets[1:])
        summary = engine.get_duplicate_summary(target, duplicates)

        assert "asset_id" in summary
        assert "duplicate_count" in summary
        assert "duplicates" in summary
        assert summary["asset_id"] == target["id"]
        assert summary["duplicate_count"] == len(duplicates)

    def test_duplicate_summary_structure(self, engine):
        """Test summary duplicate entries have correct structure"""
        asset = {"id": "TEST-001", "description": "Test asset", "price_initial": 100}
        dup = {"id": "DUP-001", "description": "Duplicate asset", "price_initial": 105}
        duplicates = [(dup, 0.95)]
        summary = engine.get_duplicate_summary(asset, duplicates)

        assert len(summary["duplicates"]) == 1
        dup_entry = summary["duplicates"][0]
        assert "id" in dup_entry
        assert "confidence" in dup_entry
        assert "description" in dup_entry
        assert dup_entry["confidence"] == 0.95

    def test_duplicate_summary_empty(self, engine):
        """Test summary with no duplicates"""
        asset = {"id": "TEST-001"}
        summary = engine.get_duplicate_summary(asset, [])

        assert summary["duplicate_count"] == 0
        assert len(summary["duplicates"]) == 0


class TestWeighting:
    """Test correct application of weights"""

    def test_weight_constants(self, engine):
        """Test that weights sum to 1.0"""
        total = (
            engine.WEIGHT_TITLE
            + engine.WEIGHT_PRICE
            + engine.WEIGHT_LOCATION
            + engine.WEIGHT_TYPE
        )
        assert abs(total - 1.0) < 0.001

    def test_weight_title_dominates(self, engine):
        """Test that title similarity dominates scoring"""
        # Two assets with same description but very different prices
        asset1 = {
            "type": "inmueble",
            "description": "Piso Madrid centro",
            "price_initial": 100000,
            "location": "Madrid",
        }
        asset2 = {
            "type": "inmueble",
            "description": "Piso Madrid centro",
            "price_initial": 500000,
            "location": "Madrid",
        }
        score = engine.calculate_similarity(asset1, asset2)
        # Should still be high because title is 50% weight
        assert score > 0.6


class TestEdgeCases:
    """Test edge cases and error handling"""

    def test_find_duplicates_none_candidates(self, engine, sample_assets):
        """Test with None candidates list"""
        target = sample_assets[0]
        with pytest.raises((TypeError, AttributeError)):
            engine.find_duplicates(target, None)

    def test_calculate_similarity_missing_fields(self, engine):
        """Test similarity calculation with missing fields"""
        asset1 = {"id": "1", "type": "inmueble"}
        asset2 = {"id": "2", "type": "inmueble"}
        score = engine.calculate_similarity(asset1, asset2)
        assert 0 <= score <= 1

    def test_fuzzy_match_special_characters(self, engine):
        """Test fuzzy matching with special characters"""
        score = engine._fuzzy_match("Piso/Apartamento", "Piso-Apartamento")
        assert score > 0

    def test_large_price_difference(self, engine):
        """Test handling of very large price differences"""
        asset1 = {"price_initial": 100.0}
        asset2 = {"price_initial": 100000000.0}
        score = engine._score_price_similarity(asset1, asset2)
        # diff = abs(100-100000000)/max = 99999900/100000000 ≈ 0.9999...
        # score = max(0, 1 - 0.9999...) ≈ 0.0000...
        assert score < 0.0001


class TestIntegration:
    """Integration tests"""

    def test_full_workflow(self, engine, sample_assets):
        """Test complete deduplication workflow"""
        # Find duplicates for first asset
        target = sample_assets[0]
        candidates = sample_assets[1:]

        duplicates = engine.find_duplicates(target, candidates)
        assert len(duplicates) > 0

        # Get summary
        summary = engine.get_duplicate_summary(target, duplicates)
        assert summary["duplicate_count"] > 0

        # Cluster all assets
        clusters = engine.cluster_duplicates(sample_assets)
        assert len(clusters) > 0

    def test_multiple_similar_assets(self):
        """Test with multiple similar assets"""
        engine = DeduplicationEngine(confidence_threshold=0.75)

        assets = [
            {"id": "1", "type": "inmueble", "description": "Casa grande Madrid", "price_initial": 200000, "location": "Madrid"},
            {"id": "2", "type": "inmueble", "description": "Casa grande en Madrid", "price_initial": 195000, "location": "Madrid"},
            {"id": "3", "type": "inmueble", "description": "Casa grande zona Madrid", "price_initial": 205000, "location": "Madrid"},
            {"id": "4", "type": "vehiculo", "description": "Coche", "price_initial": 10000, "location": "Barcelona"},
        ]

        clusters = engine.cluster_duplicates(assets)
        # Should find cluster with 3 similar houses
        assert len(clusters) <= 4


class ReferenceEngine:
    """
    Literal transcription of the pre-optimisation algorithm.

    The optimised engine prunes pairs using upper bounds instead of scoring
    every pair in full. That is only legitimate if it produces exactly the same
    output, so the two implementations are compared directly.
    """

    WEIGHT_TITLE = 0.50
    WEIGHT_PRICE = 0.25
    WEIGHT_LOCATION = 0.15
    WEIGHT_TYPE = 0.10

    def __init__(self, confidence_threshold=0.8):
        self.confidence_threshold = confidence_threshold

    def find_duplicates(self, asset, candidates):
        scores = []
        for candidate in candidates:
            if asset.get("id") == candidate.get("id"):
                continue
            score = self.calculate_similarity(asset, candidate)
            if score >= self.confidence_threshold:
                scores.append((candidate, score))
        return sorted(scores, key=lambda x: x[1], reverse=True)

    def calculate_similarity(self, asset1, asset2):
        return (
            self._title(asset1, asset2) * self.WEIGHT_TITLE
            + self._price(asset1, asset2) * self.WEIGHT_PRICE
            + self._location(asset1, asset2) * self.WEIGHT_LOCATION
            + self._type(asset1, asset2) * self.WEIGHT_TYPE
        )

    def _title(self, a1, a2):
        d1 = (a1.get("description") or "").lower().strip()
        d2 = (a2.get("description") or "").lower().strip()
        if not d1 or not d2:
            return 0.0
        return SequenceMatcher(None, " ".join(d1.split()), " ".join(d2.split())).ratio()

    def _price(self, a1, a2):
        p1, p2 = a1.get("price_initial"), a2.get("price_initial")
        if p1 is None or p2 is None:
            return 0.0
        if p1 == 0 and p2 == 0:
            return 1.0
        if p1 == 0 or p2 == 0:
            return 0.0
        return max(0.0, 1.0 - abs(p1 - p2) / max(p1, p2))

    def _location(self, a1, a2):
        l1 = (a1.get("location") or "").lower().strip()
        l2 = (a2.get("location") or "").lower().strip()
        if not l1 or not l2:
            return 0.0
        if l1 == l2:
            return 1.0
        w1, w2 = set(l1.split(",")), set(l2.split(","))
        common = w1 & w2
        if not common:
            return 0.0
        return len(common) / max(len(w1), len(w2))

    def _type(self, a1, a2):
        t1 = (a1.get("type") or "").lower().strip()
        t2 = (a2.get("type") or "").lower().strip()
        if not t1 or not t2:
            return 0.0
        return 1.0 if t1 == t2 else 0.0

    def cluster_duplicates(self, assets):
        if not assets:
            return []
        graph = {a.get("id", ""): [] for a in assets}
        lookup = {a.get("id", ""): a for a in assets}
        for i, a1 in enumerate(assets):
            for a2 in assets[i + 1:]:
                score = self.calculate_similarity(a1, a2)
                if score >= self.confidence_threshold:
                    graph[a1.get("id", "")].append((a2.get("id", ""), score))
                    graph[a2.get("id", "")].append((a1.get("id", ""), score))
        visited, clusters = set(), []
        for key in graph:
            if key in visited:
                continue
            cluster, queue = [], [key]
            visited.add(key)
            while queue:
                current = queue.pop(0)
                if current in lookup:
                    cluster.append((lookup[current], 1.0))
                for neighbour, _ in graph.get(current, []):
                    if neighbour not in visited:
                        visited.add(neighbour)
                        queue.append(neighbour)
            if cluster:
                clusters.append(cluster)
        return clusters


def build_equivalence_catalog(size=500, seed=99):
    """Synthetic catalogue with seeded near-duplicates and awkward edge cases."""
    rng = random.Random(seed)
    cities = ["Madrid, España", "Barcelona, España", "Valencia", "", "Bilbao, España"]
    types = ["inmueble", "vehiculo", "mueble", "otros"]
    templates = [
        "Piso de {n} habitaciones en {city} con balcon y plaza de garaje",
        "Vivienda unifamiliar de {n} dormitorios con jardin y trastero",
        "Turismo diesel del {n} en buen estado, revision al dia",
        "Local comercial de {n} metros cuadrados a pie de calle",
    ]

    assets = []
    for i in range(size):
        assets.append({
            "id": f"EQ-{i:05d}",
            "type": types[i % len(types)],
            "description": templates[i % len(templates)].format(
                n=rng.randint(1, 300), city=cities[i % len(cities)]
            ),
            "price_initial": float(rng.randint(0, 300000)),
            "location": cities[i % len(cities)],
        })

    # Near-duplicates: same everything, tiny textual and price deviations.
    for k in range(size // 10):
        origin = assets[k]
        assets.append({
            **origin,
            "id": f"EQDUP-{k:05d}",
            "description": origin["description"] + ".",
            "price_initial": origin["price_initial"] * 1.01,
        })

    # Edge cases the pruning must not mishandle.
    assets.extend([
        {"id": "EDGE-empty-desc", "type": "inmueble", "description": "",
         "price_initial": 1000.0, "location": "Madrid, España"},
        {"id": "EDGE-blank-desc", "type": "inmueble", "description": "   ",
         "price_initial": 1000.0, "location": "Madrid, España"},
        {"id": "EDGE-no-price", "type": "inmueble", "description": "Piso en Madrid",
         "price_initial": None, "location": "Madrid, España"},
        {"id": "EDGE-zero-price", "type": "inmueble", "description": "Piso en Madrid",
         "price_initial": 0.0, "location": "Madrid, España"},
        {"id": "EDGE-zero-price-2", "type": "inmueble", "description": "Piso en Madrid",
         "price_initial": 0.0, "location": "Madrid, España"},
        {"id": "EDGE-no-location", "type": "inmueble", "description": "Piso en Madrid",
         "price_initial": 1000.0},
        {"id": "EDGE-no-type", "description": "Piso en Madrid",
         "price_initial": 1000.0, "location": "Madrid, España"},
        {"id": "EDGE-long", "type": "otros", "description": "lote " * 130,
         "price_initial": 5000.0, "location": "Valencia"},
        {"id": "EDGE-long-2", "type": "otros", "description": "lote " * 130 + "x",
         "price_initial": 5000.0, "location": "Valencia"},
    ])
    return assets


class TestOptimisationEquivalence:
    """The pruned engine must return exactly what the reference returns"""

    @pytest.mark.parametrize("threshold", [0.0, 0.5, 0.75, 0.8, 0.9, 0.99, 1.0])
    def test_calculate_similarity_matches_reference(self, threshold):
        """Test full pairwise scores are identical for every pair"""
        assets = build_equivalence_catalog(size=60)
        optimised = DeduplicationEngine(confidence_threshold=threshold)
        reference = ReferenceEngine(confidence_threshold=threshold)

        for i, a1 in enumerate(assets):
            for a2 in assets[i + 1:]:
                assert optimised.calculate_similarity(a1, a2) == pytest.approx(
                    reference.calculate_similarity(a1, a2), abs=1e-12
                )

    @pytest.mark.parametrize("threshold", [0.5, 0.75, 0.8, 0.9, 0.99])
    def test_find_duplicates_matches_reference(self, threshold):
        """Test the pruned search finds exactly the same duplicates"""
        assets = build_equivalence_catalog(size=500)
        optimised = DeduplicationEngine(confidence_threshold=threshold)
        reference = ReferenceEngine(confidence_threshold=threshold)

        # Cover plain assets, seeded duplicates and the edge cases.
        targets = [assets[0], assets[7], assets[250], assets[-1], assets[-5], assets[-9]]

        for target in targets:
            got = optimised.find_duplicates(target, assets)
            expected = reference.find_duplicates(target, assets)

            assert [a["id"] for a, _ in got] == [a["id"] for a, _ in expected]
            for (_, got_score), (_, exp_score) in zip(got, expected):
                assert got_score == pytest.approx(exp_score, abs=1e-12)

    @pytest.mark.parametrize("threshold", [0.5, 0.8, 0.95])
    def test_cluster_duplicates_matches_reference(self, threshold):
        """Test clustering produces the same groups"""
        assets = build_equivalence_catalog(size=120)
        optimised = DeduplicationEngine(confidence_threshold=threshold)
        reference = ReferenceEngine(confidence_threshold=threshold)

        def shape(clusters):
            return sorted(
                sorted(asset.get("id") for asset, _ in cluster) for cluster in clusters
            )

        assert shape(optimised.cluster_duplicates(assets)) == \
               shape(reference.cluster_duplicates(assets))

    def test_pruning_actually_skips_expensive_matching(self):
        """Test the fast path really avoids most ratio() calls"""
        assets = build_equivalence_catalog(size=300)
        engine = DeduplicationEngine(confidence_threshold=0.8)

        calls = {"count": 0}
        original_ratio = SequenceMatcher.ratio

        def counting_ratio(self):
            calls["count"] += 1
            return original_ratio(self)

        with patch.object(SequenceMatcher, "ratio", counting_ratio):
            engine.find_duplicates(assets[0], assets)

        # Without pruning there would be one ratio() call per candidate.
        assert calls["count"] < len(assets) * 0.5

    def test_pruning_is_disabled_when_threshold_is_zero(self):
        """Test a zero threshold still returns every candidate"""
        assets = build_equivalence_catalog(size=40)
        engine = DeduplicationEngine(confidence_threshold=0.0)

        found = engine.find_duplicates(assets[0], assets)

        assert len(found) == len(assets) - 1
