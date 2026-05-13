"""
Tests for metal_calc.ai.extractor — RFQ field extractor.

API calls are mocked; no real Anthropic key is required.
Tests cover: JSON parsing, confidence handling, missing/malformed responses,
ExtractionResult properties, and the lazy-import guard.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from metal_calc.ai.extractor import ExtractionResult, RFQExtractor, extract_rfq_fields


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_response_json(**kwargs) -> str:
    """Build a valid JSON response the way the model would return it."""
    defaults = {
        "client": None,
        "quantity": None,
        "product_family": None,
        "material_family": None,
        "material_grade": None,
        "finish": None,
        "wire_diameter_mm": None,
        "thickness_mm": None,
        "tube_od_mm": None,
        "wall_thickness_mm": None,
        "length_mm": None,
        "mesh_width_mm": None,
        "mesh_height_mm": None,
        "unit_mass_kg": None,
        "drawing_reference": None,
        "delivery_date_requested": None,
        "salesperson": None,
        "rfq_subject": None,
        "confidence": "high",
        "missing_fields": [],
        "assumptions": [],
    }
    defaults.update(kwargs)
    return json.dumps(defaults)


def _mock_extractor(json_reply: str) -> RFQExtractor:
    """Return an RFQExtractor whose _get_client is replaced by a mock."""
    extractor = RFQExtractor(api_key="test-key")
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=json_reply)]
    mock_client.messages.create.return_value = mock_response
    extractor._client = mock_client
    return extractor


# ---------------------------------------------------------------------------
# ExtractionResult — properties
# ---------------------------------------------------------------------------

class TestExtractionResult:
    def test_is_complete_all_critical_present(self):
        result = ExtractionResult(
            fields={
                "client": "ACME Sp. z o.o.",
                "quantity": 1000,
                "product_family": "drut",
                "material_family": "stal_węglowa",
                "material_grade": "S235JR",
                "finish": "surowe",
            },
            confidence="high",
            missing_fields=[],
            assumptions=[],
            raw_reply="",
        )
        assert result.is_complete is True

    def test_is_complete_missing_critical_field(self):
        result = ExtractionResult(
            fields={
                "client": "ACME",
                "quantity": 500,
                "product_family": "drut",
                "material_family": "stal_węglowa",
                "material_grade": None,   # missing
                "finish": "surowe",
            },
            confidence="medium",
            missing_fields=["material_grade"],
            assumptions=[],
            raw_reply="",
        )
        assert result.is_complete is False

    def test_default_model_label(self):
        result = ExtractionResult(
            fields={}, confidence="low",
            missing_fields=[], assumptions=[], raw_reply="",
        )
        assert result.model == "claude-haiku-4-5"


# ---------------------------------------------------------------------------
# RFQExtractor._parse_response — JSON parsing
# ---------------------------------------------------------------------------

class TestParseResponse:
    def _extractor(self) -> RFQExtractor:
        e = RFQExtractor(api_key="test")
        e._client = MagicMock()  # prevent real API calls
        return e

    def test_valid_json_parsed(self):
        e = self._extractor()
        raw = _make_response_json(
            client="Beta Metal S.A.",
            quantity=500,
            product_family="drut",
            material_grade="S235JR",
            material_family="stal_węglowa",
            finish="surowe",
            confidence="high",
        )
        result = e._parse_response(raw)
        assert result.fields["client"] == "Beta Metal S.A."
        assert result.fields["quantity"] == 500
        assert result.confidence == "high"
        assert result.missing_fields == []

    def test_missing_fields_extracted(self):
        e = self._extractor()
        raw = _make_response_json(
            product_family="blacha",
            confidence="medium",
            missing_fields=["thickness_mm", "unit_mass_kg"],
        )
        result = e._parse_response(raw)
        assert "thickness_mm" in result.missing_fields
        assert "unit_mass_kg" in result.missing_fields

    def test_assumptions_extracted(self):
        e = self._extractor()
        raw = _make_response_json(
            finish="surowe",
            confidence="medium",
            assumptions=["finish"],
        )
        result = e._parse_response(raw)
        assert "finish" in result.assumptions

    def test_malformed_json_returns_low_confidence(self):
        e = self._extractor()
        result = e._parse_response("Nie mogę wyodrębnić pól — brak danych.")
        assert result.confidence == "low"
        assert result.fields == {}

    def test_markdown_code_fence_stripped(self):
        e = self._extractor()
        fenced = "```json\n" + _make_response_json(client="Klient A") + "\n```"
        result = e._parse_response(fenced)
        assert result.fields["client"] == "Klient A"

    def test_null_confidence_defaults_to_low(self):
        e = self._extractor()
        raw = _make_response_json(confidence=None)
        result = e._parse_response(raw)
        assert result.confidence == "low"

    def test_raw_reply_preserved(self):
        e = self._extractor()
        raw = _make_response_json()
        result = e._parse_response(raw)
        assert result.raw_reply == raw


# ---------------------------------------------------------------------------
# RFQExtractor.extract — mocked API calls
# ---------------------------------------------------------------------------

class TestRFQExtractorMocked:
    RFQ_TEXT = """\
