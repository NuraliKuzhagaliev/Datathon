from dataclasses import dataclass, field
from pathlib import Path
import os


ROOT = next(
    parent
    for parent in Path(__file__).resolve().parents
    if (parent / "packages/contracts/openapi.json").is_file()
)


@dataclass(frozen=True)
class Settings:
    data_dir: Path = field(default_factory=lambda: ROOT / "runtime-data")
    model_dir: Path = field(
        default_factory=lambda: Path(
            os.getenv("CASHPROOF_MODEL_DIR", str(ROOT / "models/Qwen3-VL-2B-Instruct"))
        ).resolve()
    )
    rules_path: Path = field(
        default_factory=lambda: Path(
            os.getenv("CASHPROOF_RULES", str(ROOT / "assets/rules/registry.json"))
        ).resolve()
    )
    frontend_dir: Path | None = None
    mode: str = field(default_factory=lambda: os.getenv("CASHPROOF_MODE", "offline"))
    operator_key: str = field(
        default_factory=lambda: os.getenv("CASHPROOF_API_KEY", "")
    )
    jury_key: str = field(default_factory=lambda: os.getenv("CASHPROOF_JURY_KEY", ""))
    max_pending: int = field(
        default_factory=lambda: int(os.getenv("CASHPROOF_MAX_PENDING", "1"))
    )
    watchdog_sec: float = field(
        default_factory=lambda: float(os.getenv("CASHPROOF_WATCHDOG_SEC", "270"))
    )
    max_upload_bytes: int = 128 * 1024 * 1024
    max_candidates: int = 8

    def __post_init__(self):
        if self.mode not in {"offline", "server"}:
            raise ValueError("CASHPROOF_MODE must be offline or server")
        if len(self.operator_key) < 24:
            raise ValueError("Set a random CASHPROOF_API_KEY of at least 24 characters")
        if self.jury_key and (
            len(self.jury_key) < 24 or self.jury_key == self.operator_key
        ):
            raise ValueError("Jury and operator keys must be distinct random keys")
        if not 1 <= self.max_pending <= 5 or not 1 <= self.watchdog_sec <= 270:
            raise ValueError("Invalid admission/deadline configuration")


def force_offline():
    # These are imposed even in publicly reachable server mode.
    for key in (
        "HF_HUB_OFFLINE",
        "TRANSFORMERS_OFFLINE",
        "HF_HUB_DISABLE_TELEMETRY",
        "DO_NOT_TRACK",
    ):
        os.environ[key] = "1"
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    os.environ["OTEL_SDK_DISABLED"] = "true"
