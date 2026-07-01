from datetime import date

from app.services import fear_greed_service
from app.services.fear_greed_service import _parse_cnn_payload


def test_parse_cnn_payload_accepts_iso_timestamp() -> None:
    sentiment = _parse_cnn_payload(
        {
            "fear_and_greed": {
                "score": 29.3714285714286,
                "rating": "fear",
                "timestamp": "2026-06-30T15:20:19+00:00",
            }
        }
    )

    assert sentiment.score == 29
    assert sentiment.label == "공포"
    assert sentiment.as_of == date(2026, 6, 30)


def test_fear_greed_service_sends_browser_like_headers(monkeypatch) -> None:
    captured_headers = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def read(self):
            return b'{"fear_and_greed":{"score":51,"rating":"neutral","timestamp":"2026-06-30T00:00:00+00:00"}}'

    def fake_urlopen(request, timeout):
        nonlocal captured_headers
        captured_headers = dict(request.header_items())
        return FakeResponse()

    monkeypatch.setattr(fear_greed_service, "urlopen", fake_urlopen)

    sentiment = fear_greed_service.FearGreedService().get_current()

    assert sentiment.score == 51
    assert "Mozilla" in captured_headers["User-agent"]
    assert captured_headers["Referer"] == "https://www.cnn.com/markets/fear-and-greed"
    assert captured_headers["Origin"] == "https://www.cnn.com"
