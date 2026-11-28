"""ML-based risk scoring using IsolationForest.

Provides anomaly detection on wallet behavioral features:
- Transaction frequency patterns
- Value distribution
- Address reuse patterns
- Gas usage patterns
- Temporal patterns

Produces an anomaly score (0.0 = normal, 1.0 = highly anomalous)
and feature importances for explainability.
"""
from __future__ import annotations

import logging
import math
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)

MODEL_VERSION = "1.0.0"


def _extract_features(address: str, txs: list[dict[str, Any]]) -> dict[str, float]:
    """Extract behavioral features from transaction history."""
    if not txs:
        return {
            "tx_count": 0,
            "avg_value": 0.0,
            "max_value": 0.0,
            "std_value": 0.0,
            "unique_counterparties": 0,
            "avg_gas_price": 0.0,
            "inbound_ratio": 0.0,
            "avg_time_between_txs": 0.0,
            "hour_entropy": 0.0,
            "value_entropy": 0.0,
            "peel_chain_score": 0.0,
        }

    addr_lower = address.lower()
    values: list[float] = []
    inbound = 0
    outbound = 0
    counterparties: set[str] = set()
    timestamps: list[float] = []
    gas_prices: list[float] = []

    for tx in txs:
        from_addr = tx.get("from", "").lower()
        to_addr = tx.get("to", "").lower()
        value = float(tx.get("value", "0") or "0")
        gas_price = float(tx.get("gasPrice", "0") or "0")
        timestamp = float(tx.get("timeStamp", "0") or "0")

        values.append(value)
        timestamps.append(timestamp)
        gas_prices.append(gas_price)

        if from_addr == addr_lower:
            outbound += 1
            counterparties.add(to_addr)
        else:
            inbound += 1
            counterparties.add(from_addr)

    total = len(txs)
    avg_value = sum(values) / total if total else 0.0
    max_value = max(values) if values else 0.0
    std_value = float(np.std(values)) if len(values) > 1 else 0.0
    avg_gas = sum(gas_prices) / total if total else 0.0
    inbound_ratio = inbound / total if total else 0.0

    # Time between txs
    avg_time = 0.0
    if len(timestamps) > 1:
        sorted_ts = sorted(timestamps)
        diffs = [sorted_ts[i+1] - sorted_ts[i] for i in range(len(sorted_ts)-1)]
        avg_time = sum(diffs) / len(diffs) if diffs else 0.0

    # Hour entropy (when does this address transact)
    hour_counts = [0] * 24
    for ts in timestamps:
        if ts > 0:
            hour = int(datetime.fromtimestamp(ts, tz=timezone.utc).hour)
            hour_counts[hour] += 1
    hour_entropy = _entropy(hour_counts)

    # Value entropy (are values diverse or concentrated)
    if values:
        # Bin values into 10 buckets
        max_val = max(values) if max(values) > 0 else 1.0
        bins = [0] * 10
        for v in values:
            bucket = min(int(v / max_val * 9), 9)
            bins[bucket] += 1
        value_entropy = _entropy(bins)
    else:
        value_entropy = 0.0

    # Peel chain score: ratio of transactions where output is much smaller than input
    peel_count = 0
    for tx in txs:
        if tx.get("from", "").lower() == addr_lower:
            value = float(tx.get("value", "0") or "0")
            if 0 < value < avg_value * 0.1 if avg_value > 0 else False:
                peel_count += 1
    peel_score = peel_count / total if total else 0.0

    return {
        "tx_count": total,
        "avg_value": avg_value,
        "max_value": max_value,
        "std_value": std_value,
        "unique_counterparties": len(counterparties),
        "avg_gas_price": avg_gas,
        "inbound_ratio": inbound_ratio,
        "avg_time_between_txs": avg_time,
        "hour_entropy": hour_entropy,
        "value_entropy": value_entropy,
        "peel_chain_score": peel_score,
    }


def _entropy(counts: list[int]) -> float:
    """Compute normalized entropy of a distribution."""
    total = sum(counts)
    if total == 0:
        return 0.0
    probs = [c / total for c in counts if c > 0]
    ent = -sum(p * math.log2(p) for p in probs)
    max_ent = math.log2(len(counts)) if len(counts) > 1 else 1.0
    return ent / max_ent if max_ent > 0 else 0.0


