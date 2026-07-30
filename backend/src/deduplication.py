"""
Deduplication engine for AssetFinder
Provides fuzzy matching and duplicate detection with weighted scoring
"""

import logging
from collections import deque
from difflib import SequenceMatcher
from typing import Any

logger = logging.getLogger(__name__)


class _PreparedAsset:
    """
    Normalised view of an asset, built once per asset instead of once per
    comparison. Comparing N assets is quadratic in pairs, so lowercasing and
    splitting the same strings inside the inner loop was pure waste.
    """

    __slots__ = ("asset", "id", "cluster_key", "description", "location",
                 "location_parts", "type", "price")

    def __init__(self, asset: dict[str, Any]):
        self.asset = asset
        self.id = asset.get("id")
        # cluster_duplicates keys its graph with a "" default for absent ids.
        self.cluster_key = asset.get("id", "")

        # _fuzzy_match collapsed runs of whitespace before matching; doing it
        # here keeps the comparison identical and hoists it out of the loop.
        description = (asset.get("description") or "").lower().strip()
        self.description = " ".join(description.split())

        location = (asset.get("location") or "").lower().strip()
        self.location = location
        # Parts are deliberately not stripped: the original comparison split on
        # "," only, so "madrid, españa" yields {"madrid", " españa"}.
        self.location_parts: set[str] = set(location.split(",")) if location else set()

        self.type = (asset.get("type") or "").lower().strip()
        self.price = asset.get("price_initial")


