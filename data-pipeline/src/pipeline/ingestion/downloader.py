import hashlib
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote, unquote, urlparse

import httpx
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

from pipeline.config import settings


@dataclass
class DownloadResult:
    url: str
    filename: str
    bronze_path: Path
    checksum_sha256: str
    size_bytes: int
    etag: str | None
    last_modified: str | None


def _safe_url(url: str) -> str:
    """Кодирует кириллицу и пробелы в URL, не ломая схему и слэши."""
    parts = urlparse(url)
    encoded_path = quote(unquote(parts.path), safe="/")
    return parts._replace(path=encoded_path).geturl()


def _filename_from_url(url: str) -> str:
    """Достаёт имя файла из URL, декодирует кириллицу."""
    path = urlparse(url).path
    name = unquote(Path(path).name)
    if not name:
        raise ValueError(f"Не удалось определить имя файла из URL: {url}")
    return name


def _sha256_of_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            h.update(chunk)
    return h.hexdigest()


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True,
)
def _head(url: str) -> httpx.Response:
    """HEAD-запрос, чтобы узнать ETag и Last-Modified до скачивания."""
    with httpx.Client(timeout=30.0, follow_redirects=True) as client:
        return client.head(url)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True,
)
def _get_stream(url: str, dest: Path) -> httpx.Response:
    """Скачивает файл потоком, чтобы не держать в памяти целиком."""
    with httpx.Client(timeout=60.0, follow_redirects=True) as client:
        with client.stream("GET", url) as response:
            response.raise_for_status()
            dest.parent.mkdir(parents=True, exist_ok=True)
            with dest.open("wb") as f:
                for chunk in response.iter_bytes(chunk_size=1024 * 64):
                    f.write(chunk)
        return response


def download(
    url: str,
    source: str,
    dataset: str,
    period: str | None = None,
) -> DownloadResult:
    """
    Скачивает файл в Bronze и возвращает метаданные.

    Путь: data/bronze/{source}/{dataset}/{period}/{filename}
    """
    safe_url = _safe_url(url)
    filename = _filename_from_url(url)

    # Куда кладём
    folder = settings.bronze_dir / source / dataset
    if period:
        folder = folder / period
    dest = folder / filename

    # HEAD — узнаём ETag / Last-Modified, но не падаем, если сервер не отдаёт
    etag = None
    last_modified = None
    try:
        head = _head(safe_url)
        etag = head.headers.get("ETag")
        last_modified = head.headers.get("Last-Modified")
    except Exception as e:
        logger.warning(f"HEAD не удался для {safe_url}: {e}. Продолжаем без ETag.")

    # Если файл уже есть — не качаем повторно
    if dest.exists():
        logger.info(f"Файл уже есть: {dest}")
        checksum = _sha256_of_file(dest)
        return DownloadResult(
            url=url,
            filename=filename,
            bronze_path=dest,
            checksum_sha256=checksum,
            size_bytes=dest.stat().st_size,
            etag=etag,
            last_modified=last_modified,
        )

    logger.info(f"Скачиваем: {safe_url}")
    _get_stream(safe_url, dest)

    checksum = _sha256_of_file(dest)
    size = dest.stat().st_size
    logger.success(f"Сохранено: {dest} ({size} байт, sha256={checksum[:12]}…)")

    return DownloadResult(
        url=url,
        filename=filename,
        bronze_path=dest,
        checksum_sha256=checksum,
        size_bytes=size,
        etag=etag,
        last_modified=last_modified,
    )