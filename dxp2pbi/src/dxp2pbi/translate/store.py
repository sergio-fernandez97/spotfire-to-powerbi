"""``translations.json``: how each Spotfire expression maps to Power BI.

Items with status ``ai`` or ``human`` are never overwritten by a re-run of the rules, so the work
done by the ``dxp-tmdl`` skill (or a person) survives regenerating the spec.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from ..spec import ExpressionKind

Status = Literal["rule", "ai", "human", "needs_review", "unsupported", "not_applicable"]
TargetKind = Literal["measure", "calculated_column", "relationship", "visual", "none"]

KEEP_STATUSES = {"ai", "human"}
READY_STATUSES = {"rule", "ai", "human"}


class TranslationItem(BaseModel):
    id: str
    kind: ExpressionKind
    table: str | None = None
    expression: str
    target_kind: TargetKind
    status: Status
    name: str | None = None
    dax: str | None = None
    notes: str | None = None


class Translations(BaseModel):
    analysis_name: str
    spec_version: str
    items: list[TranslationItem] = Field(default_factory=list)

    def summary(self) -> dict[str, int]:
        return dict(Counter(i.status for i in self.items))

    def for_render(self) -> dict[str, dict]:
        return {
            i.expression: {"status": i.status, "target": i.dax or i.notes}
            for i in self.items
        }


def load(path: Path) -> Translations | None:
    if not path.exists():
        return None
    return Translations.model_validate_json(path.read_text(encoding="utf-8"))


def save(translations: Translations, path: Path) -> None:
    path.write_text(translations.model_dump_json(indent=2), encoding="utf-8")
