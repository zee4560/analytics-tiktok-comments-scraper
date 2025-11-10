import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable

@dataclass
class Exporter:
    output_dir: Path

    def _ensure_dir(self) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def to_json(self, obj: Dict[str, Any], filename: str) -> Path:
        self._ensure_dir()
        out_path = self.output_dir / filename
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(obj, f, indent=2, ensure_ascii=False)
        return out_path

    def to_csv(self, rows: Iterable[Dict[str, Any]], filename: str) -> Path:
        self._ensure_dir()
        rows = list(rows)
        if not rows:
            # Write a placeholder CSV with a single column to indicate emptiness
            out_path = self.output_dir / filename
            with open(out_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["info"])
                writer.writerow(["No rows"])
            return out_path

        # Determine the superset of all keys
        keys = set()
        for r in rows:
            keys.update(r.keys())
        fieldnames = sorted(keys)

        out_path = self.output_dir / filename
        with open(out_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            for r in rows:
                writer.writerow({k: r.get(k, "") for k in fieldnames})
        return out_path