Dzień dobry,

Proszę o wycenę drutu stalowego S235JR, fi5mm, ilość 2000 szt., wykończenie: surowe.
Klient: Alfa Produkcja Sp. z o.o.
Termin: 2025-06-30.
"""

    def test_extract_returns_result(self):
        json_reply = _make_response_json(
            client="Alfa Produkcja Sp. z o.o.",
            quantity=2000,
            product_family="drut",
            material_family="stal_węglowa",
            material_grade="S235JR",
            finish="surowe",
            wire_diameter_mm=5.0,
            delivery_date_requested="2025-06-30",
            confidence="high",
        )
        extractor = _mock_extractor(json_reply)
        result = extractor.extract(self.RFQ_TEXT)
        assert isinstance(result, ExtractionResult)
        assert result.fields["client"] == "Alfa Produkcja Sp. z o.o."
        assert result.fields["quantity"] == 2000
        assert result.fields["product_family"] == "drut"
        assert result.fields["wire_diameter_mm"] == 5.0
        assert result.confidence == "high"
        assert result.is_complete is True

    def test_extract_calls_model_with_rfq_text(self):
        extractor = _mock_extractor(_make_response_json())
        extractor.extract("Przykładowe RFQ")
        call_args = extractor._client.messages.create.call_args
        messages = call_args.kwargs.get("messages", call_args.args[0] if call_args.args else [])
        if isinstance(messages, list):
            user_content = next(
                (m["content"] for m in messages if m.get("role") == "user"), ""
            )
        else:
            user_content = ""
        assert "Przykładowe RFQ" in user_content

    def test_extract_uses_configured_model(self):
        extractor = _mock_extractor(_make_response_json())
        extractor._model = "claude-haiku-4-5"
        extractor.extract("RFQ")
        call_kwargs = extractor._client.messages.create.call_args.kwargs
        assert call_kwargs["model"] == "claude-haiku-4-5"

    def test_result_model_attribute(self):
        extractor = _mock_extractor(_make_response_json(confidence="high"))
        extractor._model = "claude-haiku-4-5"
        result = extractor.extract("RFQ")
        assert result.model == "claude-haiku-4-5"

    def test_incomplete_rfq_detected(self):
        json_reply = _make_response_json(
            product_family="blacha",
            quantity=None,
            material_grade=None,
            client=None,
            material_family=None,
            finish=None,
            confidence="low",
            missing_fields=["client", "quantity", "material_grade", "material_family", "finish"],
        )
        extractor = _mock_extractor(json_reply)
        result = extractor.extract("Potrzebujemy blachę.")
        assert result.is_complete is False
        assert len(result.missing_fields) > 0


# ---------------------------------------------------------------------------
# extract_rfq_fields convenience function
# ---------------------------------------------------------------------------

class TestExtractRFQFieldsFunction:
    def test_convenience_function_returns_result(self):
        json_reply = _make_response_json(
            client="Test", quantity=100,
            product_family="drut",
            material_family="stal_węglowa",
            material_grade="S235JR",
            finish="surowe",
            confidence="high",
        )
        with patch("metal_calc.ai.extractor.RFQExtractor.extract") as mock_extract:
            mock_extract.return_value = ExtractionResult(
                fields={"client": "Test"},
                confidence="high",
                missing_fields=[],
                assumptions=[],
                raw_reply=json_reply,
            )
            result = extract_rfq_fields("RFQ text", api_key="key")
        assert result.fields["client"] == "Test"


# ---------------------------------------------------------------------------
# Missing anthropic package guard
# ---------------------------------------------------------------------------

class TestMissingAnthropicPackage:
    def test_import_error_raised_when_anthropic_missing(self):
        import builtins
        real_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "anthropic":
                raise ImportError("No module named 'anthropic'")
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            from metal_calc.ai import extractor as ext_mod
            with pytest.raises(ImportError, match="anthropic"):
                ext_mod._get_anthropic()
