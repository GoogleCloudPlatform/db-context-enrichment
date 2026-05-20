#!/usr/bin/env python3
"""Ask a natural-language question of a GCP customer's BigQuery data.

Wraps Google Cloud's Conversational Analytics API
(geminidataanalytics.googleapis.com, currently in Preview). Two modes:

  Mode A (explicit tables):
    data_qa.py --project=P --table=P:DS.T [--table=...] --question="..."

  Mode B (wiki-grounded):
    data_qa.py --project=P --wiki-dir=PATH --question="..."
    (auto-extracts tables + composes a rich system instruction from the wiki)

Output: JSON to stdout. See SKILL.md for the schema.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Any

# Lazy import so --help works without the SDK installed.
def _load_sdk():
    """Pin to the v1beta surface; the default `geminidataanalytics` package
    currently resolves to v1alpha which has different message field shapes."""
    try:
        from google.cloud import geminidataanalytics_v1beta as geminidataanalytics  # type: ignore
        return geminidataanalytics
    except ImportError as e:
        die(f"Python SDK not installed: {e}\n"
            f"  fix: pip install -r {Path(__file__).parent}/requirements.txt")


def die(msg: str, code: int = 2):
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(code)


def parse_table_ref(ref: str) -> tuple[str, str, str]:
    """Parse 'project:dataset.table' or 'project.dataset.table' -> (p, ds, t)."""
    if ":" in ref:
        proj, rest = ref.split(":", 1)
    else:
        parts = ref.split(".")
        if len(parts) != 3:
            die(f"bad --table {ref!r}: want project:dataset.table or project.dataset.table")
        return tuple(parts)  # type: ignore
    if "." not in rest or rest.count(".") != 1:
        die(f"bad --table {ref!r}: want project:dataset.table")
    ds, tbl = rest.split(".", 1)
    return proj, ds, tbl


def tables_fingerprint(tables: list[str]) -> str:
    """Stable short hash of the table set, used to name the chart tempfile so
    reruns of the same question on the same tables overwrite the prior preview."""
    return hashlib.sha256("|".join(sorted(tables)).encode()).hexdigest()[:12]


def chat_one_shot(
    geminidataanalytics, *,
    project: str, location: str,
    tables: list[tuple[str, str, str]],
    system_instruction: str,
    question: str,
) -> list[dict[str, Any]]:
    """Stateless, agentless chat.

    Uses `ChatRequest.inline_context` to pass the BigQuery datasource
    references and system instruction inline on every call — no
    `DataAgent` resource is created or persisted in the project. This
    avoids accumulating per-table-set agent resources across question
    history and removes the create/AlreadyExists roundtrip.
    """
    chat_client = geminidataanalytics.DataChatServiceClient()
    parent = f"projects/{project}/locations/{location}"

    bq_refs = [
        geminidataanalytics.BigQueryTableReference(
            project_id=p, dataset_id=ds, table_id=t,
        )
        for (p, ds, t) in tables
    ]
    ds_refs = geminidataanalytics.DatasourceReferences()
    ds_refs.bq.table_references = bq_refs

    ctx = geminidataanalytics.Context(
        # 32K-char cap accommodates the v0.4 enriched system instruction
        # (per-table fields/lineage + personal_context narrative). The API
        # handles long instructions in practice; the cap is just defensive.
        system_instruction=system_instruction[:32000],
        datasource_references=ds_refs,
    )

    msg = geminidataanalytics.Message()
    msg.user_message.text = question

    req = geminidataanalytics.ChatRequest(
        parent=parent, messages=[msg], inline_context=ctx,
    )

    messages: list[dict[str, Any]] = []
    for resp in chat_client.chat(request=req):
        messages.append(_normalize_response(resp))
    return messages


def _normalize_response(resp) -> dict[str, Any]:
    """Best-effort flatten of a streamed response into a JSON-able dict.

    The API has a few message variants (system_message: thought / progress /
    final_response / data / chart, plus error). We pull the salient fields and
    skip what we can't represent."""
    out: dict[str, Any] = {}
    try:
        if hasattr(resp, "system_message") and resp.system_message:
            sm = resp.system_message
            if hasattr(sm, "thought") and getattr(sm.thought, "thoughts", None):
                out = {"type": "THOUGHT", "text": "\n".join(sm.thought.thoughts)}
            elif hasattr(sm, "progress") and getattr(sm.progress, "thoughts", None):
                out = {"type": "PROGRESS", "text": "\n".join(sm.progress.thoughts)}
            elif hasattr(sm, "data") and sm.data:
                d = sm.data
                # Schema + rows if available
                schema = []
                rows = []
                if hasattr(d, "result") and d.result:
                    if hasattr(d.result, "schema") and d.result.schema:
                        schema = [
                            {"name": f.name, "type": str(f.type_)}
                            for f in (d.result.schema.fields or [])
                        ]
                    if hasattr(d.result, "data"):
                        for r in (d.result.data or []):
                            rows.append({k: _scalar(v) for k, v in r.items()})
                out = {"type": "DATA", "schema": schema, "rows": rows}
                # Optional generated SQL on data messages
                if hasattr(d, "generated_sql") and d.generated_sql:
                    out["sql"] = d.generated_sql
            elif hasattr(sm, "chart") and sm.chart:
                out = _normalize_chart(sm.chart)
            elif hasattr(sm, "text") and getattr(sm.text, "parts", None):
                out = {"type": "FINAL_RESPONSE", "text": "\n".join(sm.text.parts)}
        elif hasattr(resp, "error") and resp.error:
            out = {"type": "ERROR", "text": str(resp.error)}
    except Exception as e:
        out = {"type": "PARSE_ERROR", "text": f"could not normalize: {e}", "raw": str(resp)[:500]}

    if not out:
        # Last-ditch: stringify a small chunk so we don't lose visibility.
        out = {"type": "UNKNOWN", "raw": str(resp)[:500]}
    return out


