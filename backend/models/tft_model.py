"""
Temporal Fusion Transformer (TFT) — stub implementation.
Full training requires GPU + historical data pipeline.
"""
import logging
import numpy as np

logger = logging.getLogger(__name__)


class TFTModel:
    """
    Temporal Fusion Transformer stub.
    
    Architecture:
    - Variable Selection Networks (VSN) for input selection
    - Long-Short Term Memory (LSTM) encoders for temporal state
    - Interpretable Multi-Head Attention for temporal self-attention
    - Point-wise feed-forward layers
    - Quantile output head (p10, p50, p90)
    
    In production: train with pytorch-forecasting library on 2+ years of OHLCV data.
    Stub returns plausible random signals for paper trading demo.
    """

    def __init__(self, sequence_length: int = 50, n_features: int = 5):
        self.sequence_length = sequence_length
        self.n_features = n_features
        self.is_trained = False
        logger.info("TFTModel initialised (stub mode — not trained)")

    def predict(self, candles: list[dict]) -> dict:
        """
        Returns trend signal from TFT.
        
        Returns:
            {
                "short_trend": float,   # -1 to +1, next 1h
                "long_trend": float,    # -1 to +1, next 24h
                "attention_peaks": list # timesteps with highest attention weight
            }
        """
        if len(candles) < 10:
            return {"short_trend": 0.0, "long_trend": 0.0, "attention_peaks": []}

        # Stub: compute momentum from closes
        closes = np.array([c["close"] for c in candles[-self.sequence_length:]])
        
        short_window = min(5, len(closes))
        long_window = min(20, len(closes))
        
        short_ma = closes[-short_window:].mean()
        long_ma = closes[-long_window:].mean()
        
        # Normalised trend signal
        if long_ma > 0:
            short_trend = np.clip((short_ma - long_ma) / long_ma * 50, -1, 1)
        else:
            short_trend = 0.0
        
        long_trend = np.clip(float(np.polyfit(range(len(closes)), closes, 1)[0] / closes.mean() * 100), -1, 1)
        
        # Attention peaks — indices with highest volatility (stub)
        if len(closes) > 3:
            volatility = np.abs(np.diff(closes))
            peaks = list(np.argsort(volatility)[-3:].tolist())
        else:
            peaks = []

        return {
            "short_trend": float(short_trend),
            "long_trend": float(long_trend),
            "attention_peaks": peaks,
        }

    def train(self, X: np.ndarray, y: np.ndarray):
        """Placeholder training method. Use pytorch-forecasting in production."""
        logger.info("TFTModel.train() called — stub, no actual training performed.")
        self.is_trained = True
