from dataclasses import dataclass
from datetime import date, datetime
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen
import json


CNN_FEAR_GREED_URL = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"


@dataclass(frozen=True)
class MarketSentiment:
    score: int | None
    rating: str | None
    label: str
    as_of: date | None
    source: str
    available: bool = True


class FearGreedService:
    def get_current(self) -> MarketSentiment:
        try:
            request = Request(
                CNN_FEAR_GREED_URL,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/126.0.0.0 Safari/537.36"
                    ),
                    "Accept": "application/json,text/plain,*/*",
                    "Accept-Language": "en-US,en;q=0.9,ko;q=0.8",
                    "Origin": "https://www.cnn.com",
                    "Referer": "https://www.cnn.com/markets/fear-and-greed",
                },
            )
            with urlopen(request, timeout=2) as response:
                payload = json.loads(response.read().decode("utf-8"))
            return _parse_cnn_payload(payload)
        except (OSError, URLError, TimeoutError, ValueError, KeyError, TypeError):
            return MarketSentiment(
                score=None,
                rating=None,
                label="데이터 대기",
                as_of=None,
                source="CNN Fear & Greed",
                available=False,
            )


def _parse_cnn_payload(payload: dict[str, Any]) -> MarketSentiment:
    fear_and_greed = payload.get("fear_and_greed") or {}
    raw_score = fear_and_greed.get("score")
    score = int(round(float(raw_score))) if raw_score is not None else None
    rating = str(fear_and_greed.get("rating") or "").lower() or None
    timestamp = fear_and_greed.get("timestamp")
    as_of = _parse_timestamp(timestamp)
    return MarketSentiment(
        score=score,
        rating=rating,
        label=_label_for_score(score, rating),
        as_of=as_of,
        source="CNN Fear & Greed",
        available=score is not None,
    )


def _parse_timestamp(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
        except ValueError:
            pass
    try:
        timestamp = float(value)
    except (TypeError, ValueError):
        return None
    if timestamp > 10_000_000_000:
        timestamp = timestamp / 1000
    return datetime.fromtimestamp(timestamp).date()


def _label_for_score(score: int | None, rating: str | None) -> str:
    if score is None:
        return "데이터 대기"
    labels = {
        "extreme fear": "극단적 공포",
        "fear": "공포",
        "neutral": "중립",
        "greed": "탐욕",
        "extreme greed": "극단적 탐욕",
    }
    if rating in labels:
        return labels[rating]
    if score <= 24:
        return "극단적 공포"
    if score <= 44:
        return "공포"
    if score <= 55:
        return "중립"
    if score <= 75:
        return "탐욕"
    return "극단적 탐욕"