def _normalize_chart(chart) -> dict[str, Any]:
    """Extract a Vega-Lite spec (and the Python instructions that produced it)
    from a CHART system message. The v1beta API has the spec in a few
    possible locations depending on which step of generation we're seeing,
    so we try several paths defensively."""
    out: dict[str, Any] = {"type": "CHART"}

    # Step 1: the agent's Python/Altair instructions
    if hasattr(chart, "query") and chart.query:
        q = chart.query
        for attr in ("instructions", "code"):
            if hasattr(q, attr):
                val = getattr(q, attr)
                if val:
                    out["instructions"] = str(val)
                    break

    # Step 2: the resolved Vega-Lite spec (proto Struct or pre-parsed dict).
    spec = None
    if hasattr(chart, "result") and chart.result:
        r = chart.result
        # Try common field names: vega_config, spec, vega_lite_spec, config
        for attr in ("vega_config", "spec", "vega_lite_spec", "config"):
            if hasattr(r, attr):
                val = getattr(r, attr)
                if val:
                    spec = _proto_to_jsonable(val)
                    if spec:
                        break

    if spec:
        out["spec"] = spec
    else:
        # Save the proto repr so we can debug if extraction fails.
        out["debug_raw"] = str(chart)[:500]

    return out


def _proto_to_jsonable(v: Any) -> Any:
    """Convert a protobuf Struct / Value / MapComposite / dict-like /
    ListComposite into a plain JSON-able tree, recursing through nested
    structures. Vega-Lite specs from the API arrive as nested
    proto.marshal.collections (MapComposite / RepeatedComposite), which
    look dict/list-like but stringify as `<MapComposite object at 0x...>`
    in JSON unless we walk them explicitly."""
    # Strings: try JSON first (some API variants return spec as a JSON string)
    if isinstance(v, str):
        try:
            import json as _json
            parsed = _json.loads(v)
            return _proto_to_jsonable(parsed)  # recurse into the parsed structure
        except Exception:
            return v

    # Plain JSON scalars
    if isinstance(v, (int, float, bool, type(None))):
        return v

    # Try google.protobuf.Struct / Value via MessageToDict (handles full Message
    # with DESCRIPTOR; recurses correctly)
    try:
        from google.protobuf.json_format import MessageToDict
        if hasattr(v, "DESCRIPTOR"):
            return MessageToDict(v, preserving_proto_field_name=True)
    except Exception:
        pass

    # MapComposite / dict-like — has .items() and indexing
    if hasattr(v, "items"):
        try:
            return {str(k): _proto_to_jsonable(vv) for k, vv in v.items()}
        except Exception:
            pass

    # RepeatedComposite / list-like — iterable but not dict-like
    if hasattr(v, "__iter__") and not isinstance(v, (str, bytes)):
        try:
            return [_proto_to_jsonable(item) for item in v]
        except Exception:
            pass

    # Last resort: stringify
    return str(v)


