from pathlib import Path


def project_root() -> Path:
    """仓库根目录（含 `docs/`、`pyproject.toml`）。

    `paths.py` 为 `src/app/core/paths.py`：`parents[0]` 同 `parent`（`core/`），
    再向上 `app` → `src` → 仓库根为 `parents[3]`。
    """
    return Path(__file__).resolve().parents[3]
