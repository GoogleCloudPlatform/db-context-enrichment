#!/usr/bin/env python3
"""Upload Context Set JSON to Dataplex Knowledge Catalog & Benchmark Latency.

Creates:
1. EntryGroup (Context Bundle Container) - waits for Long Running Operation (LRO)
2. Context Set Entry with 'context-set-aspect' (domain info and tables)
3. Query Template Entries with 'query-template-aspect' (nlQuery, parameterizedIntent, parameterizedSql, sql)

Benchmarks & Verifies:
- Recall@K Accuracy (-k / --top_k): Verifies if expected template is returned within Top K results and reports matched rank.
- Upload & Search Latencies: P50 and P95 (ms).

Modes:
- --first_n N: Process only first N templates (0 = all).
- -k / --top_k K: Retrieve top K results and evaluate Recall@K (default: 5).
- --search_only: Skip upload and run semantic searches.
- --search_iterations N: Number of search runs to benchmark (default: 5).
- --verbose / -v: Pretty-print live Dataplex resource JSON and raw API payloads.
- --delete: Delete the EntryGroup and exit.
"""

import argparse
import json
import logging
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)


def parse_args():
  parser = argparse.ArgumentParser(
      description="Upload Context Set JSON to Dataplex Knowledge Catalog and benchmark latency / Recall@K."
  )
  parser.add_argument("--input_json", required=True, help="Path to input context set JSON file.")
  parser.add_argument("--project", default="cloud-db-nl2sql", help="GCP Project ID.")
  parser.add_argument("--location", default="us-central1", help="GCP Location (e.g. us-central1).")
  parser.add_argument("--bundle_id", default="bundle-financial", help="EntryGroup ID.")
  parser.add_argument("--domain_name", default="Financial Reporting", help="Analytical domain name.")
  parser.add_argument("--domain_description", default="", help="Optional domain description.")
  parser.add_argument("--endpoint", default="https://dataplex.googleapis.com", help="Dataplex API endpoint.")
  parser.add_argument("--auth_token", default="", help="OAuth2 token (or use AUTH_TOKEN env var).")
  parser.add_argument("--first_n", type=int, default=0, help="Upload/search only first N templates (0 = all).")
  parser.add_argument("-k", "--top_k", type=int, default=5, help="Number of results to retrieve (Recall@K evaluation).")
  parser.add_argument("--search_only", action="store_true", help="Skip upload and only search templates.")
  parser.add_argument("--search_query", default="", help="Custom query string to search for.")
  parser.add_argument("--search_iterations", type=int, default=5, help="Number of search iterations to benchmark.")
  parser.add_argument("-v", "--verbose", action="store_true", help="Pretty-print live Dataplex resource JSON and raw responses.")
  parser.add_argument("--delete", action="store_true", help="Delete the EntryGroup and exit.")
  return parser.parse_args()


def get_auth_token(token: str) -> str:
  """Gets token from argument, AUTH_TOKEN env, or gcloud CLI."""
  if token:
    return token.strip()
  if os.environ.get("AUTH_TOKEN"):
    return os.environ["AUTH_TOKEN"].strip()
  try:
    return subprocess.check_output(
        ["gcloud", "auth", "application-default", "print-access-token"], text=True
    ).strip()
  except Exception:
    pass
  try:
    return subprocess.check_output(
        ["gcloud", "auth", "print-access-token"], text=True
    ).strip()
  except Exception:
    return ""


def request(url: str, method: str, payload: Optional[Dict[str, Any]], token: str) -> Tuple[int, Dict[str, Any], float]:
  """Sends HTTP request to Dataplex REST API and returns (status_code, json_body, latency_sec)."""
  headers = {"Content-Type": "application/json"}
  if token:
    headers["Authorization"] = f"Bearer {token}"

  data_bytes = json.dumps(payload).encode("utf-8") if payload is not None else None
  req = urllib.request.Request(url=url, data=data_bytes, headers=headers, method=method)

  start = time.perf_counter()
  try:
    with urllib.request.urlopen(req, timeout=60) as resp:
      elapsed = time.perf_counter() - start
      body = resp.read().decode("utf-8")
      return resp.status, json.loads(body) if body.strip() else {}, elapsed
  except urllib.error.HTTPError as e:
    elapsed = time.perf_counter() - start
    body = e.read().decode("utf-8")
    try:
      return e.code, json.loads(body), elapsed
    except Exception:
      return e.code, {"error": body}, elapsed