def _scalar(v: Any) -> Any:
    """Coerce a protobuf scalar value to a JSON-compatible type."""
    try:
        from google.protobuf.struct_pb2 import Value
        if isinstance(v, Value):
            kind = v.WhichOneof("kind")
            if kind == "null_value":
                return None
            if kind == "number_value":
                return v.number_value
            if kind == "string_value":
                return v.string_value
            if kind == "bool_value":
                return v.bool_value
            return None
    except Exception:
        pass
    if isinstance(v, (int, float, str, bool, type(None))):
        return v
    return str(v)


def write_transcript(out_path: Path, payload: dict[str, Any]) -> None:
    """Write a markdown transcript of the session for archival.

    The Conversational Analytics API streams MANY messages in a single chat
    (multiple THOUGHTs, multiple text payloads — some are intermediate
    progress narration, some are the final answer, some are follow-up
    suggestions). To keep the transcript readable we consolidate by type:
    one consolidated "## Answer" section (final response streams joined),
    one "## SQL" section (last DATA message with a sql field), one "##
    Result data" section if schema/rows came through, and one collapsed
    "## Agent reasoning" trail at the bottom for THOUGHT/PROGRESS.
    """
    lines = [
        f"# Q&A session — {payload['question']}",
        "",
        f"- Project: `{payload['project']}`",
        f"- Tables: " + ", ".join(f"`{t}`" for t in payload['tables']),
        f"- Context mode: `{payload['context_mode']}` (no DataAgent resource created)",
        f"- Generated at: {payload['generated_at']}",
        f"- Duration: {payload['duration_seconds']}s",
        "",
        "## Question",
        f"> {payload['question']}",
        "",
    ]

    msgs = payload["messages"]
    final_responses = [m.get("text", "") for m in msgs if m.get("type") == "FINAL_RESPONSE"]
    thoughts = [m.get("text", "") for m in msgs if m.get("type") in ("THOUGHT", "PROGRESS")]
    errors = [m.get("text", "") for m in msgs if m.get("type") == "ERROR"]
    sqls = [m.get("sql") for m in msgs if m.get("type") == "DATA" and m.get("sql")]
    last_data = next((m for m in reversed(msgs)
                      if m.get("type") == "DATA" and (m.get("schema") or m.get("rows"))), None)

    if errors:
        lines += ["## Errors", ""]
        for e in errors:
            lines += ["```", e, "```", ""]

    if final_responses:
        lines += ["## Answer", ""]
        # Trim duplicates (the API often re-sends the same intro for each text stream).
        seen: set[str] = set()
        deduped = []
        for fr in final_responses:
            key = fr.strip()[:120]
            if key in seen:
                continue
            seen.add(key)
            deduped.append(fr.strip())
        lines.append("\n\n".join(deduped))
        lines.append("")

    if sqls:
        # Use the last unique SQL (intermediate streams sometimes repeat).
        unique_sqls = list(dict.fromkeys(sqls))
        lines += ["## SQL", "", "```sql", unique_sqls[-1], "```", ""]

    if last_data and (last_data.get("schema") and last_data.get("rows")):
        schema = last_data["schema"]
        rows = last_data["rows"]
        lines += ["## Result data", ""]
        lines.append("| " + " | ".join(s["name"] for s in schema) + " |")
        lines.append("|" + "|".join("---" for _ in schema) + "|")
        for r in rows[:20]:
            lines.append("| " + " | ".join(str(r.get(s["name"], "")) for s in schema) + " |")
        if len(rows) > 20:
            lines.append(f"\n_({len(rows)} rows total; showing first 20)_")
        lines.append("")

    # Charts — link to the interactive HTML preview that the top-level driver
    # already wrote to payload["chart_html_path"], and inline the spec(s).
    charts = [m for m in msgs if m.get("type") == "CHART"]
    chart_specs = [c for c in charts if c.get("spec")]
    if charts:
        lines += ["## Charts", ""]
        if chart_specs:
            chart_html = payload.get("chart_html_path")
            if chart_html:
                lines.append(
                    f"{len(chart_specs)} chart(s) rendered. "
                    f"Open the interactive preview: [{Path(chart_html).name}]({chart_html})"
                )
                lines.append("")
            for i, c in enumerate(chart_specs, 1):
                lines += [f"### Chart {i} — Vega-Lite spec", "", "```json",
                          json.dumps(c["spec"], indent=2)[:4000], "```", ""]
        else:
            lines.append("_(chart messages were emitted but no spec could be extracted "
                         "from the v1beta payload — this is a known wrapper limitation; "
                         "the chart's underlying SQL+data are still in the Result data section)_")
            lines.append("")

    if thoughts:
        lines += ["## Agent reasoning trail", "",
                  "_(intermediate THOUGHT / PROGRESS messages, oldest first)_", ""]
        for i, t in enumerate(thoughts, 1):
            lines += [f"**Step {i}:**", "", t.strip(), ""]

    out_path.write_text("\n".join(lines), encoding="utf-8")


