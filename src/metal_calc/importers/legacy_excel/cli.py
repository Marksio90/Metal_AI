from __future__ import annotations

import argparse
import json

from .normalizer import normalize_rows
from .parser import parse_legacy_excel


def main() -> None:
    parser = argparse.ArgumentParser(description="Import and normalize legacy Excel costing files")
    parser.add_argument("input_file", help="Path to local private Excel file")
    args = parser.parse_args()

    parsed = parse_legacy_excel(args.input_file)
    normalized, issues = normalize_rows(
        source_filename=parsed["sourceFile"],
        rows=parsed["operations"],
        material_detected=parsed["materialDetected"],
        packaging_detected=parsed["packagingDetected"],
        cost_summary_detected=parsed["costSummaryDetected"],
    )

    print(
        json.dumps(
            {
                "source": parsed["sourceFile"],
                "detectedSheets": parsed["detectedSheets"],
                "records": [r.to_dict() for r in normalized],
                "validationIssues": issues,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