def wait_for_lro(endpoint: str, op_name: str, token: str, timeout_sec: int = 45):
  """Polls a Dataplex Long Running Operation until it completes."""
  logging.info("Waiting for LRO %s to complete...", op_name)
  start = time.time()
  while time.time() - start < timeout_sec:
    url = f"{endpoint.rstrip('/')}/v1/{op_name}"
    status, body, _ = request(url, "GET", None, token)
    if status == 200 and body.get("done"):
      if "error" in body:
        logging.error("LRO failed: %s", body["error"])
        sys.exit(1)
      logging.info("EntryGroup creation finished successfully.")
      return
    time.sleep(1.0)
  logging.warning("LRO wait timed out after %d seconds.", timeout_sec)


def sanitize_id(text: str, idx: int) -> str:
  """Sanitizes query text into a valid Dataplex Entry ID."""
  cleaned = re.sub(r"[^a-zA-Z0-9_-]", "-", text.lower().strip())
  cleaned = re.sub(r"-+", "-", cleaned).strip("-")[:35]
  return f"template-{idx}-{cleaned}" if cleaned else f"template-{idx}"


def extract_tables(data: Dict[str, Any]) -> List[str]:
  """Extracts simple table names from the dataset definition."""
  tables = []
  datasets = data.get("dataset", [])
  if isinstance(datasets, dict):
    datasets = [datasets]
  for item in datasets:
    if isinstance(item, dict):
      for t in item.get("tables", []):
        name = t.split("/")[-1] if "/" in t else t
        if name and name not in tables:
          tables.append(name)
  return tables


def print_resource(endpoint: str, path: str, token: str, label: str):
  """GETs and pretty-prints a resource directly from Dataplex."""
  query = "?view=ALL" if "/entries/" in path else ""
  url = f"{endpoint.rstrip('/')}/v1/{path}{query}"
  status, body, elapsed = request(url, "GET", None, token)
  if status == 200:
    print("\n" + "=" * 80)
    print(f"=== LIVE DATAPLEX RESPONSE: {label} ({elapsed * 1000.0:.2f} ms) ===")
    print("=" * 80)
    print(json.dumps(body, indent=2))
    print("=" * 80 + "\n")
  else:
    logging.error("Failed to GET %s (Status %d): %s", label, status, body)


def search_templates(
    endpoint: str,
    project: str,
    location: str,
    bundle_id: str,
    query_text: str,
    token: str,
    page_size: int = 5,
) -> Tuple[int, Dict[str, Any], float, str]:
  """Executes SearchEntries with semantic search enabled across Dataplex Knowledge Catalog."""
  url = f"{endpoint.rstrip('/')}/v1/projects/{project}/locations/global:searchEntries"
  
  payload = {
      "name": f"projects/{project}/locations/global",
      "query": query_text,
      "pageSize": page_size,
      "scope": f"projects/{project}",
      "semanticSearch": True,
  }
  status, body, elapsed = request(url, "POST", payload, token)
  return status, body, elapsed, query_text


def calculate_stats(latencies: List[float]) -> Dict[str, float]:
  """Calculates min, avg, p50, p90, p95, max from latencies in seconds."""
  if not latencies:
    return {"min_ms": 0.0, "avg_ms": 0.0, "p50_ms": 0.0, "p90_ms": 0.0, "p95_ms": 0.0, "max_ms": 0.0}
  sorted_ms = sorted(lat * 1000.0 for lat in latencies)
  n = len(sorted_ms)
  return {
      "min_ms": round(sorted_ms[0], 2),
      "avg_ms": round(sum(sorted_ms) / n, 2),
      "p50_ms": round(sorted_ms[int(n * 0.50)], 2),
      "p90_ms": round(sorted_ms[int(n * 0.90)], 2),
      "p95_ms": round(sorted_ms[int(n * 0.95)], 2),
      "max_ms": round(sorted_ms[-1], 2),
  }


