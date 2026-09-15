"""UC-0A complaint classifier."""

import argparse
import csv
from pathlib import Path

ALLOWED_CATEGORIES = [
    "Pothole",
    "Flooding",
    "Streetlight",
    "Waste",
    "Noise",
    "Road Damage",
    "Heritage Damage",
    "Heat Hazard",
    "Drain Blockage",
    "Other",
]

SEVERITY_KEYWORDS = [
    "injury",
    "child",
    "school",
    "hospital",
    "ambulance",
    "fire",
    "hazard",
    "fell",
    "collapse",
]

CATEGORY_KEYWORDS = {
    "Drain Blockage": [
        ("drain blocked", 5),
        ("blocked drain", 5),
        ("clogged drain", 5),
        ("blocked drainage", 5),
        ("storm drain blocked", 5),
        ("manhole cover missing", 5),
        ("manhole", 4),
        ("sewer overflow", 5),
        ("water not flowing", 4),
        ("drain", 2),
    ],
    "Flooding": [
        ("underpass flooded", 5),
        ("bridge floods", 5),
        ("flooded", 5),
        ("flooding", 5),
        ("flood", 4),
        ("waterlogged", 4),
        ("water logging", 4),
        ("standing in water", 4),
        ("knee-deep", 3),
        ("inundated", 3),
    ],
    "Streetlight": [
        ("streetlight", 5),
        ("street light", 5),
        ("streetlights", 5),
        ("lights out", 4),
        ("light out", 4),
        ("lamp", 4),
        ("flickering", 4),
        ("sparking", 4),
        ("dark at night", 4),
        ("electrical hazard", 5),
    ],
    "Waste": [
        ("garbage bins", 5),
        ("overflowing bins", 5),
        ("bulk waste", 5),
        ("dumped on public road", 5),
        ("garbage", 4),
        ("waste", 4),
        ("dead animal", 5),
        ("smell affecting shoppers", 3),
    ],
    "Noise": [
        ("playing music", 5),
        ("music", 4),
        ("noise", 4),
        ("loud", 3),
        ("disturbance", 3),
        ("past midnight", 3),
        ("party noise", 4),
    ],
    "Road Damage": [
        ("road surface cracked", 5),
        ("surface cracked", 5),
        ("cracked road", 5),
        ("sinking road", 5),
        ("broken tiles", 5),
        ("upturned", 4),
        ("broken footpath", 5),
        ("road damaged", 5),
        ("road crack", 5),
        ("utility work", 3),
        ("road", 1),
    ],
    "Heritage Damage": [
        ("heritage street", 5),
        ("heritage building", 5),
        ("heritage wall", 5),
        ("heritage", 4),
        ("historic", 4),
        ("monument", 4),
        ("old city", 3),
    ],
    "Heat Hazard": [
        ("heatwave", 5),
        ("extreme heat", 5),
        ("hot weather", 5),
        ("heat", 4),
        ("temperature", 3),
        ("scorching", 4),
        ("sun", 2),
    ],
    "Pothole": [
        ("large pothole", 5),
        ("deep pothole", 5),
        ("pothole", 5),
        ("pot hole", 5),
        ("tyre damage", 4),
        ("road broken", 3),
        ("cracked surface", 3),
    ],
}


def normalize_text(value: str) -> str:
    return (value or "").strip().lower()


def contains_any(text: str, keywords: list[str]) -> bool:
    normalized = normalize_text(text)
    return any(keyword in normalized for keyword in keywords)


def classify_complaint(row: dict) -> dict:
    """Classify a single complaint row based on the README enforcement rules."""
    complaint_id = row.get("complaint_id", "UNKNOWN")
    description = row.get("description", "")
    text = normalize_text(description)

    if not description or len(description.strip()) < 6:
        return {
            "complaint_id": complaint_id,
            "category": "Other",
            "priority": "Urgent" if contains_any(description, SEVERITY_KEYWORDS) else "Standard",
            "reason": "The description is too vague to classify confidently and does not mention approved category terms.",
            "flag": "NEEDS_REVIEW",
        }

    priority = "Urgent" if contains_any(description, SEVERITY_KEYWORDS) else "Standard"

    matched_category = "Other"
    matched_score = 0
    matched_evidence = ""

    for category, keyword_rules in CATEGORY_KEYWORDS.items():
        for keyword, weight in keyword_rules:
            if keyword in text and weight > matched_score:
                matched_category = category
                matched_score = weight
                matched_evidence = keyword
            elif keyword in text and weight == matched_score and matched_category == "Other":
                matched_category = category
                matched_evidence = keyword

    if matched_category == "Other":
        reason = (
            f"The description is too vague to classify confidently because it does not mention approved category terms such as 'pothole', 'flood', 'streetlight', or 'waste'."
        )
        flag = "NEEDS_REVIEW"
        return {
            "complaint_id": complaint_id,
            "category": "Other",
            "priority": priority,
            "reason": reason,
            "flag": flag,
        }

    reason = f"The description mentions '{matched_evidence}' and related terms, which matches {matched_category}."

    return {
        "complaint_id": complaint_id,
        "category": matched_category,
        "priority": priority,
        "reason": reason,
        "flag": "",
    }


def batch_classify(input_path: str, output_path: str):
    """Read input CSV, classify each valid row, and write output CSV."""
    input_file = Path(input_path)
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    rows = []
    try:
        with input_file.open("r", newline="", encoding="utf-8") as csv_file:
            reader = csv.DictReader(csv_file)
            if reader.fieldnames is None:
                raise ValueError("Input CSV is missing a header row.")
            for row_index, row in enumerate(reader, start=1):
                try:
                    if row is None:
                        raise ValueError("Empty row.")
                    rows.append(classify_complaint(row))
                except Exception as exc:  # pragma: no cover - runtime safety
                    print(f"Skipping malformed row {row_index}: {exc}", flush=True)
    except FileNotFoundError:
        raise FileNotFoundError(f"Input file not found: {input_path}")
    except Exception as exc:  # pragma: no cover - runtime safety
        raise ValueError(f"Unable to read input CSV: {exc}") from exc

    fieldnames = ["complaint_id", "category", "priority", "reason", "flag"]
    with output_file.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({
                "complaint_id": row.get("complaint_id", ""),
                "category": row.get("category", "Other"),
                "priority": row.get("priority", "Standard"),
                "reason": row.get("reason", ""),
                "flag": row.get("flag", ""),
            })


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="UC-0A Complaint Classifier")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    batch_classify(args.input, args.output)
    print(f"Done. Results written to {args.output}")
