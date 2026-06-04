import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass

import httpx

BASE_URL = "http://www.khs.go.kr/cha"
INTANGIBLE_KIND_CODE = "17"
REGION_CODE = "ZZ"


@dataclass
class HeritageItemRaw:
    external_id: str
    name: str
    category: str
    description: str
    source: str = "khs.go.kr"


def fetch_list(page_index: int = 1, page_unit: int = 100) -> tuple[int, list[dict]]:
    """국가무형유산 목록 조회. (총 건수, 항목 리스트) 반환."""
    resp = httpx.get(
        f"{BASE_URL}/SearchKindOpenapiList.do",
        params={
            "ccbaKdcd": INTANGIBLE_KIND_CODE,
            "ccbaCtcd": REGION_CODE,
            "ccbaCncl": "N",
            "pageUnit": page_unit,
            "pageIndex": page_index,
        },
        follow_redirects=True,
        timeout=10,
    )
    resp.raise_for_status()
    root = ET.fromstring(resp.text)

    total = int(root.findtext("totalCnt") or 0)
    items = []
    for item in root.findall("item"):
        items.append({
            "ccbaKdcd": item.findtext("ccbaKdcd", "").strip(),
            "ccbaAsno": item.findtext("ccbaAsno", "").strip(),
            "ccbaCtcd": item.findtext("ccbaCtcd", "").strip(),
            "name": item.findtext("ccbaMnm1", "").strip(),
        })
    return total, items


def fetch_detail(ccba_kdcd: str, ccba_asno: str, ccba_ctcd: str, retries: int = 3) -> HeritageItemRaw | None:
    """국가무형유산 상세 조회. 실패 시 최대 retries회 재시도."""
    for attempt in range(1, retries + 1):
        try:
            resp = httpx.get(
                f"{BASE_URL}/SearchKindOpenapiDt.do",
                params={
                    "ccbaKdcd": ccba_kdcd,
                    "ccbaAsno": ccba_asno,
                    "ccbaCtcd": ccba_ctcd,
                },
                follow_redirects=True,
                timeout=15,
            )
            resp.raise_for_status()
            root = ET.fromstring(resp.text)
            item = root.find("item")
            if item is None:
                return None

            name = item.findtext("ccbaMnm1", "").strip()
            description = item.findtext("content", "").strip()
            category = item.findtext("bcodeName", "").strip()
            external_id = f"{ccba_kdcd}_{ccba_asno}_{ccba_ctcd}"

            if not name or not description:
                return None

            return HeritageItemRaw(
                external_id=external_id,
                name=name,
                category=category,
                description=description,
            )
        except (httpx.ConnectError, httpx.TimeoutException) as e:
            print(f"  재시도 {attempt}/{retries}: {e}")
            time.sleep(2 * attempt)

    return None


def fetch_all(delay: float = 1.0) -> list[HeritageItemRaw]:
    """전체 국가무형유산 수집. delay는 API 과호출 방지용 대기 시간(초)."""
    total, first_page = fetch_list(page_index=1, page_unit=100)
    print(f"총 {total}건 수집 시작")

    all_items = first_page
    page = 2
    while len(all_items) < total:
        _, items = fetch_list(page_index=page, page_unit=100)
        if not items:
            break
        all_items.extend(items)
        page += 1

    results = []
    for i, meta in enumerate(all_items, 1):
        detail = fetch_detail(meta["ccbaKdcd"], meta["ccbaAsno"], meta["ccbaCtcd"])
        if detail:
            results.append(detail)
            print(f"[{i}/{len(all_items)}] {detail.name} 수집 완료")
        else:
            print(f"[{i}/{len(all_items)}] 스킵 (본문 없음 또는 실패)")
        time.sleep(delay)

    return results
