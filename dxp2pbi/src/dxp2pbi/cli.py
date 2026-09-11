"""dxp2pbi command line."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .archive import DxpArchive
from .extract import build_spec
from .graph import Graph
from .render_md import render_md
from .spec import Spec
from .tmdl.emit import emit
from .translate import store, translate
from .validate import validate_model


def _load_spec(d: Path) -> Spec:
    return Spec.model_validate_json((d / "spec.json").read_text(encoding="utf-8"))


def _render(d: Path, spec: Spec, translations: store.Translations | None) -> None:
    md_path = d / "spec.md"
    existing = md_path.read_text(encoding="utf-8") if md_path.exists() else None
    md_path.write_text(
        render_md(spec, existing=existing, has_preview=(d / "preview.png").exists(),
                  translations=translations.for_render() if translations else None),
        encoding="utf-8",
    )


def _model_roots(path: Path) -> list[Path]:
    path = path.resolve()
    for p in (path, *path.parents):
        if p.name.endswith(".SemanticModel"):
            return [p]
    base = path if path.is_dir() else path.parent
    return sorted(p for p in base.rglob("*.SemanticModel") if p.is_dir())


# -- steps ------------------------------------------------------------------------------------

def run_spec(file: str, out: str) -> Path:
    spec, archive = build_spec(file)
    d = Path(out) / spec.analysis_name
    d.mkdir(parents=True, exist_ok=True)
    (d / "spec.json").write_text(spec.model_dump_json(indent=2), encoding="utf-8")
    png = archive.preview_png()
    if png:
        (d / "preview.png").write_bytes(png)
    archive.close()
    _render(d, spec, store.load(d / "translations.json"))
    print(
        f"{spec.analysis_name}: {len(spec.tables)} tables, "
        f"{sum(len(t.columns) for t in spec.tables)} columns, {len(spec.pages)} pages, "
        f"{sum(len(p.visuals) for p in spec.pages)} visuals, {len(spec.expressions)} expressions, "
        f"{len(spec.risks)} risks -> {d}"
    )
    return d


def run_translate(d: Path) -> store.Translations:
    spec = _load_spec(d)
    translations = translate(spec, store.load(d / "translations.json"))
    store.save(translations, d / "translations.json")
    _render(d, spec, translations)
    summary = ", ".join(f"{k}={v}" for k, v in sorted(translations.summary().items()))
    print(f"{spec.analysis_name}: translations {summary}")
    return translations


def run_tmdl(d: Path) -> bool:
    spec = _load_spec(d)
    translations = run_translate(d)
    result = emit(spec, translations, d)
    print(f"{spec.analysis_name}: wrote {result.root} ({len(result.todos)} TODO)")
    for todo in result.todos:
        print(f"  TODO {todo}")
    report = validate_model(result.root)
    print(report.render().splitlines()[0])
    for e in report.errors:
        print(f"  error: {e}")
    return report.ok


# -- commands ---------------------------------------------------------------------------------

def cmd_spec(args: argparse.Namespace) -> int:
    for file in args.files:
        run_spec(file, args.out)
    return 0


def cmd_translate(args: argparse.Namespace) -> int:
    for d in args.dirs:
        run_translate(Path(d))
    return 0


def cmd_tmdl(args: argparse.Namespace) -> int:
    ok = [run_tmdl(Path(d)) for d in args.dirs]
    return 0 if all(ok) else 1


def cmd_validate(args: argparse.Namespace) -> int:
    roots = [r for p in args.paths for r in _model_roots(Path(p))]
    if not roots:
        print("no .SemanticModel folder found", file=sys.stderr)
        return 1
    failed = False
    for root in roots:
        report = validate_model(root)
        print(report.render(), file=sys.stdout if report.ok else sys.stderr)
        failed |= not report.ok
    return 1 if failed else 0


def cmd_all(args: argparse.Namespace) -> int:
    ok = [run_tmdl(run_spec(file, args.out)) for file in args.files]
    return 0 if all(ok) else 1


def cmd_inspect(args: argparse.Namespace) -> int:
    with DxpArchive.open(args.file) as archive:
        graph = Graph(archive.document_xml())
        print(f"{archive.name}: document {archive.document_path} (v{archive.document_version}), "
              f"saved by {archive.saved_by_version}")
        print(f"  nodes: {len(graph.nodes)}  unknown tags: {sorted(graph.unknown_tags) or 'none'}")
        print(f"  resources: {', '.join(sorted(archive.resources))}")
        for name, count in graph.type_inventory().most_common(args.types or None):
            if name.startswith("Spotfire.") and (args.types or ".Visuals." in name or ".Import." in name):
                print(f"  {count:6}  {name}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="dxp2pbi", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("spec", help="extract spec.json + spec.md from .dxp files")
    p.add_argument("files", nargs="+")
    p.add_argument("--out", default="out", help="output root (default: ./out)")
    p.set_defaults(func=cmd_spec)

    p = sub.add_parser("translate", help="apply rules to write/merge translations.json")
    p.add_argument("dirs", nargs="+", help="analysis output folders, e.g. out/Viajes2024")
    p.set_defaults(func=cmd_translate)

    p = sub.add_parser("tmdl", help="emit <analysis>.SemanticModel/ from spec + translations")
    p.add_argument("dirs", nargs="+", help="analysis output folders, e.g. out/Viajes2024")
    p.set_defaults(func=cmd_tmdl)

    p = sub.add_parser("validate", help="check a generated semantic model")
    p.add_argument("paths", nargs="+", help="a .SemanticModel folder, a file inside it, or a parent folder")
    p.set_defaults(func=cmd_validate)

    p = sub.add_parser("all", help="spec -> translate -> tmdl -> validate for .dxp files")
    p.add_argument("files", nargs="+")
    p.add_argument("--out", default="out", help="output root (default: ./out)")
    p.set_defaults(func=cmd_all)

    p = sub.add_parser("inspect", help="summarize the object graph of one .dxp")
    p.add_argument("file")
    p.add_argument("--types", type=int, default=0, help="show the N most common types")
    p.set_defaults(func=cmd_inspect)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
