"""
AI-powered RFQ field extractor using Claude Haiku (cheapest Anthropic model).

Extracts structured fields from free-text or OCR-ed RFQ documents:
    product_family, material_grade, quantity, finish, dimensions, etc.

Requires the optional 'ai' dependency:
    pip install metal-calc[ai]
    or
    pip install anthropic>=0.40

Usage:
    from metal_calc.ai.extractor import RFQExtractor

    extractor = RFQExtractor()                       # uses ANTHROPIC_API_KEY env var
    result = extractor.extract(rfq_text)
    print(result.fields)      # dict of extracted fields
    print(result.confidence)  # "high" / "medium" / "low"
    print(result.raw_reply)   # full model output for debugging

Cost estimate (claude-haiku-4-5):
    ~500 tokens in + ~200 tokens out ≈ $0.0014 per RFQ document
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# Lazy import — anthropic is optional
# ---------------------------------------------------------------------------

def _get_anthropic():
    try:
        import anthropic
        return anthropic
    except ImportError as exc:
        raise ImportError(
            "The 'anthropic' package is required for AI extraction. "
            "Install it with:  pip install metal-calc[ai]"
        ) from exc


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass
class ExtractionResult:
    """Result of one RFQ extraction call."""
    fields: dict[str, Any]           # extracted field→value pairs (None if not found)
    confidence: str                   # "high" | "medium" | "low"
    missing_fields: list[str]        # fields the model could not find
    assumptions: list[str]           # fields the model had to guess
    raw_reply: str                   # full model text output (for debugging)
    model: str = "claude-haiku-4-5"

    @property
    def is_complete(self) -> bool:
        """True when all critical common fields were extracted."""
        critical = {"client", "quantity", "product_family",
                    "material_family", "material_grade", "finish"}
        return all(self.fields.get(f) for f in critical)


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
Jesteś ekspertem od analizy zapytań ofertowych (RFQ) dla polskiej firmy metalowej.
Twoim zadaniem jest wyekstrahowanie ustrukturyzowanych pól z tekstu RFQ.

Firma produkuje:
- DRUT (drut): elementy z drutu stalowego (giętarki, zgrzewarki)
- BLACHA (blacha): elementy z blach stalowych (laser, gięcie, wykrawanie)
- RURA_PROFIL (rura_profil): elementy rurowe i profilowe (cięcie, gięcie)
- SIATKA (siatka): siatki zgrzewane z drutu
- KONSTRUKCJA (konstrukcja): konstrukcje spawane i zmontowane

Wyodrębnij poniższe pola i zwróć WYŁĄCZNIE poprawny JSON.
Jeśli pole nie jest wymienione w RFQ — ustaw wartość null.
Nie dodawaj wyjaśnień poza JSON.

Pola do wyodrębnienia:
{
  "client": null,                    // nazwa klienta lub firmy
  "quantity": null,                  // ilość sztuk (liczba całkowita)
  "product_family": null,            // jeden z: drut, blacha, rura_profil, siatka, konstrukcja
  "material_family": null,           // np. "stal_węglowa", "stal_nierdzewna", "aluminium"
  "material_grade": null,            // np. "S235JR", "S355", "DC01", "304"
  "finish": null,                    // np. "surowe", "ocynkowane", "malowane_proszkowo", "polerowane"
  "wire_diameter_mm": null,          // [drut/siatka] średnica drutu w mm
  "thickness_mm": null,              // [blacha] grubość blachy w mm
  "tube_od_mm": null,               // [rura] zewnętrzna średnica rury w mm
  "wall_thickness_mm": null,         // [rura] grubość ścianki w mm
  "length_mm": null,                 // [rura] długość odcinka w mm
  "mesh_width_mm": null,             // [siatka] szerokość oczka w mm
  "mesh_height_mm": null,            // [siatka] wysokość oczka w mm
  "unit_mass_kg": null,              // masa jednostkowa wyrobu w kg/szt.
  "drawing_reference": null,         // numer rysunku lub symbol
  "delivery_date_requested": null,   // oczekiwany termin dostawy (ISO data jeśli możliwe)
  "salesperson": null,               // handlowiec (jeśli podany)
  "rfq_subject": null,               // temat / tytuł zapytania
  "confidence": null,                // "high" | "medium" | "low" — Twoja ocena pewności
  "missing_fields": [],              // lista pól których NIE znalazłeś
  "assumptions": []                  // lista pól które zgadłeś / założyłeś (nie wynikają wprost z tekstu)
}
"""


# ---------------------------------------------------------------------------
# Extractor
# ---------------------------------------------------------------------------

class RFQExtractor:
    """
    Extracts RFQ fields from free text using Claude Haiku.

    Args:
        api_key: Anthropic API key. Defaults to ANTHROPIC_API_KEY env var.
        model:   Model ID to use. Defaults to claude-haiku-4-5 (cheapest).
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "claude-haiku-4-5",
    ) -> None:
        self._model = model
        self._api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self._client = None  # lazy-initialized

    def _get_client(self):
        if self._client is None:
            anthropic = _get_anthropic()
            self._client = anthropic.Anthropic(api_key=self._api_key)
        return self._client

    def extract(self, rfq_text: str) -> ExtractionResult:
        """
        Extract structured fields from an RFQ text.

        Args:
            rfq_text: Free-text RFQ content (email body, OCR output, etc.)

        Returns:
            ExtractionResult with .fields dict and metadata.
        """
        client = self._get_client()

        response = client.messages.create(
            model=self._model,
            max_tokens=512,
            system=_SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": (
                        "Wyodrębnij pola z poniższego RFQ:\n\n"
                        f"{rfq_text}\n\n"
                        "Zwróć WYŁĄCZNIE poprawny JSON bez żadnego tekstu przed lub po."
                    ),
                }
            ],
        )

        raw = response.content[0].text.strip()
        return self._parse_response(raw)

    def _parse_response(self, raw: str) -> ExtractionResult:
        """Parse JSON response from the model into ExtractionResult."""
        # Strip markdown code fences if present
        text = raw
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(
                line for line in lines
                if not line.startswith("```")
            ).strip()

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            # Return a low-confidence result if JSON is malformed
            return ExtractionResult(
                fields={},
                confidence="low",
                missing_fields=[],
                assumptions=[],
                raw_reply=raw,
            )

        confidence = data.pop("confidence", "low") or "low"
        missing = data.pop("missing_fields", []) or []
        assumptions = data.pop("assumptions", []) or []

        return ExtractionResult(
            fields=data,
            confidence=confidence,
            missing_fields=missing,
            assumptions=assumptions,
            raw_reply=raw,
            model=self._model,
        )


# ---------------------------------------------------------------------------
# Convenience function
# ---------------------------------------------------------------------------

def extract_rfq_fields(
    rfq_text: str,
    api_key: str | None = None,
    model: str = "claude-haiku-4-5",
) -> ExtractionResult:
    """
    One-shot helper: create extractor and run extraction.

    Example:
        result = extract_rfq_fields(email_body)
        if result.is_complete:
            # proceed to CalcForm
            pass
        else:
            print("Missing:", result.missing_fields)
    """
    return RFQExtractor(api_key=api_key, model=model).extract(rfq_text)
