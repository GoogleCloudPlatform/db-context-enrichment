"""End-to-end smoke test for the Context Store client against autopush.

Exercises both the CSG-create LRO path and the synchronous CS lifecycle.
Every RPC is logged at DEBUG so you can see method, URL, request, response.

Prereq: `gcloud auth application-default login` with quota project
`cloud-db-nl2sql`.

Run from the repo root:
    uv run python scripts/smoke_context_store_client.py
"""

import logging
import time

from google.cloud.db_context_enrichment.common.context_store_client import (
    ContextStoreClient,
)
from google.cloud.db_context_enrichment.model.context import (
    ContextSet,
    ParameterizedTemplate,
    Template,
)

# Surface every HTTP call from the client to stderr. `google-api-core` sets
# `logging.getLogger("google").propagate = False` during its first auth/HTTP
# round-trip, which strands our google.cloud.* logs (they never reach the
# root handler that basicConfig installs). Workaround: attach our own
# handler directly to the `google` logger so propagation stoppage is moot.
_fmt = logging.Formatter("%(asctime)s %(name)s [%(levelname)s] %(message)s")
_handler = logging.StreamHandler()
_handler.setFormatter(_fmt)
_google_logger = logging.getLogger("google")
_google_logger.addHandler(_handler)
_google_logger.setLevel(logging.DEBUG)
# Stop records from propagating to the root logger, which would emit them a
# second time via basicConfig's handler. (google-api-core flips this to False
# itself during its first auth call, but only after a few of our log lines
# have already been double-emitted.)
_google_logger.propagate = False
# Quiet down noisy children we don't care to see.
for noisy in ("google.auth", "google.auth.transport"):
    logging.getLogger(noisy).setLevel(logging.WARNING)
# urllib3 lives outside the `google` namespace; configure it via basicConfig.
logging.basicConfig(level=logging.WARNING, format="%(name)s [%(levelname)s] %(message)s")

CS_ID = "autoctx"


def banner(msg: str) -> None:
    print(f"\n{'=' * 8} {msg} {'=' * 8}")


def main() -> None:
    c = ContextStoreClient(location="us-central1")
    print(f"Project from ADC: {c._project}")

    # Use a timestamped CSG so we always exercise CreateContextSetGroup (LRO).
    run_id = int(time.time())
    csg_id = f"smoke-csg-{run_id}"
    version = f"smoke-{run_id}"

    banner(f"ensure_context_set_group({csg_id})  [LRO]")
    t0 = time.monotonic()
    csg = c.ensure_context_set_group(csg_id)
    print(f"CSG ready in {time.monotonic() - t0:.1f}s: {csg}")

    try:
        ctx = ContextSet(
            templates=[
                Template(
                    nl_query="How many users?",
                    sql="SELECT count(*) FROM users",
                    intent="Count users",
                    manifest="Count rows in users",
                    parameterized=ParameterizedTemplate(
                        parameterized_sql="SELECT count(*) FROM users",
                        parameterized_intent="Count users",
                    ),
                )
            ],
        )

        banner(f"create_context_set({CS_ID}, {version})")
        resource = c.create_context_set(csg, CS_ID, version)
        print(f"Created: {resource}")

        banner("upload_context_set")
        c.upload_context_set(resource, ctx)
        print("Uploaded body")

        banner("download_context_set")
        back = c.download_context_set(resource)
        assert back.model_dump(exclude_none=True) == ctx.model_dump(
            exclude_none=True
        )
        print("Round-trip OK")

        banner("delete_context_set")
        c.delete_context_set(resource)
        print(f"Deleted: {resource}")
    finally:
        # Always tear down the CSG, even if a step above failed.
        banner(f"delete_context_set_group({csg_id})  [LRO]")
        t0 = time.monotonic()
        c.delete_context_set_group(csg)
        print(f"CSG deleted in {time.monotonic() - t0:.1f}s")


if __name__ == "__main__":
    main()
