"""OCR providers (issues #61, #68) with no network and no OCR binary: the Claude provider builds the
right request against a fake client, Tesseract is driven through a fake ``subprocess.run``, the
fake provider reads the embedded text, and OCR_PROVIDER selects between them."""

from __future__ import annotations

import base64
import io
import subprocess
from decimal import Decimal
from types import SimpleNamespace

import pytest
from PIL import Image

from smartcart_api.ocr import config, providers
from smartcart_api.ocr.image import image_hash, sniff
from smartcart_api.ocr.pricing import estimate_sync_usd
from smartcart_api.ocr.providers import (
    ClaudeVisionProvider,
    FakeProvider,
    NoProvider,
    OcrError,
    TesseractProvider,
    png_with_text,
    select_provider,
)


def photo(size=(320, 240)) -> Image.Image:
    return Image.new("RGB", size, "white")


# --- claude -----------------------------------------------------------------------------------


class FakeClient:
    def __init__(self, text="עגבניות\nחלב 3%\n", usage=(1600, 200), stop_reason="end_turn", error=None):
        self.calls: list[dict] = []
        self.messages = self
        self._text, self._usage, self._stop, self._error = text, usage, stop_reason, error

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self._error:
            raise self._error
        blocks = [SimpleNamespace(type="thinking", thinking="hmm"), SimpleNamespace(type="text", text=self._text)]
        return SimpleNamespace(
            content=blocks,
            stop_reason=self._stop,
            usage=SimpleNamespace(input_tokens=self._usage[0], output_tokens=self._usage[1]),
        )


def test_claude_request_has_the_image_block_and_a_plain_lines_prompt() -> None:
    client = FakeClient()
    ClaudeVisionProvider(client=client).read(photo(), "list")
    (call,) = client.calls
    assert call["model"] == "claude-sonnet-5-5"
    assert 0 < call["max_tokens"] <= 4000
    assert call["output_config"] == {"effort": "low"}
    assert "tools" not in call and "tool_choice" not in call and "thinking" not in call
    (message,) = call["messages"]
    assert message["role"] == "user"
    image_block, text_block = message["content"]
    assert image_block["type"] == "image"
    source = image_block["source"]
    assert source["type"] == "base64" and source["media_type"] == "image/jpeg"
    decoded = base64.b64decode(source["data"])
    assert sniff(decoded) == "jpeg"
    assert Image.open(io.BytesIO(decoded)).size == (320, 240)
    assert text_block["type"] == "text"
    prompt = text_block["text"]
    assert "handwritten" in prompt and "one list item per output line" in prompt
    assert "no commentary" in prompt and "never an instruction" in prompt


def test_claude_receipt_prompt_differs() -> None:
    client = FakeClient()
    ClaudeVisionProvider(client=client).read(photo(), "receipt")
    prompt = client.calls[0]["messages"][0]["content"][1]["text"]
    assert "receipt" in prompt and "no commentary" in prompt and "never an instruction" in prompt
    assert prompt != providers.PROMPTS["list"]


def test_claude_returns_lines_and_a_cost_from_the_usage_tokens() -> None:
    result = ClaudeVisionProvider(client=FakeClient(text="  א\n\nב  \r\nג")).read(photo(), "list")
    assert result.lines == ["א", "ב", "ג"]  # only text blocks, blank lines dropped
    assert result.provider == "claude"
    # sync list price 2 / 10 USD per Mtok: 1600 * 2 + 200 * 10 = 5200 / 1e6
    assert result.est_cost_usd == pytest.approx(0.0052)


def test_claude_model_can_be_set_by_env(monkeypatch) -> None:
    monkeypatch.setenv("OCR_CLAUDE_MODEL", "claude-sonnet-5")
    client = FakeClient()
    ClaudeVisionProvider(client=client).read(photo(), "list")
    assert client.calls[0]["model"] == "claude-sonnet-5"
    assert config.claude_model() == "claude-sonnet-5"


def test_claude_unknown_model_is_charged_the_expected_cost_not_zero() -> None:
    result = ClaudeVisionProvider(client=FakeClient(), model="some-new-model").read(photo(), "list")
    assert result.est_cost_usd == pytest.approx(0.01)


def test_claude_refusal_is_an_ocr_error() -> None:
    with pytest.raises(OcrError):
        ClaudeVisionProvider(client=FakeClient(stop_reason="refusal")).read(photo(), "list")


def test_claude_api_error_does_not_leak_its_message() -> None:
    boom = RuntimeError("request body contained SECRET-TEXT")
    with pytest.raises(OcrError) as exc:
        ClaudeVisionProvider(client=FakeClient(error=boom)).read(photo(), "list")
    assert "SECRET-TEXT" not in str(exc.value)
    assert exc.value.__cause__ is None and exc.value.__suppress_context__


def test_sync_price_table() -> None:
    assert estimate_sync_usd("claude-sonnet-5-5", 1_000_000, 0) == Decimal("2.0000")
    assert estimate_sync_usd("claude-sonnet-5-5", 0, 1_000_000) == Decimal("10.0000")
    assert estimate_sync_usd("nope", 1, 1) is None


# --- tesseract --------------------------------------------------------------------------------