def main():
  args = parse_args()
  token = get_auth_token(args.auth_token)
  if not token:
    logging.error("No auth token provided. Pass --auth_token or export AUTH_TOKEN.")
    sys.exit(1)

  parent = f"projects/{args.project}/locations/{args.location}"
  eg_name = f"{parent}/entryGroups/{args.bundle_id}"

  # Mode: Delete
  if args.delete:
    url = f"{args.endpoint.rstrip('/')}/v1/{eg_name}"
    logging.info("Deleting EntryGroup %s...", args.bundle_id)
    status, body, elapsed = request(url, "DELETE", None, token)
    logging.info("Delete status %d (%.2f ms): %s", status, elapsed * 1000.0, body)
    return

  # Load JSON
  logging.info("Reading input JSON from: %s", args.input_json)
  with open(args.input_json, "r") as f:
    data = json.load(f)

  domain_desc = args.domain_description or f"{args.domain_name} context bundle."
  tables = extract_tables(data)
  cs_aspect_key = f"{args.project}.{args.location}.context-set-aspect"
  qt_aspect_key = f"{args.project}.{args.location}.query-template-aspect"

  templates = data.get("templates", [])
  if args.first_n > 0:
    logging.info("Filtering to first %d templates (out of %d).", args.first_n, len(templates))
    templates = templates[:args.first_n]

  test_items = []
  for idx, tpl in enumerate(templates, start=1):
    nl = tpl.get("nl_query", f"Template {idx}")
    manifest = tpl.get("manifest") or nl
    eid = sanitize_id(nl, idx)
    test_items.append({"query": manifest, "expected_id": eid, "nl_query": nl})

  upload_latencies = []
  uploaded_ids = []

  # -------------------------------------------------------------
  # UPLOAD PHASE (Skipped if --search_only)
  # -------------------------------------------------------------
  if not args.search_only:
    # 1. Create EntryGroup (Asynchronous LRO)
    logging.info("--> [1/3] Creating EntryGroup: %s", args.bundle_id)
    eg_url = f"{args.endpoint.rstrip('/')}/v1/{parent}/entryGroups?entry_group_id={args.bundle_id}"
    status, body, elapsed = request(
        eg_url, "POST",
        {"name": eg_name, "display_name": args.domain_name, "description": domain_desc},
        token,
    )
    if status in (200, 201):
      op_name = body.get("name")
      if op_name and not body.get("done"):
        wait_for_lro(args.endpoint, op_name, token)
      else:
        logging.info("Created EntryGroup '%s' in %.2f ms.", args.bundle_id, elapsed * 1000.0)
    elif status == 409:
      logging.info("EntryGroup '%s' already exists (409).", args.bundle_id)
    else:
      logging.error("Failed to create EntryGroup (Status %d): %s", status, body)
      sys.exit(1)

    # 2. Create Context Set Config Entry
    cs_entry_id = "context-set-config"
    cs_name = f"{eg_name}/entries/{cs_entry_id}"
    cs_url = f"{args.endpoint.rstrip('/')}/v1/{eg_name}/entries?entry_id={cs_entry_id}"
    cs_data = {"domainName": args.domain_name, "domainDescription": domain_desc}
    if tables:
      cs_data["dataResourceNames"] = tables

    logging.info("--> [2/3] Uploading Context Set Config Entry: %s", cs_entry_id)
    status, body, elapsed = request(
        cs_url, "POST",
        {
            "name": cs_name,
            "entry_type": f"{parent}/entryTypes/context-set",
            "display_name": f"{args.domain_name} Context Set",
            "description": domain_desc,
            "aspects": {
                cs_aspect_key: {
                    "aspect_type": f"{parent}/aspectTypes/context-set-aspect",
                    "data": cs_data,
                }
            },
        },
        token,
    )
    if status in (200, 201, 409):
      logging.info("Context Set Entry configured in %.2f ms.", elapsed * 1000.0)
    else:
      logging.warning("Context Set Entry warning (Status %d): %s", status, body)

    # 3. Upload Query Templates
    logging.info("--> [3/3] Uploading %d Query Templates...", len(templates))

    for idx, tpl in enumerate(templates, start=1):
      nl = tpl.get("nl_query", f"Template {idx}")
      manifest = tpl.get("manifest") or nl
      raw_sql = tpl.get("sql", "")
      p_dict = tpl.get("parameterized", {})
      p_sql = p_dict.get("parameterized_sql") or raw_sql
      p_intent = p_dict.get("parameterized_intent") or tpl.get("intent", "")

      entry_id = sanitize_id(nl, idx)
      entry_name = f"{eg_name}/entries/{entry_id}"
      entry_url = f"{args.endpoint.rstrip('/')}/v1/{eg_name}/entries?entry_id={entry_id}"

      status, body, elapsed = request(
          entry_url, "POST",
          {
              "name": entry_name,
              "entry_type": f"{parent}/entryTypes/query-template",
              "display_name": nl[:63],
              "description": manifest,
              "aspects": {
                  qt_aspect_key: {
                      "aspect_type": f"{parent}/aspectTypes/query-template-aspect",
                      "data": {
                          "nlQuery": nl,
                          "parameterizedIntent": p_intent,
                          "parameterizedSql": p_sql,
                          "sql": raw_sql,
                      },
                  }
              },
          },
          token,
      )
      upload_latencies.append(elapsed)
      if status in (200, 201):
        uploaded_ids.append(entry_id)
        logging.info("[%d/%d] Entry '%s' uploaded in %.2f ms", idx, len(templates), entry_id, elapsed * 1000.0)
      elif status == 409:
        logging.info("[%d/%d] Entry '%s' already exists (409).", idx, len(templates), entry_id)
        uploaded_ids.append(entry_id)
      else:
        logging.error("[%d/%d] Failed Entry '%s' (Status %d): %s", idx, len(templates), entry_id, status, body)

    # Print resource verification if verbose
    if args.verbose:
      print_resource(args.endpoint, eg_name, token, f"EntryGroup ({args.bundle_id})")
      print_resource(args.endpoint, cs_name, token, f"Context Set Config ({cs_entry_id})")
      if uploaded_ids:
        print_resource(args.endpoint, f"{eg_name}/entries/{uploaded_ids[0]}", token, f"Query Template ({uploaded_ids[0]})")
  else:
    logging.info("--> --search_only mode enabled: Skipping upload.")

  # -------------------------------------------------------------
  # TEMPLATE-SCOPED SEARCH & RECALL@K VERIFICATION PHASE
  # -------------------------------------------------------------
  k = max(1, args.top_k)
  total_runs = max(args.search_iterations, len(test_items))
  logging.info("--> Running Semantic Search (Top K = %d, %d runs across %d queries)...", k, total_runs, len(test_items) if test_items else 1)

  search_latencies = []
  recall_at_k_hits = 0
  total_queries_tested = 0

  items_to_test = test_items if test_items else [{"query": args.search_query or args.domain_name, "expected_id": "", "nl_query": ""}]
  if args.search_query:
    items_to_test = [{"query": args.search_query, "expected_id": test_items[0]["expected_id"] if test_items else "", "nl_query": args.search_query}]

  print("\n" + "-" * 100)
  print(f"{'Run':<5} | {'Search Query':<30} | {'Expected ID':<18} | {'Matched Rank':<14} | {f'Recall@{k}':<10} | {'Latency':<8}")
  print("-" * 100)

  first_fail_body = None

  for i in range(1, total_runs + 1):
    item = items_to_test[(i - 1) % len(items_to_test)]
    q = item["query"]
    expected_id = item["expected_id"]

    status, search_resp, search_elapsed, sent_query = search_templates(
        endpoint=args.endpoint,
        project=args.project,
        location=args.location,
        bundle_id=args.bundle_id,
        query_text=q,
        token=token,
        page_size=k,
    )
    lat_ms = search_elapsed * 1000.0
    search_latencies.append(search_elapsed)

    results = search_resp.get("results", []) if status == 200 else []
    
    # Check if expected_id is within the top K results
    matched_rank = -1
    for rank_idx, res in enumerate(results, start=1):
      entry_name = res.get("dataplexEntry", {}).get("name", "")
      entry_id = entry_name.split("/")[-1] if entry_name else ""
      if expected_id and expected_id in entry_id:
        matched_rank = rank_idx
        break
      elif not expected_id and len(results) > 0:
        matched_rank = 1
        break

    is_hit = matched_rank > 0 and matched_rank <= k
    if is_hit:
      recall_at_k_hits += 1
      rank_str = f"Rank #{matched_rank}"
      status_str = "✅ PASS"
    else:
      rank_str = f"Not in Top {k}" if results else "0 matches"
      status_str = "❌ FAIL"
      if first_fail_body is None:
        first_fail_body = {"status": status, "query": sent_query, "response": search_resp}

    total_queries_tested += 1

    q_snip = (q[:27] + "...") if len(q) > 30 else q
    exp_snip = (expected_id[:15] + "...") if len(expected_id) > 18 else expected_id

    print(f"#{i:<4} | {q_snip:<30} | {exp_snip:<18} | {rank_str:<14} | {status_str:<10} | {lat_ms:<6.1f}ms")

  print("-" * 100)

  # Diagnostic print if verbose or if all failed
  if first_fail_body and recall_at_k_hits == 0:
    print("\n" + "=" * 80)
    print("=== SEARCH DIAGNOSTIC (0 MATCHES RETURNED) ===")
    print("=" * 80)
    print(f"HTTP Status: {first_fail_body['status']}")
    print(f"Sent Query:  '{first_fail_body['query']}'")
    print(f"Raw Response: {json.dumps(first_fail_body['response'], indent=2)}")
    
    # Try broad diagnostic probe with name:*
    print("\n--> Probing with broad wildcard query 'name:*' to inspect indexed entries...")
    diag_status, diag_resp, _, _ = search_templates(args.endpoint, args.project, args.location, args.bundle_id, "name:*", token, page_size=5)
    diag_matches = diag_resp.get("results", [])
    print(f"Wildcard 'name:*' Status: {diag_status} | Total indexed entries found: {len(diag_matches)}")
    for idx, d in enumerate(diag_matches[:3], 1):
      print(f"  [{idx}] {d.get('dataplexEntry', {}).get('name')}")
    print("=" * 80 + "\n")

  # -------------------------------------------------------------
  # PERFORMANCE & ACCURACY REPORT
  # -------------------------------------------------------------
  upload_stats = calculate_stats(upload_latencies)
  search_stats = calculate_stats(search_latencies)
  recall_k_pct = (recall_at_k_hits / total_queries_tested * 100.0) if total_queries_tested else 0.0

  print("\n" + "=" * 80)
  print(f"=== PERFORMANCE & RECALL@{k} BENCHMARK REPORT ===")
  print("=" * 80)
  print(f"Recall@{k} Accuracy (Found in Top {k}): {recall_k_pct:.1f}% ({recall_at_k_hits}/{total_queries_tested})")
  print("-" * 80)
  print(f"{'Metric':<20} | {'Min (ms)':<10} | {'Avg (ms)':<10} | {'P50 (ms)':<10} | {'P90 (ms)':<10} | {'P95 (ms)':<10} | {'Max (ms)':<10}")
  print("-" * 80)
  if not args.search_only:
    print(f"{'Upload Latency':<20} | {upload_stats['min_ms']:<10.2f} | {upload_stats['avg_ms']:<10.2f} | {upload_stats['p50_ms']:<10.2f} | {upload_stats['p90_ms']:<10.2f} | {upload_stats['p95_ms']:<10.2f} | {upload_stats['max_ms']:<10.2f}")
  print(f"{'Search Latency':<20} | {search_stats['min_ms']:<10.2f} | {search_stats['avg_ms']:<10.2f} | {search_stats['p50_ms']:<10.2f} | {search_stats['p90_ms']:<10.2f} | {search_stats['p95_ms']:<10.2f} | {search_stats['max_ms']:<10.2f}")
  print("=" * 80 + "\n")


if __name__ == "__main__":
  main()