def write_charts_html(out_path: Path, question: str, charts: list[dict[str, Any]]) -> None:
    """Render a self-contained HTML file with every chart spec inlined as SVG.

    Charts are pre-rendered server-side via vl-convert-python so the output
    works on `file://`, in markdown viewers, and in script-blocked browsers
    without needing a CDN load. If vl-convert isn't available, falls back
    to vega-embed via CDN (interactive but requires network + scripts)."""
    try:
        import vl_convert as vlc  # type: ignore
        have_vlc = True
    except ImportError:
        have_vlc = False

    chart_blocks: list[str] = []
    cdn_scripts: list[str] = []
    rendered_inline = 0

    for i, c in enumerate(charts, 1):
        spec = c.get("spec")
        if not spec:
            continue
        # Vega-Lite specs from the API often declare schema v4; vl-convert
        # handles v4/v5 transparently.
        spec_json = json.dumps(spec)
        if have_vlc:
            try:
                svg = vlc.vegalite_to_svg(spec_json)
                chart_blocks.append(f'<h2>Chart {i}</h2><div class="chart-svg">{svg}</div>')
                rendered_inline += 1
                continue
            except Exception as e:
                # Fall through to CDN-based rendering for this chart.
                chart_blocks.append(
                    f'<h2>Chart {i}</h2>'
                    f'<div id="chart-{i}"><pre>vl-convert failed ({e}); '
                    f'attempting interactive render…</pre></div>'
                )
                cdn_scripts.append(
                    f"vegaEmbed('#chart-{i}', {spec_json}, {{actions: true}})"
                    f".catch(e => {{ document.getElementById('chart-{i}').innerHTML = "
                    f"'<pre>chart-{i} render failed: ' + e + '</pre>'; }});"
                )
        else:
            chart_blocks.append(f'<h2>Chart {i}</h2><div id="chart-{i}"></div>')
            cdn_scripts.append(
                f"vegaEmbed('#chart-{i}', {spec_json}, {{actions: true}})"
                f".catch(e => {{ document.getElementById('chart-{i}').innerHTML = "
                f"'<pre>chart-{i} render failed: ' + e + '</pre>'; }});"
            )

    cdn_block = ""
    if cdn_scripts:
        cdn_block = (
            '<script src="https://cdn.jsdelivr.net/npm/vega@5"></script>\n'
            '<script src="https://cdn.jsdelivr.net/npm/vega-lite@5"></script>\n'
            '<script src="https://cdn.jsdelivr.net/npm/vega-embed@6"></script>\n'
            f'<script>\n{chr(10).join(cdn_scripts)}\n</script>'
        )

    if rendered_inline == len(charts) and rendered_inline > 0:
        meta = f"{len(charts)} chart(s) rendered as inline SVG (self-contained, no scripts required)."
    elif rendered_inline > 0:
        meta = f"{rendered_inline} of {len(charts)} chart(s) inlined; the rest fall back to vega-embed (needs network + JS)."
    else:
        meta = f"{len(charts)} chart(s) via vega-embed (CDN). For self-contained SVG output, install vl-convert-python."

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Q&A charts — {html_escape(question[:80])}</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif; max-width: 1100px; margin: 30px auto; padding: 0 24px; color: #1f2328; }}
  h1 {{ font-size: 18px; color: #57606a; margin-bottom: 4px; }}
  h1 .q {{ display: block; color: #1f2328; font-size: 22px; margin-top: 4px; }}
  h2 {{ font-size: 16px; margin-top: 36px; padding-bottom: 6px; border-bottom: 1px solid #d1d9e0; }}
  .meta {{ font-size: 12px; color: #6e7781; margin-bottom: 28px; }}
  .chart-svg svg {{ max-width: 100%; height: auto; }}
</style>
</head>
<body>
<h1>Q&amp;A charts <span class="q">{html_escape(question)}</span></h1>
<div class="meta">{meta}</div>
{''.join(chart_blocks)}
{cdn_block}
</body>
</html>
"""
    out_path.write_text(html, encoding="utf-8")


def html_escape(s: str) -> str:
    """Minimal HTML escape for embedding text in the chart preview."""
    import html as _h
    return _h.escape(s, quote=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--location", default="global")
    ap.add_argument("--question", required=True)
    ap.add_argument("--table", action="append", default=[],
                    help="repeatable: PROJECT:DATASET.TABLE (Mode A)")
    ap.add_argument("--wiki-dir", help="path to a per-customer wiki dir (Mode B)")
    ap.add_argument("--output-file", help="also write a markdown transcript to this path")
    ap.add_argument("--chart-html",
                    help="path for the interactive Vega-Lite chart preview. "
                         "If omitted, defaults to a tempfile when charts are present "
                         "(or to a sibling of --output-file if that's set).")
    args = ap.parse_args()

    if not args.table and not args.wiki_dir:
        die("must give --table (one or more) OR --wiki-dir")
    if args.table and args.wiki_dir:
        die("specify --table OR --wiki-dir, not both")

    geminidataanalytics = _load_sdk()

    # Resolve tables + system instruction.
    system_instruction = ""
    table_strs: list[str] = []
    warnings: list[str] = []

    if args.wiki_dir:
        # Local import (we're inside scripts/, wiki_parser.py is a sibling).
        sys.path.insert(0, str(Path(__file__).parent))
        from wiki_parser import parse_wiki
        ctx = parse_wiki(Path(args.wiki_dir), project_fallback=args.project)
        if not ctx.tables:
            die(f"wiki at {args.wiki_dir} produced no tables. Warnings: {ctx.warnings}")
        table_strs = ctx.tables
        system_instruction = ctx.system_instruction
        warnings = ctx.warnings
    else:
        table_strs = args.table
        system_instruction = (
            f"You are answering questions about BigQuery data in project `{args.project}`. "
            f"Tables available:\n" + "\n".join(f"- `{t}`" for t in table_strs) +
            "\nUse only these tables. If a question can't be answered with them, say so plainly."
        )

    parsed_tables = [parse_table_ref(t.replace(".", ":", 1) if t.count(".") == 2 and ":" not in t else t)
                     for t in table_strs]

    started = time.time()
    messages = chat_one_shot(
        geminidataanalytics,
        project=args.project, location=args.location,
        tables=parsed_tables, system_instruction=system_instruction,
        question=args.question,
    )
    duration = round(time.time() - started, 2)

    payload = {
        "question": args.question,
        "project": args.project,
        "location": args.location,
        "tables": table_strs,
        "context_mode": "inline",
        "generated_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "duration_seconds": duration,
        "messages": messages,
        "warnings": warnings,
        "system_instruction_chars": len(system_instruction),
    }

    # Always render an interactive HTML preview when chart specs come back.
    # Path selection priority:
    #   1. --chart-html (explicit)
    #   2. sibling of --output-file (.charts.html)
    #   3. tempfile keyed on a fingerprint of the table set so reruns of the
    #      same question on the same tables overwrite the prior preview
    chart_specs = [m for m in messages if m.get("type") == "CHART" and m.get("spec")]
    if chart_specs:
        if args.chart_html:
            chart_path = Path(args.chart_html)
        elif args.output_file:
            chart_path = Path(args.output_file).with_suffix(".charts.html")
        else:
            import tempfile
            chart_path = Path(tempfile.gettempdir()) / f"data_qa_charts_{tables_fingerprint(table_strs)}.html"
        write_charts_html(chart_path, args.question, chart_specs)
        payload["chart_html_path"] = str(chart_path.resolve())
        print(f"# wrote {len(chart_specs)} chart(s) to {chart_path}", file=sys.stderr)

    print(json.dumps(payload, indent=2, default=str))

    if args.output_file:
        write_transcript(Path(args.output_file), payload)
        print(f"# wrote transcript to {args.output_file}", file=sys.stderr)


if __name__ == "__main__":
    main()
