"""충북 JSON 데이터 저장소.

DB 없이 파일 기반으로 동작한다. 콘텐츠 파일(experiences, artisans, card_news, heritage)은
앱 코드와 함께 배포되는 시드 데이터를 최초 1회 운영 데이터 디렉토리로 복사해 사용하고,
이후로는 운영 데이터 디렉토리(`settings.chungbuk_data_dir`)의 파일만 읽고 쓴다.
운영 데이터 디렉토리는 git이 추적하는 코드 폴더 밖에 둬야 `git pull` 시 덮어써지지 않는다.
"""

import json
import logging
import shutil
import threading
from pathlib import Path
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)

# 동일 프로세스 내 동시 쓰기로 인한 파일 깨짐을 막기 위한 락.
# 여러 프로세스가 같은 파일에 동시에 쓰는 경우까지는 보호하지 못하지만,
# 데모 규모의 트래픽에서는 단일 프로세스 내 락으로 충분하다.
_write_lock = threading.Lock()

# 코드와 함께 배포되는 초기 시드 데이터 위치
SEED_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "chungbuk_seed"


def _data_dir() -> Path:
    path = Path(settings.chungbuk_data_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _ensure_seeded(filename: str, default: Any) -> Path:
    target = _data_dir() / filename
    if target.exists():
        return target

    seed_file = SEED_DIR / filename
    if seed_file.exists():
        shutil.copy(seed_file, target)
        logger.info("Seeded %s from %s", target, seed_file)
    else:
        target.write_text(json.dumps(default, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("Initialized empty %s", target)
    return target


def read_json(filename: str, default: Any = None) -> Any:
    if default is None:
        default = []
    path = _ensure_seeded(filename, default)
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(filename: str, data: Any) -> None:
    path = _data_dir() / filename
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with _write_lock:
        with tmp_path.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        tmp_path.replace(path)  # 원자적 교체 - 쓰는 도중 프로세스가 죽어도 기존 파일은 보존됨


def next_id(records: list[dict]) -> int:
    if not records:
        return 1
    return max(record["id"] for record in records) + 1
