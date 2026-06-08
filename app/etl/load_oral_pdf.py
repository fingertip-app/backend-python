"""
구술 자서전 PDF 자동 추출 및 heritage_items 적재 스크립트

지원 구조:
    A. [전자책]001~011, 013~020: [N] {이름}의 생애 / [N] {이름} 연보
    B. [전자책]021~034: {이름}의 생애 / {이름}이 걸어온 길 (섹션 번호 없음)
    C. [전자책]012: 전각 괄호 〔〕 구조

사용법:
    python -m app.etl.load_oral_pdf --file ~/Downloads/구술자서전/[전자책]001-갓일\ 김인.pdf
    python -m app.etl.load_oral_pdf --dir ~/Downloads/구술자서전
"""

import argparse
import re
from pathlib import Path

import pdfplumber

from app.db.models import HeritageItem
from app.db.session import SessionLocal

SOURCE = "iha.go.kr"
MIN_TEXT_LENGTH = 50


def extract_text_pages(pdf_path: Path) -> list[str]:
    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            pages.append(text.strip())
    return pages


def parse_cover(pages: list[str], pdf_path: Path) -> tuple[str, str]:
    """표지(페이지2)에서 이름/종목 추출. 실패 시 파일명 fallback."""
    cover = pages[1] if len(pages) > 1 else ""

    # 종목: 전각/반각 괄호 모두 처리
    category_match = re.search(r'[\[〔]?제\d+호\s+(.+?)[\]〕\n]', cover)
    category = category_match.group(1).strip() if category_match else ""

    # 이름: 한글 이름 + 전각/반각 한자 괄호 패턴
    name_match = re.search(r'([가-힣]{1,2}[^\S\n]?[가-힣]{1,2})[^\S\n]*[\[〔][\u4e00-\u9fff]', cover)
    if name_match:
        name = re.sub(r'\s+', '', name_match.group(1))
    else:
        # fallback: 파일명에서 공백 뒤 이름 추출 ('종목명 이름_숫자' 패턴)
        name_match2 = re.search(r'\s([가-힣]{2,4})(?:[_\d]|$)', pdf_path.stem)
        name = name_match2.group(1) if name_match2 else ""

    return name, category


def find_section_last(pages: list[str], pattern: str, stop_patterns: list[str]) -> str:
    """패턴 매칭 페이지 중 마지막(실제 본문)에서 stop_patterns까지 수집."""
    match_indices = [
        i for i, text in enumerate(pages)
        if text and len(text) >= MIN_TEXT_LENGTH and re.search(pattern, text)
    ]

    if not match_indices:
        return ""

    start_idx = match_indices[-1]
    collected = []

    for text in pages[start_idx:]:
        if not text or len(text) < MIN_TEXT_LENGTH:
            continue
        if collected:
            # 기본 종료 조건
            if any(re.search(p, text) for p in stop_patterns):
                break
            # 챕터 타이틀 페이지: 짧고 숫자로 시작 (021~034 시리즈)
            if len(text) < 300 and re.match(r'^\d+\n', text):
                break
        if not collected:
            match = re.search(pattern, text)
            collected.append(text[match.start():] if match else text)
        else:
            collected.append(text)

    return "\n".join(collected).strip()


def clean_text(text: str) -> str:
    lines = text.splitlines()
    cleaned = []
    prev = ""
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if re.match(r'국가무형문화재 전승자 구술 자서전 [〔\[]\d+[〕\]]', line):
            continue
        if line == prev:
            continue
        cleaned.append(line)
        prev = line
    return "\n".join(cleaned)


def extract_from_pdf(pdf_path: Path) -> dict | None:
    try:
        pages = extract_text_pages(pdf_path)
    except Exception as e:
        print(f"  PDF 읽기 실패: {e}")
        return None

    name, category = parse_cover(pages, pdf_path)
    if not name:
        print(f"  ⚠️  이름 추출 실패: {pdf_path.name}")
        return None

    name_esc = re.escape(name)

    # 생애 섹션
    desc_raw = (
        # A/C 타입: [N] {이름}의 생애
        find_section_last(
            pages,
            rf'[\[〔]\d+[\]〕]\s*{name_esc}의\s*생애',
            [r'[\[〔]\d+[\]〕]\s*(조사자|주석|참고|채록)']
        )
        # B 타입: {이름}의 생애 (섹션 번호 없음)
        or find_section_last(
            pages,
            rf'{name_esc}의\s*생애',
            [
                r'[\[〔]\d+[\]〕]\s*(조사자|주석|참고|채록)',
                rf'{name_esc}이\s*걸어온\s*길',
                r'^(조사자|주석|참고)',
            ]
        )
    )

    # 연보 섹션
    hist_raw = (
        # A/C 타입: [N] {이름} 연보
        find_section_last(
            pages,
            rf'[\[〔]\d+[\]〕]\s*{name_esc}\s*연보',
            [r'[\[〔]\d+[\]〕]\s*(조사자|주석|참고|채록)']
        )
        # B 타입: {이름}이 걸어온 길
        or find_section_last(
            pages,
            rf'{name_esc}이\s*걸어온\s*길',
            [r'(조사자|주석|참고)', r'^\d+\n']
        )
        # 진주검무 타입: {이름}이 걸어온 길 (표 없이)
        or find_section_last(
            pages,
            rf'{name_esc}\s*연보',
            [r'(조사자|주석|참고)']
        )
    )

    description = clean_text(desc_raw) if desc_raw else None
    history = clean_text(hist_raw) if hist_raw else None

    if not description:
        print(f"  ⚠️  생애 텍스트 추출 실패: {pdf_path.name}")
        return None

    return {
        "name": name,
        "category": category,
        "description": description,
        "history": history,
        "external_id": f"oral_{name}_{category}",
    }


def load_records(records: list[dict]) -> None:
    db = SessionLocal()
    try:
        new_count, skip_count = 0, 0
        for rec in records:
            exists = db.query(HeritageItem).filter_by(external_id=rec["external_id"]).first()
            if exists:
                skip_count += 1
                print(f"  스킵 (중복): {rec['name']}")
                continue
            db.add(HeritageItem(
                source=SOURCE,
                external_id=rec["external_id"],
                name=rec["name"],
                category=rec["category"],
                description=rec["description"],
                history=rec["history"],
            ))
            new_count += 1
            has_history = "✅ 연보 포함" if rec["history"] else "⚠️  연보 없음"
            print(f"  적재: {rec['name']} ({rec['category']}) {has_history}")
        db.commit()
        print(f"\n완료: {new_count}건 적재, {skip_count}건 스킵(중복)")
    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()


def run(file_path: Path | None = None, dir_path: Path | None = None) -> None:
    pdf_files = [file_path] if file_path else sorted((dir_path or Path()).glob("*.pdf"))
    if not pdf_files:
        print("PDF 파일 없음.")
        return

    print(f"처리 대상: {len(pdf_files)}개 PDF")
    records = []

    for pdf_path in pdf_files:
        print(f"\n[{pdf_path.name}]")
        rec = extract_from_pdf(pdf_path)
        if rec:
            print(f"  추출 완료: {rec['name']} ({rec['category']})")
            print(f"  생애 {len(rec['description'])}자 / 연보 {len(rec['history']) if rec['history'] else 0}자")
            records.append(rec)

    if records:
        print(f"\n--- DB 적재 시작 ({len(records)}건) ---")
        load_records(records)
    else:
        print("적재할 항목 없음.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--file", type=Path)
    group.add_argument("--dir", type=Path)
    args = parser.parse_args()
    run(file_path=args.file, dir_path=args.dir)