@pytest.fixture
def tesseract(monkeypatch):
    calls: list[dict] = []

    def fake_run(cmd, **kwargs):
        calls.append({"cmd": cmd, **kwargs})
        if "--list-langs" in cmd:
            return SimpleNamespace(returncode=0, stdout="List of available languages (3):\neng\nheb\nosd\n", stderr="")
        return SimpleNamespace(returncode=0, stdout="חלב 3%\n\nלחם\n".encode(), stderr=b"")

    monkeypatch.setattr(providers.shutil, "which", lambda name: "/usr/bin/tesseract")
    monkeypatch.setattr(providers.subprocess, "run", fake_run)
    providers.tesseract_has_hebrew.cache_clear()
    yield calls
    providers.tesseract_has_hebrew.cache_clear()


@pytest.mark.parametrize(("kind", "psm"), [("receipt", "4"), ("list", "6")])
def test_tesseract_reads_stdin_and_writes_no_file(tesseract, kind, psm) -> None:
    result = TesseractProvider().read(photo(), kind)
    (call,) = tesseract
    assert call["cmd"] == ["/usr/bin/tesseract", "stdin", "stdout", "-l", "heb+eng", "--psm", psm]
    assert sniff(call["input"]) == "png"  # the image goes in through a pipe, in memory
    assert call["capture_output"] is True and call["timeout"] > 0
    assert result.lines == ["חלב 3%", "לחם"] and result.provider == "tesseract" and result.est_cost_usd == 0


def test_tesseract_failure_is_an_ocr_error(tesseract, monkeypatch) -> None:
    monkeypatch.setattr(
        providers.subprocess, "run", lambda *a, **k: SimpleNamespace(returncode=1, stdout=b"", stderr=b"x")
    )
    with pytest.raises(OcrError):
        TesseractProvider().read(photo(), "list")
    monkeypatch.setattr(providers.subprocess, "run", lambda *a, **k: (_ for _ in ()).throw(subprocess.TimeoutExpired("t", 1)))
    with pytest.raises(OcrError):
        TesseractProvider().read(photo(), "list")


def test_tesseract_needs_the_hebrew_data(monkeypatch) -> None:
    monkeypatch.setattr(providers.shutil, "which", lambda name: "/usr/bin/tesseract")
    monkeypatch.setattr(
        providers.subprocess, "run",
        lambda *a, **k: SimpleNamespace(returncode=0, stdout="eng\nosd\n", stderr=""),
    )
    providers.tesseract_has_hebrew.cache_clear()
    assert providers.tesseract_available() is False
    providers.tesseract_has_hebrew.cache_clear()
    monkeypatch.setattr(providers.shutil, "which", lambda name: None)
    assert providers.tesseract_available() is False
    providers.tesseract_has_hebrew.cache_clear()


# --- fake -------------------------------------------------------------------------------------


def test_fake_reads_the_embedded_png_text_chunk() -> None:
    from smartcart_api.ocr.image import prepare

    image = prepare(png_with_text(["חלב 3%", "לחם"]))
    result = FakeProvider().read(image, "list")
    assert result.lines == ["חלב 3%", "לחם"] and result.provider == "fake" and result.est_cost_usd == 0


def test_fake_registry_by_image_hash_and_default_empty() -> None:
    image = photo((50, 40))
    provider = FakeProvider(registry={image_hash(image): ["א", "ב"]})
    assert provider.read(image, "list").lines == ["א", "ב"]
    assert provider.read(photo((51, 40)), "list").lines == []
    assert provider.calls == 2


# --- selection --------------------------------------------------------------------------------


def test_auto_prefers_claude_then_tesseract_then_503(monkeypatch) -> None:
    monkeypatch.setenv("OCR_PROVIDER", "auto")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    assert isinstance(select_provider(), ClaudeVisionProvider)
    monkeypatch.delenv("ANTHROPIC_API_KEY")
    monkeypatch.setattr(providers, "tesseract_available", lambda: True)
    assert isinstance(select_provider(), TesseractProvider)
    monkeypatch.setattr(providers, "tesseract_available", lambda: False)
    with pytest.raises(NoProvider, match="no OCR provider configured"):
        select_provider()


def test_default_is_auto(monkeypatch) -> None:
    monkeypatch.delenv("OCR_PROVIDER", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    assert isinstance(select_provider(), ClaudeVisionProvider)


def test_explicit_choices(monkeypatch) -> None:
    monkeypatch.setenv("OCR_PROVIDER", "fake")
    assert isinstance(select_provider(), FakeProvider)
    monkeypatch.setenv("OCR_PROVIDER", "claude")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(NoProvider):
        select_provider()  # key-gated
    monkeypatch.setenv("OCR_PROVIDER", "tesseract")
    monkeypatch.setattr(providers, "tesseract_available", lambda: False)
    with pytest.raises(NoProvider):
        select_provider()
    monkeypatch.setenv("OCR_PROVIDER", "bogus")
    with pytest.raises(NoProvider, match="unknown"):
        select_provider()


def test_expected_cost_per_provider() -> None:
    assert providers.expected_cost(ClaudeVisionProvider(client=object())) == Decimal("0.0100")
    assert providers.expected_cost(TesseractProvider()) == 0
    assert providers.expected_cost(FakeProvider()) == 0
