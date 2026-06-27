"""
충청북도 관광명소정보 Open API에서 데이터를 받아와
app/data/chungbuk_seed/chungbuk_tourist_spots.json 에 "관광명소" 항목으로 추가하는 1회성 스크립트.

이 API는 별도 인증키 없이 호출 가능하다 (apis.data.go.kr이 아니라 충북 자체 도메인).
이미 있는 전통시장(category=전통시장) 항목은 그대로 두고, 관광명소 항목만 새로 이어붙인다.

사용법:
    uv run python scripts/fetch_chungbuk_tourattr.py
    MAX_TOUR_ATTR_ITEMS=500 uv run python scripts/fetch_chungbuk_tourattr.py  # 개수 조절
"""

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

BASE_URL = "https://tour.chungbuk.go.kr/openapi/tourInfo/attr.do"
PAGE_UNIT = 10
# totalCount가 1737건이라 데모 규모에 맞게 기본 캡을 둔다. 필요하면 env로 늘릴 수 있다.
DEFAULT_MAX_ITEMS = 300
OUTPUT_PATH = (
    Path(__file__).resolve().parent.parent
    / "app"
    / "data"
    / "chungbuk_seed"
    / "chungbuk_tourist_spots.json"
)


def fetch_all_attractions(max_items: int) -> list[dict]:
    results: list[dict] = []
    page_index = 1

    while len(results) < max_items:
        query = urllib.parse.urlencode({"pageIndex": page_index, "pageUnit": PAGE_UNIT})
        url = f"{BASE_URL}?{query}"
        # 웹방화벽(WAF)이 기본 urllib User-Agent를 봇으로 보고 차단하는 경우가 있어 브라우저처럼 위장한다.
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept": "application/json, text/plain, */*",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                raw = response.read()
                charset = response.headers.get_content_charset()
                if charset:
                    text = raw.decode(charset)
                else:
                    # 이 API는 charset 헤더 없이 EUC-KR(CP949)로 내려주는 경우가 있어 폴백한다.
                    try:
                        text = raw.decode("utf-8")
                    except UnicodeDecodeError:
                        text = raw.decode("cp949")
                try:
                    payload = json.loads(text)
                except json.JSONDecodeError:
                    print(f"JSON 파싱 실패. 응답 원문(앞 500자):\n{text[:500]}", file=sys.stderr)
                    raise
        except urllib.error.HTTPError as error:
            body = error.read().decode("utf-8", errors="replace")
            print(f"API 호출 실패 (HTTP {error.code}): {body}", file=sys.stderr)
            raise
        except urllib.error.URLError as error:
            print(f"네트워크 에러: {error.reason}", file=sys.stderr)
            raise

        if payload.get("status") != "OK":
            raise RuntimeError(f"API error: {payload}")

        rows = payload.get("result") or []
        results.extend(rows)

        total_count = payload.get("totalCount", 0)
        if not rows or len(results) >= total_count:
            break
        page_index += 1

    return results[:max_items]


def _normalize_sigun(area_se: str | None) -> str | None:
    """
    이 API는 '청주시', '증평군'처럼 접미사가 붙어 오는데, 전통시장 데이터는 '청주'처럼
    접미사 없이 들어있다. sigun 필터가 카테고리를 넘나들며 동작하도록 맞춰준다.
    """
    if not area_se:
        return area_se
    if area_se.endswith(("시", "군", "구")) and len(area_se) > 2:
        return area_se[:-1]
    return area_se


def to_tourist_spot(record: dict, idx: int) -> dict:
    return {
        "id": idx,
        "category": "관광명소",
        "region": "충북",
        "sigun": _normalize_sigun(record.get("areaSe")),
        "name": record.get("tourNm"),
        "address": record.get("adres"),
        "established_year": None,
        "open_cycle": None,
        "market_day": None,
        "note": None,
        "lat": record.get("lat"),
        "lng": record.get("lng"),
        "tour_type": record.get("tourSe"),
        "intro": record.get("intrcn"),
        "image_url": record.get("tourImg"),
        "hours": record.get("operTime"),
        "tel": record.get("telno"),
        "url": record.get("tourUrl"),
    }


def main() -> None:
    max_items = int(os.environ.get("MAX_TOUR_ATTR_ITEMS", DEFAULT_MAX_ITEMS))

    existing: list[dict] = []
    if OUTPUT_PATH.exists():
        existing = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
        # 기존에 받아둔 관광명소 데이터가 있으면 중복으로 또 쌓이지 않게 제거하고 새로 받은 걸로 교체
        existing = [item for item in existing if item.get("category") != "관광명소"]

    attractions = fetch_all_attractions(max_items)
    next_id = (max((item["id"] for item in existing), default=0)) + 1
    spots = [to_tourist_spot(record, next_id + i) for i, record in enumerate(attractions)]

    combined = existing + spots

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(combined, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"관광명소 {len(spots)}건 추가, 전체 {len(combined)}건 저장 완료: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
