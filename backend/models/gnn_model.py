"""
GNN-TFT Hybrid — stub for modelling XAU/XAG/DXY correlations.
Full implementation requires torch-geometric + historical data.
"""
import logging
from typing import Dict, List

import numpy as np

logger = logging.getLogger(__name__)

# Static correlation graph edges (will be learned from data in production)
ASSET_NODES = ["XAU_USD", "XAG_USD", "EUR_USD", "BTCUSDT", "AAPL", "SPY"]
EDGES = [
    ("XAU_USD", "XAG_USD", 0.85),   # Gold-Silver correlation
    ("XAU_USD", "EUR_USD", 0.40),   # Gold-Dollar
    ("XAU_USD", "BTCUSDT", 0.30),   # Gold-BTC
    ("XAG_USD", "EUR_USD", 0.35),
    ("AAPL", "SPY", 0.78),
    ("BTCUSDT", "AAPL", 0.25),
]


class GNNCorrelationModel:
    """
    Graph Neural Network for cross-asset correlation modelling.
    
    Architecture (production):
    - Node features: last 50 OHLCV per asset → TFT embedding
    - Edge weights: rolling Pearson correlation (60-day)
    - Message passing: 2-layer GraphSAGE
    - Output: per-node signal adjustment + arbitrage-break probability
    
    Stub: uses static correlation weights to compute a signal boost.
    """

    def __init__(self):
        self.nodes = ASSET_NODES
        self.edges = EDGES
        logger.info("GNNCorrelationModel initialised (stub)")

    def _build_adjacency(self, asset_scores: Dict[str, float]) -> np.ndarray:
        n = len(self.nodes)
        adj = np.zeros((n, n))
        node_idx = {name: i for i, name in enumerate(self.nodes)}
        for src, dst, weight in self.edges:
            i, j = node_idx.get(src, -1), node_idx.get(dst, -1)
            if i >= 0 and j >= 0:
                adj[i][j] = weight
                adj[j][i] = weight
        return adj

    def propagate_signals(self, asset_scores: Dict[str, float]) -> Dict[str, float]:
        """
        Message passing: each node aggregates weighted signals from neighbours.
        Returns adjusted scores per asset.
        """
        adj = self._build_adjacency(asset_scores)
        node_idx = {name: i for i, name in enumerate(self.nodes)}
        signals = np.array([asset_scores.get(n, 0.0) for n in self.nodes])

        # 1-hop message passing
        neighbour_signals = adj @ signals
        row_sums = adj.sum(axis=1)
        row_sums[row_sums == 0] = 1.0
        aggregated = neighbour_signals / row_sums

        # Blend: 70% own signal + 30% neighbour consensus
        updated = 0.70 * signals + 0.30 * aggregated
        return {name: float(updated[node_idx[name]]) for name in self.nodes if name in asset_scores}

    def detect_arbitrage_break(self, asset_scores: Dict[str, float]) -> List[str]:
        """
        Detect when correlated assets diverge significantly (arbitrage opportunity).
        Returns list of asset pairs that are breaking their historical correlation.
        """
        breaks = []
        node_idx = {name: i for i, name in enumerate(self.nodes)}
        for src, dst, expected_corr in self.edges:
            s1 = asset_scores.get(src, 0.0)
            s2 = asset_scores.get(dst, 0.0)
            # If signs diverge on strongly correlated pairs
            if abs(expected_corr) > 0.6 and np.sign(s1) != np.sign(s2) and abs(s1) > 0.1 and abs(s2) > 0.1:
                breaks.append(f"{src}-{dst} (corr={expected_corr:.2f})")
        return breaks
