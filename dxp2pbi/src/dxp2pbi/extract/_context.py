from __future__ import annotations

from dataclasses import dataclass, field

from ..graph import Graph, Node
from ..spec import ExpressionKind, ExpressionUse, Spec


def text_of(value) -> str | None:
    """Expression text from a ``PreprocessorNode`` (or a plain string)."""
    if isinstance(value, Node):
        expr = value.get("Expression")
        return expr if isinstance(expr, str) else None
    return value if isinstance(value, str) else None


@dataclass
class Context:
    graph: Graph
    spec: Spec
    _uses: dict[tuple[str, str, str | None], ExpressionUse] = field(default_factory=dict)

    def use(self, expression: str, kind: ExpressionKind, table: str | None, location: str) -> None:
        """Record where an expression is used, de-duplicated by (expression, kind, table)."""
        key = (expression, kind, table)
        use = self._uses.get(key)
        if use is None:
            use = self._uses[key] = ExpressionUse(expression=expression, kind=kind, table=table)
            self.spec.expressions.append(use)
        if location not in use.locations:
            use.locations.append(location)

    def unparsed(self, message: str) -> None:
        if message not in self.spec.unparsed:
            self.spec.unparsed.append(message)
