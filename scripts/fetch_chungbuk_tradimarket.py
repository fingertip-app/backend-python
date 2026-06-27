"""
충청북도 전통시장 현황 Open API에서 데이터를 받아와
app/data/chungbuk_seed/chungbuk_tourist_spots.json 으로 저장하는 1회성 스크립트.

사용법 (둘 중 하나):
    1) .env에 TRADI_MARKET_SERVICE_KEY=<디코딩 인증키> 추가 후: uv run python scripts/fetch_chungbuk_tradimarket.py
    2) TRADI_MARKET_SERVICE_KEY="<디코딩 인증키>" uv run python scripts/fetch_chungbuk_tradimarket.py

API 문서: OpenAPI활용가이드_[충청북도_전통시장 현황]_v1.0.docx
"""

import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://apis.data.go.kr/6430000/tradiMarketStatService/getTradiMarketStat"
PER_PAGE = 100
OUTPUT_PATH = (
    Path(__file__).resolve().parent.parent
    / "app"
    / "data"
    / "chungbuk_seed"
    / "chungbuk_tourist_spots.json"
)

# API 응답 필드명(영문) -> 우리 JSON 필드명. API 스펙이 바뀌면 여기만 고치면 됨.
FIELD_MAPPING = {
    "SIGUN": "sigun",
    "MRKT_ND_SOPSTR": "name",
    "MRKT_ADRES": "address",
    "ESTBL_YEAR": "established_year",
    "ESTBL_CYCLE": "open_cycle",
    "MRKT_DE": "market_day",
    "RM": "note",
}


def fetch_all_markets(service_key: str) -> list[dict]:
    results: list[dict] = []
    page = 1

    while True:
        query = urllib.parse.urlencode(
            {"serviceKey": service_key, "currentPage": page, "perPage": PER_PAGE}
        )
        url = f"{BASE_URL}?{query}"
        try:
            with urllib.request.urlopen(url, timeout=10) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            body = error.read().decode("utf-8", errors="replace")
            print(f"API 호출 실패 (HTTP {error.code}): {body}", file=sys.stderr)
            raise
        except urllib.error.URLError as error:
            print(f"네트워크 에러: {error.reason}", file=sys.stderr)
            raise

        header = payload.get("header", {})
        if header.get("resultCode") != "00":
            raise RuntimeError(f"API error: {header}")

        body_rows = payload.get("body") or []
        results.extend(body_rows)

        total_rows = header.get("totalRows", 0)
        if len(results) >= total_rows or not body_rows:
            break
        page += 1

    return results


def to_tourist_spot(record: dict, idx: int) -> dict:
    return {
        "id": idx,
        "category": "전통시장",
        "region": "충북",
        **{json_key: record.get(api_key) for api_key, json_key in FIELD_MAPPING.items()},
    }


def main() -> None:
    service_key = os.environ.get("TRADI_MARKET_SERVICE_KEY")
    if not service_key:
        print("환경변수 TRADI_MARKET_SERVICE_KEY 가 설정되지 않았습니다.", file=sys.stderr)
        sys.exit(1)

    markets = fetch_all_markets(service_key)
    spots = [to_tourist_spot(record, idx + 1) for idx, record in enumerate(markets)]

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(spots, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{len(spots)}건 저장 완료: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
