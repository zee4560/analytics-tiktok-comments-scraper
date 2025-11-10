import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

# Ensure local imports work when running as a script
CURRENT_DIR = Path(__file__).parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from extractors.tiktok_comment_parser import TikTokCommentScraper
from outputs.exporters import Exporter
from extractors.utils_datetime import now_utc_iso

def load_settings() -> Dict[str, Any]:
    """
    Loads settings from src/config/settings.example.json if present,
    otherwise provides sensible defaults.
    """
    default_settings = {
        "comment_limit": 100,
        "concurrency": 8,
        "proxy": None,  # e.g. "http://user:pass@host:port"
        "timeout_seconds": 25,
        "output_dir": str((CURRENT_DIR.parent / "data").resolve()),
        "output_format": "json",  # json or csv
    }
    example_path = CURRENT_DIR / "config" / "settings.example.json"
    try:
        if example_path.exists():
            with open(example_path, "r", encoding="utf-8") as f:
                user_settings = json.load(f)
            default_settings.update({k: v for k, v in user_settings.items() if v is not None})
    except Exception as e:
        logging.warning("Failed to load settings.example.json, using defaults: %s", e)
    return default_settings

def load_urls(filepath: Path) -> List[str]:
    if not filepath.exists():
        raise FileNotFoundError(f"Input URLs file not found: {filepath}")
    urls = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            urls.append(line)
    if not urls:
        raise ValueError("No URLs found in input file.")
    return urls

async def scrape_all(
    urls: List[str],
    comment_limit: int,
    concurrency: int,
    proxy: Optional[str],
    timeout_seconds: int,
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Scrape comments for each TikTok video URL concurrently.
    Returns a dict keyed by video URL -> list of comment dicts.
    """
    scraper = TikTokCommentScraper(
        comment_limit=comment_limit,
        proxy=proxy,
        timeout_seconds=timeout_seconds,
    )
    sem = asyncio.Semaphore(max(1, concurrency))
    results: Dict[str, List[Dict[str, Any]]] = {}

    async def run_one(url: str):
        async with sem:
            try:
                comments = await scraper.fetch_comments(url)
                results[url] = comments
                logging.info("Fetched %d comments for %s", len(comments), url)
            except Exception as e:
                logging.exception("Failed to fetch comments for %s: %s", url, e)
                results[url] = []

    await asyncio.gather(*(run_one(u) for u in urls))
    await scraper.close()
    return results

def ensure_output_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)

def main():
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s | %(levelname)-8s | %(message)s",
    )
    settings = load_settings()

    # Resolve paths
    repo_root = CURRENT_DIR.parent
    data_dir = repo_root / "data"
    input_file = data_dir / "input_urls.txt"
    ensure_output_dir(data_dir)

    try:
        urls = load_urls(input_file)
    except Exception as e:
        logging.error("Error loading input URLs: %s", e)
        sys.exit(1)

    logging.info("Starting TikTok comments scrape for %d URLs", len(urls))
    logging.info("Settings: limit=%s concurrency=%s proxy=%s timeout=%ss",
                 settings["comment_limit"], settings["concurrency"],
                 "yes" if settings["proxy"] else "no",
                 settings["timeout_seconds"])

    try:
        results = asyncio.run(
            scrape_all(
                urls=urls,
                comment_limit=int(settings["comment_limit"]),
                concurrency=int(settings["concurrency"]),
                proxy=settings.get("proxy"),
                timeout_seconds=int(settings["timeout_seconds"]),
            )
        )
    except KeyboardInterrupt:
        logging.warning("Interrupted by user")
        sys.exit(130)
    except Exception as e:
        logging.exception("Fatal error: %s", e)
        sys.exit(2)

    # Flatten results for CSV option; keep mapping for JSON option too
    exporter = Exporter(output_dir=Path(settings["output_dir"]))

    timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    metadata = {
        "generated_at": now_utc_iso(),
        "source": "TikTok",
        "total_videos": len(results),
        "total_comments": sum(len(v) for v in results.values()),
        "comment_limit": int(settings["comment_limit"]),
    }

    if settings["output_format"].lower() == "csv":
        # Flatten into rows with url included
        rows: List[Dict[str, Any]] = []
        for url, comments in results.items():
            for c in comments:
                row = {"video_url": url}
                row.update(c)
                # Convert nested user dict into flat keys
                user = row.pop("user", {})
                for k, v in user.items():
                    row[f"user.{k}"] = v
                rows.append(row)
        out_path = exporter.to_csv(rows, filename=f"comments_{timestamp}.csv")
        logging.info("CSV written to %s", out_path)
        print(str(out_path.resolve()))
    else:
        out_path = exporter.to_json({"metadata": metadata, "results": results}, filename=f"comments_{timestamp}.json")
        logging.info("JSON written to %s", out_path)
        print(str(out_path.resolve()))

if __name__ == "__main__":
    main()