class DeduplicationEngine:
    """
    Fuzzy matching deduplication system with weighted scoring.

    Scoring weights:
    - Title/Description: 50%
    - Price: 25%
    - Location: 15%
    - Type: 10%
    """

    # Scoring weights (must sum to 1.0)
    WEIGHT_TITLE = 0.50
    WEIGHT_PRICE = 0.25
    WEIGHT_LOCATION = 0.15
    WEIGHT_TYPE = 0.10

    # Slack for the pruning bounds. Summing the weighted scores in a different
    # order can differ from calculate_similarity by ~1e-16, so bounds are
    # relaxed by a margin far larger than that error and far smaller than any
    # meaningful score difference. Guarantees pruning never drops a real match.
    _PRUNE_EPSILON = 1e-12

    def __init__(self, confidence_threshold: float = 0.8):
        """
        Initialize deduplication engine.

        Args:
            confidence_threshold: Minimum confidence score to consider duplicates (0.0-1.0)
        """
        if not 0 <= confidence_threshold <= 1:
            raise ValueError("confidence_threshold must be between 0 and 1")
        self.confidence_threshold = confidence_threshold

    def find_duplicates(
        self, asset: dict, candidates: list[dict]
    ) -> list[tuple[dict, float]]:
        """
        Find potential duplicates for an asset.

        Args:
            asset: Asset to find duplicates for
            candidates: List of candidate assets to compare against

        Returns:
            List of (asset, confidence_score) tuples sorted by score descending
        """
        target = _PreparedAsset(asset)

        # One matcher reused across candidates. The target stays as sequence "a"
        # and each candidate becomes "b", the same orientation the per-pair
        # SequenceMatcher used, which matters because difflib's autojunk
        # heuristic only applies to "b".
        matcher = SequenceMatcher(None)
        matcher.set_seq1(target.description)

        scores = []
        for candidate in candidates:
            if target.id == candidate.get("id"):
                continue  # Skip self-comparison

            score = self._score_if_confident(target, _PreparedAsset(candidate), matcher)
            if score is not None:
                scores.append((candidate, score))

        # Sort by score descending
        return sorted(scores, key=lambda x: x[1], reverse=True)

    def calculate_similarity(self, asset1: dict, asset2: dict) -> float:
        """
        Calculate similarity score between two assets.

        Args:
            asset1: First asset
            asset2: Second asset

        Returns:
            Weighted similarity score (0.0-1.0)
        """
        p1 = _PreparedAsset(asset1)
        p2 = _PreparedAsset(asset2)

        return self._combine(
            self._title_score(p1, p2),
            self._price_score(p1, p2),
            self._location_score(p1, p2),
            self._type_score(p1, p2),
        )

    def _combine(
        self, title: float, price: float, location: float, type_: float
    ) -> float:
        """
        Weighted sum of the four sub-scores.

        The operand order is fixed so that a score obtained through the pruning
        path is bit-identical to one obtained through calculate_similarity.
        """
        return (
            title * self.WEIGHT_TITLE
            + price * self.WEIGHT_PRICE
            + location * self.WEIGHT_LOCATION
            + type_ * self.WEIGHT_TYPE
        )

    def _score_if_confident(
        self, p1: _PreparedAsset, p2: _PreparedAsset, matcher: SequenceMatcher
    ):
        """
        Exact similarity score if the pair reaches the confidence threshold,
        otherwise None.

        The three cheap sub-scores (price, location, type) are O(1) and account
        for half of the total weight; the title score needs sequence matching
        and dominates the cost. Since the title score cannot exceed 1.0, any
        pair whose cheap score leaves too little room to reach the threshold is
        rejected without matching at all. difflib's real_quick_ratio() and
        quick_ratio() are documented upper bounds of ratio(), giving two more
        progressively tighter bail-outs. The result is exact: no pair that would
        have reached the threshold is discarded.
        """
        threshold = self.confidence_threshold

        price = self._price_score(p1, p2)
        location = self._location_score(p1, p2)
        type_ = self._type_score(p1, p2)

        cheap = (
            price * self.WEIGHT_PRICE
            + location * self.WEIGHT_LOCATION
            + type_ * self.WEIGHT_TYPE
        )

        # Upper bound assuming a perfect title match.
        if cheap + self.WEIGHT_TITLE + self._PRUNE_EPSILON < threshold:
            return None

        if not p1.description or not p2.description:
            title = 0.0
        else:
            matcher.set_seq2(p2.description)

            if cheap + self.WEIGHT_TITLE * matcher.real_quick_ratio() \
                    + self._PRUNE_EPSILON < threshold:
                return None

            if cheap + self.WEIGHT_TITLE * matcher.quick_ratio() \
                    + self._PRUNE_EPSILON < threshold:
                return None

            title = matcher.ratio()

        total = self._combine(title, price, location, type_)
        return total if total >= threshold else None

    def _title_score(self, p1: _PreparedAsset, p2: _PreparedAsset) -> float:
        """Score similarity of descriptions/titles (50% weight)"""
        if not p1.description or not p2.description:
            return 0.0

        return SequenceMatcher(None, p1.description, p2.description).ratio()

    def _price_score(self, p1: _PreparedAsset, p2: _PreparedAsset) -> float:
        """Score similarity of prices (25% weight)"""
        price1 = p1.price
        price2 = p2.price

        if price1 is None or price2 is None:
            return 0.0

        # Perfect match if within 5% difference
        if price1 == 0 and price2 == 0:
            return 1.0

        if price1 == 0 or price2 == 0:
            return 0.0

        # Calculate percentage difference
        diff = abs(price1 - price2) / max(price1, price2)

        # Score: 1.0 if 0% diff, 0.0 if 100%+ diff
        return max(0.0, 1.0 - diff)

    def _location_score(self, p1: _PreparedAsset, p2: _PreparedAsset) -> float:
        """Score similarity of locations (15% weight)"""
        if not p1.location or not p2.location:
            return 0.0

        # Exact match
        if p1.location == p2.location:
            return 1.0

        # Partial match on key words (city names)
        common = p1.location_parts & p2.location_parts

        if not common:
            return 0.0

        # Score based on overlap
        return len(common) / max(len(p1.location_parts), len(p2.location_parts))

    def _type_score(self, p1: _PreparedAsset, p2: _PreparedAsset) -> float:
        """Score similarity of asset types (10% weight)"""
        if not p1.type or not p2.type:
            return 0.0

        return 1.0 if p1.type == p2.type else 0.0

    # ------------------------------------------------------------------
    # Dict-based wrappers: the per-field scoring API, kept for callers and
    # tests that score two raw assets directly.
    # ------------------------------------------------------------------

    def _score_title_similarity(self, asset1: dict, asset2: dict) -> float:
        """Score similarity of descriptions/titles (50% weight)"""
        return self._title_score(_PreparedAsset(asset1), _PreparedAsset(asset2))

    def _score_price_similarity(self, asset1: dict, asset2: dict) -> float:
        """Score similarity of prices (25% weight)"""
        return self._price_score(_PreparedAsset(asset1), _PreparedAsset(asset2))

    def _score_location_similarity(self, asset1: dict, asset2: dict) -> float:
        """Score similarity of locations (15% weight)"""
        return self._location_score(_PreparedAsset(asset1), _PreparedAsset(asset2))

    def _score_type_similarity(self, asset1: dict, asset2: dict) -> float:
        """Score similarity of asset types (10% weight)"""
        return self._type_score(_PreparedAsset(asset1), _PreparedAsset(asset2))

    def _fuzzy_match(self, str1: str, str2: str) -> float:
        """
        Calculate fuzzy match ratio between two strings.

        Args:
            str1: First string
            str2: Second string

        Returns:
            Match ratio (0.0-1.0)
        """
        # Remove extra whitespace
        str1 = " ".join(str1.split())
        str2 = " ".join(str2.split())

        # Use SequenceMatcher for fuzzy matching
        matcher = SequenceMatcher(None, str1, str2)
        return matcher.ratio()

    def cluster_duplicates(
        self, assets: list[dict]
    ) -> list[list[tuple[dict, float]]]:
        """
        Cluster assets into groups of duplicates using graph-based approach.

        Args:
            assets: List of assets to cluster

        Returns:
            List of clusters, each cluster is a list of (asset, confidence) tuples
        """
        if not assets:
            return []

        prepared = [_PreparedAsset(asset) for asset in assets]

        # Build similarity graph
        graph: dict[str, list[tuple[str, float]]] = {p.cluster_key: [] for p in prepared}
        asset_dict = {p.cluster_key: p.asset for p in prepared}

        matcher = SequenceMatcher(None)
        total = len(prepared)

        for i in range(total):
            p1 = prepared[i]
            # Sequence "a" only changes once per outer iteration.
            matcher.set_seq1(p1.description)
            key1 = p1.cluster_key

            for j in range(i + 1, total):
                p2 = prepared[j]
                score = self._score_if_confident(p1, p2, matcher)
                if score is not None:
                    graph[key1].append((p2.cluster_key, score))
                    graph[p2.cluster_key].append((key1, score))

        # Find connected components (clusters)
        visited: set[str] = set()
        clusters: list[list[tuple[dict, float]]] = []

        for asset_id in graph:
            if asset_id not in visited:
                cluster = self._find_cluster(asset_id, graph, asset_dict, visited)
                if cluster:
                    clusters.append(cluster)

        return clusters

    def _find_cluster(
        self,
        start_id: str,
        graph: dict[str, list[tuple[str, float]]],
        assets: dict[str, dict],
        visited: set[str],
    ) -> list[tuple[dict, float]]:
        """
        Find a cluster of duplicates starting from a given asset ID using BFS.

        Args:
            start_id: Starting asset ID
            graph: Similarity graph
            assets: Asset dictionary
            visited: Set of visited asset IDs

        Returns:
            Cluster of (asset, confidence) tuples
        """
        cluster = []
        # deque: popping the head of a list is O(n), making the traversal O(n^2).
        queue = deque([start_id])
        visited.add(start_id)

        while queue:
            current_id = queue.popleft()
            if current_id in assets:
                cluster.append((assets[current_id], 1.0))

            # Add connected neighbors
            # The edge score is not needed here, only connectivity.
            for neighbor_id, _score in graph.get(current_id, []):
                if neighbor_id not in visited:
                    visited.add(neighbor_id)
                    queue.append(neighbor_id)

        return cluster

    def get_duplicate_summary(
        self, asset: dict, duplicates: list[tuple[dict, float]]
    ) -> dict:
        """
        Generate a summary of duplicate information.

        Args:
            asset: Original asset
            duplicates: List of (duplicate_asset, confidence_score) tuples

        Returns:
            Dictionary with duplicate summary
        """
        return {
            "asset_id": asset.get("id"),
            "duplicate_count": len(duplicates),
            "duplicates": [
                {
                    "id": dup_asset.get("id"),
                    "confidence": round(score, 3),
                    "description": dup_asset.get("description", "")[:100],
                }
                for dup_asset, score in duplicates
            ],
        }