class AnomalyScorer:
    """IsolationForest-based anomaly scorer for wallet behavior."""

    def __init__(self) -> None:
        self._model: IsolationForest | None = None
        self._scaler: StandardScaler | None = None
        self._feature_names: list[str] = []
        self._version = MODEL_VERSION

    def train(self, feature_matrix: list[dict[str, float]]) -> dict[str, Any]:
        """Train the anomaly detection model on a set of wallet features."""
        if len(feature_matrix) < 10:
            return {"status": "insufficient_data", "min_required": 10}

        self._feature_names = list(feature_matrix[0].keys())
        X = np.array([[f[n] for n in self._feature_names] for f in feature_matrix])

        self._scaler = StandardScaler()
        X_scaled = self._scaler.fit_transform(X)

        self._model = IsolationForest(
            n_estimators=100,
            contamination=0.1,
            max_samples="auto",
            random_state=42,
            n_jobs=-1,
        )
        self._model.fit(X_scaled)

        return {
            "status": "trained",
            "samples": len(feature_matrix),
            "features": self._feature_names,
            "version": self._version,
        }

    def score(
        self, features: dict[str, float]
    ) -> dict[str, Any]:
        """Score a single wallet's features for anomaly.

        Returns:
            anomaly_score: 0.0 (normal) to 1.0 (highly anomalous)
            feature_importances: dict of feature -> contribution to anomaly
        """
        if self._model is None or self._scaler is None:
            # No trained model: say so instead of reporting a "0% anomalous"
            # score that was never computed.
            return {
                "anomaly_score": None,
                "feature_importances": {},
                "model_version": None,
                "status": "no_model",
            }

        try:
            X = np.array([[features.get(n, 0.0) for n in self._feature_names]])
            X_scaled = self._scaler.transform(X)

            raw_score = self._model.decision_function(X_scaled)[0]
            # decision_function returns score where negative = anomaly
            # Map to 0.0 (normal) to 1.0 (anomalous)
            # Typical range: -0.5 (very anomalous) to 0.5 (very normal)
            anomaly_score = max(0.0, min(1.0, 0.5 - raw_score))

            # Feature importances via deviation from training mean
            feature_importances = {}
            if hasattr(self._scaler, 'mean_') and hasattr(self._scaler, 'scale_'):
                for i, name in enumerate(self._feature_names):
                    mean = self._scaler.mean_[i]
                    std = self._scaler.scale_[i]
                    if std > 0:
                        z_score = abs(X[0][i] - mean) / std
                        feature_importances[name] = round(min(z_score / 3.0, 1.0), 4)

            return {
                "anomaly_score": round(anomaly_score, 4),
                "feature_importances": feature_importances,
                "model_version": self._version,
                "status": "scored",
            }
        except Exception as e:
            logger.error("Anomaly scoring failed: %s", e)
            return {
                "anomaly_score": 0.0,
                "feature_importances": {},
                "model_version": self._version,
                "status": "error",
            }


def explain_anomaly(features: dict[str, float], importances: dict[str, float]) -> str:
    """Generate a human-readable explanation of why a wallet is anomalous."""
    if not importances:
        return "No anomaly features detected."

    # Sort by importance descending
    top_features = sorted(importances.items(), key=lambda x: x[1], reverse=True)[:5]

    explanations = []
    for feature, importance in top_features:
        if importance < 0.1:
            continue
        value = features.get(feature, 0.0)

        if feature == "tx_count":
            if value > 1000:
                explanations.append(f"Very high transaction count ({int(value)})")
            elif value < 3:
                explanations.append(f"Very few transactions ({int(value)})")
        elif feature == "unique_counterparties":
            if value > 500:
                explanations.append(f"Interacts with many unique addresses ({int(value)})")
            elif value == 1:
                explanations.append("Only interacts with one other address")
        elif feature == "inbound_ratio":
            if value > 0.9:
                explanations.append("Almost all transactions are inbound (potential fund receiving)")
            elif value < 0.1:
                explanations.append("Almost all transactions are outbound (potential fund draining)")
        elif feature == "hour_entropy":
            if value < 0.3:
                explanations.append("Very consistent transaction timing (automated behavior)")
        elif feature == "peel_chain_score":
            if value > 0.3:
                explanations.append(f"Peeling chain behavior detected ({int(value*100)}% of txs)")
        elif feature == "std_value":
            if value > 100:
                explanations.append("High variance in transaction values")

    if not explanations:
        return "Mild statistical deviation from normal behavior."

    return "; ".join(explanations) + "."


# ── Module-level scorer instance ────────────────────────────────────────────

scorer = AnomalyScorer()
