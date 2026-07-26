"""
Deduplication engine for AssetFinder
Provides fuzzy matching and duplicate detection with weighted scoring
"""

from typing import List, Dict, Tuple, Optional, Set
from difflib import SequenceMatcher
import logging

logger = logging.getLogger(__name__)


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
        self, asset: Dict, candidates: List[Dict]
    ) -> List[Tuple[Dict, float]]:
        """
        Find potential duplicates for an asset.

        Args:
            asset: Asset to find duplicates for
            candidates: List of candidate assets to compare against

        Returns:
            List of (asset, confidence_score) tuples sorted by score descending
        """
        scores = []
        for candidate in candidates:
            if asset.get("id") == candidate.get("id"):
                continue  # Skip self-comparison

            score = self.calculate_similarity(asset, candidate)
            if score >= self.confidence_threshold:
                scores.append((candidate, score))

        # Sort by score descending
        return sorted(scores, key=lambda x: x[1], reverse=True)

    def calculate_similarity(self, asset1: Dict, asset2: Dict) -> float:
        """
        Calculate similarity score between two assets.

        Args:
            asset1: First asset
            asset2: Second asset

        Returns:
            Weighted similarity score (0.0-1.0)
        """
        scores = {
            "title": self._score_title_similarity(asset1, asset2),
            "price": self._score_price_similarity(asset1, asset2),
            "location": self._score_location_similarity(asset1, asset2),
            "type": self._score_type_similarity(asset1, asset2),
        }

        # Calculate weighted score
        total_score = (
            scores["title"] * self.WEIGHT_TITLE
            + scores["price"] * self.WEIGHT_PRICE
            + scores["location"] * self.WEIGHT_LOCATION
            + scores["type"] * self.WEIGHT_TYPE
        )

        return total_score

    def _score_title_similarity(self, asset1: Dict, asset2: Dict) -> float:
        """Score similarity of descriptions/titles (50% weight)"""
        desc1 = (asset1.get("description") or "").lower().strip()
        desc2 = (asset2.get("description") or "").lower().strip()

        if not desc1 or not desc2:
            return 0.0

        return self._fuzzy_match(desc1, desc2)

    def _score_price_similarity(self, asset1: Dict, asset2: Dict) -> float:
        """Score similarity of prices (25% weight)"""
        price1 = asset1.get("price_initial")
        price2 = asset2.get("price_initial")

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

    def _score_location_similarity(self, asset1: Dict, asset2: Dict) -> float:
        """Score similarity of locations (15% weight)"""
        loc1 = (asset1.get("location") or "").lower().strip()
        loc2 = (asset2.get("location") or "").lower().strip()

        if not loc1 or not loc2:
            return 0.0

        # Exact match
        if loc1 == loc2:
            return 1.0

        # Partial match on key words (city names)
        words1 = set(loc1.split(","))
        words2 = set(loc2.split(","))
        common = words1 & words2

        if not common:
            return 0.0

        # Score based on overlap
        return len(common) / max(len(words1), len(words2))

    def _score_type_similarity(self, asset1: Dict, asset2: Dict) -> float:
        """Score similarity of asset types (10% weight)"""
        type1 = asset1.get("type", "").lower().strip()
        type2 = asset2.get("type", "").lower().strip()

        if not type1 or not type2:
            return 0.0

        return 1.0 if type1 == type2 else 0.0

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
        self, assets: List[Dict]
    ) -> List[List[Tuple[Dict, float]]]:
        """
        Cluster assets into groups of duplicates using graph-based approach.

        Args:
            assets: List of assets to cluster

        Returns:
            List of clusters, each cluster is a list of (asset, confidence) tuples
        """
        if not assets:
            return []

        # Build similarity graph
        graph: Dict[str, List[Tuple[str, float]]] = {
            asset.get("id", ""): [] for asset in assets
        }

        asset_dict = {asset.get("id", ""): asset for asset in assets}

        for i, asset1 in enumerate(assets):
            id1 = asset1.get("id", "")
            for asset2 in assets[i + 1 :]:
                id2 = asset2.get("id", "")
                score = self.calculate_similarity(asset1, asset2)
                if score >= self.confidence_threshold:
                    graph[id1].append((id2, score))
                    graph[id2].append((id1, score))

        # Find connected components (clusters)
        visited: Set[str] = set()
        clusters: List[List[Tuple[Dict, float]]] = []

        for asset_id in graph:
            if asset_id not in visited:
                cluster = self._find_cluster(asset_id, graph, asset_dict, visited)
                if cluster:
                    clusters.append(cluster)

        return clusters

    def _find_cluster(
        self,
        start_id: str,
        graph: Dict[str, List[Tuple[str, float]]],
        assets: Dict[str, Dict],
        visited: Set[str],
    ) -> List[Tuple[Dict, float]]:
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
        queue = [start_id]
        visited.add(start_id)

        while queue:
            current_id = queue.pop(0)
            if current_id in assets:
                cluster.append((assets[current_id], 1.0))

            # Add connected neighbors
            for neighbor_id, score in graph.get(current_id, []):
                if neighbor_id not in visited:
                    visited.add(neighbor_id)
                    queue.append(neighbor_id)

        return cluster

    def get_duplicate_summary(
        self, asset: Dict, duplicates: List[Tuple[Dict, float]]
    ) -> Dict:
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
