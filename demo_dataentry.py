#!/usr/bin/env python3
"""Send demo data to the /dataentry endpoint for local testing.

Examples:
    python demo_dataentry.py
    python demo_dataentry.py --url http://127.0.0.1:8000/dataentry
    python demo_dataentry.py --print-only
"""

import argparse
import json
import os
import sys
from typing import Any

import requests


def build_demo_payload() -> list[dict[str, Any]]:
    return [
        {
            "Larus Labs": {
                "email": "ops@laruslabs.com",
                "candidates": [
                    {
                        "name": "Amina Hassan",
                        "age": 24,
                        "email": "60302700@udst.edu.qa",
                        "cv": "https://example.com/cv/amina-hassan.pdf",
                        "phone": "+974 508 27742",
                        "major": "Computer Science",
                        "university": "Qatar University",
                        "linkedin": "https://www.linkedin.com/in/aminahassan",
                    },
                    {
                        "name": "Noor Al-Sayed",
                        "age": 23,
                        "email": "60302700@udst.edu.qa",
                        "cv": "https://example.com/cv/noor-al-sayed.pdf",
                        "phone": "+974 501 22334",
                        "major": "Software Engineering",
                        "university": "HBKU",
                        "linkedin": "https://www.linkedin.com/in/nooral-sayed",
                    },
                ],
            }
        },
        {
            "Northstar AI": {
                "email": "talent@northstar.ai",
                "candidates": [
                    {
                        "name": "Khalid Rahman",
                        "age": 27,
                        "email": "60302700@udst.edu.qa",
                        "cv": "https://example.com/cv/khalid-rahman.pdf",
                        "phone": "+974 555 11223",
                        "major": "Data Science",
                        "university": "Carnegie Mellon University",
                        "linkedin": "https://www.linkedin.com/in/khalidrahman",
                    }
                ],
            }
        },
    ]


def send_payload(url: str, payload: list[dict[str, Any]]) -> requests.Response:
    print(f"Sending payload to {url}...")
    response = requests.post(url, json=payload)
    print(f"Status: {response.status_code}")
    try:
        print(json.dumps(response.json(), indent=2))
    except ValueError:
        print(response.text)
    return response


def main() -> int:
    parser = argparse.ArgumentParser(description="Send demo data to the /dataentry endpoint")
    parser.add_argument(
        "--url",
        default=os.getenv("DATAENTRY_URL", "http://127.0.0.1:8000/dataentry"),
        help="Endpoint URL to post to",
    )
    parser.add_argument(
        "--print-only",
        action="store_true",
        help="Print the demo payload and exit without sending it",
    )
    args = parser.parse_args()

    payload = build_demo_payload()

    if args.print_only:
        print(json.dumps(payload, indent=2))
        return 0

    response = send_payload(args.url, payload)
    return 0 if response.ok else 1


if __name__ == "__main__":
    sys.exit(main())
