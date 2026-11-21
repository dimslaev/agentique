"""Feed items that link through a redirect are stored under the page they land on."""

from __future__ import annotations

import pytest

from app.features.collect import redirects
from app.features.collect.model import RawItem


def _item(url: str) -> RawItem:
    return {
        "title": url,
        "url": url,
        "content": "text",
        "published_date": None,
        "source": "Console",
    }


def test_the_ref_marker_goes_and_other_params_stay() -> None:
    assert (
        redirects.without_ref("https://ui-sdk.dev/docs/intro?ref=console.dev&v=2")
        == "https://ui-sdk.dev/docs/intro?v=2"
    )
    assert redirects.without_ref("https://x.dev/a") == "https://x.dev/a"


def test_only_redirect_items_move(monkeypatch: pytest.MonkeyPatch) -> None:
    lands = {
        "https://console.dev/out/ui-sdk/abc": "https://ui-sdk.dev/docs/intro",
        "https://console.dev/out/dead/def": None,
    }
    monkeypatch.setattr(redirects, "_destination", lands.__getitem__)
    items = [_item(u) for u in [*lands, "https://jiff.rs/"]]

    redirects.unwrap_redirects(items)

    assert [a["url"] for a in items] == [
        "https://ui-sdk.dev/docs/intro",
        "https://console.dev/out/dead/def",
        "https://jiff.rs/",
    ]
