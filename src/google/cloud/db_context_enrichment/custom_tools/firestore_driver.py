import json
import logging
import time
import urllib.request
import urllib.error
from typing import Any, Callable, Dict, List

import google.auth
from google.auth.transport.requests import Request

logger = logging.getLogger(__name__)

DEFAULT_SANDBOX_ENDPOINT = "test-firestore.sandbox.googleapis.com"
FIRESTORE_SCOPES = [
    "https://www.googleapis.com/auth/datastore",
    "https://www.googleapis.com/auth/cloud-platform",
]


def _get_auth_token() -> str:
    """Acquires and refreshes an OAuth2 access token via Application Default Credentials (ADC)."""
    credentials, _ = google.auth.default(scopes=FIRESTORE_SCOPES)
    if not credentials.valid:
        credentials.refresh(Request())
    return credentials.token


def _execute_pipeline_rest(
    endpoint: str,
    project_id: str,
    database_id: str,
    payload: Dict[str, Any],
    max_retries: int = 3,
) -> Dict[str, Any]:
    """
    Executes a Firestore ExecutePipeline HTTP REST call against the sandbox endpoint.
    Includes exponential backoff retries for transient errors.
    """
    url = f"https://{endpoint}/v1/projects/{project_id}/databases/{database_id}:executePipeline"
    
    token = _get_auth_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "x-goog-request-params": f"project_id={project_id}&database_id={database_id}",
        "x-goog-firestore-api-requester": "querydata",
    }

    json_data = json.dumps(payload).encode("utf-8")
    
    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(url, data=json_data, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=30) as response:
                resp_bytes = response.read()
                return json.loads(resp_bytes.decode("utf-8"))
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="ignore")
            logger.warning(f"ExecutePipeline HTTP {e.code} (attempt {attempt + 1}/{max_retries}): {err_body}")
            if attempt == max_retries - 1:
                raise RuntimeError(f"ExecutePipeline HTTP request failed: {e.code} - {err_body}")
            time.sleep(2 ** attempt)
        except Exception as e:
            logger.warning(f"ExecutePipeline connection error (attempt {attempt + 1}/{max_retries}): {e}")
            if attempt == max_retries - 1:
                raise
            time.sleep(2 ** attempt)

    return {}


def _flatten_schema(fields: Dict[str, Any], prefix: str = "") -> List[Dict[str, str]]:
    """Recursively flattens nested MapValue schema objects into dot-notation field names."""
    columns = []
    if not isinstance(fields, dict):
        return columns

    for name, val in fields.items():
        field_name = f"{prefix}.{name}" if prefix else name
        if not isinstance(val, dict):
            columns.append({"name": field_name, "type": "STRING"})
            continue

        value_type = val.get("valueType") or list(val.keys())[0] if val else "stringValue"

        if value_type == "mapValue":
            map_fields = val.get("mapValue", {}).get("fields", {})
            columns.extend(_flatten_schema(map_fields, field_name))
        else:
            data_type = val.get("stringValue") or value_type.replace("Value", "").upper()
            columns.append({"name": field_name, "type": data_type})

    return columns


def make_list_collections_tool(tool_doc: Dict[str, Any], source_info: Dict[str, Any]) -> Callable:
    """Factory creating the firestore-list-collections MCP tool function."""
    tool_name = tool_doc.get("name", "firestore-list-collections")
    description = tool_doc.get("description", "List document collection schemas from Firestore.")
    
    project_id = source_info.get("project", "cloud-db-nl2sql")
    database_id = source_info.get("database", "nl2sql-mflix")
    endpoint = source_info.get("endpoint", DEFAULT_SANDBOX_ENDPOINT)
    configured_collections = source_info.get("collections") or source_info.get("table_ids") or []

    async def firestore_list_collections(collection_names: List[str] | None = None) -> str:
        target_collections = collection_names or configured_collections
        if not target_collections:
            target_collections = ["movies", "users", "comments", "customers", "orders", "products"]

        database_path = f"projects/{project_id}/databases/{database_id}"
        schema_output = []

        for col_id in target_collections:
            get_schema_str = json.dumps({"collection": col_id, "semantics": "mongodb"})
            payload = {
                "database": database_path,
                "structuredPipeline": {
                    "pipeline": {
                        "stages": [
                            {
                                "name": "get_schema",
                                "args": [
                                    {"stringValue": get_schema_str}
                                ],
                            }
                        ]
                    }
                },
            }

            try:
                result = _execute_pipeline_rest(endpoint, project_id, database_id, payload)
                results = result.get("results", []) or result.get("responses", [])
                
                columns = []
                for doc in results:
                    fields = doc.get("fields", {})
                    columns.extend(_flatten_schema(fields))

                schema_output.append({
                    "collection": col_id,
                    "columns": columns if columns else [{"name": "_id", "type": "STRING"}],
                })
            except Exception as e:
                logger.error(f"Error fetching schema for collection '{col_id}': {e}")
                schema_output.append({
                    "collection": col_id,
                    "error": str(e),
                    "columns": [{"name": "_id", "type": "STRING"}],
                })

        return json.dumps(schema_output, indent=2)

    firestore_list_collections.__name__ = tool_name.replace("-", "_")
    firestore_list_collections.__doc__ = description
    return firestore_list_collections


def make_execute_mongodb_tool(tool_doc: Dict[str, Any], source_info: Dict[str, Any]) -> Callable:
    """Factory creating the firestore-execute-mongodb MCP tool function."""
    tool_name = tool_doc.get("name", "firestore-execute-mongodb")
    description = tool_doc.get("description", "Execute MongoDB JSON queries against Firestore.")

    project_id = source_info.get("project", "cloud-db-nl2sql")
    database_id = source_info.get("database", "nl2sql-mflix")
    endpoint = source_info.get("endpoint", DEFAULT_SANDBOX_ENDPOINT)

    async def firestore_execute_mongodb(query: str) -> str:
        database_path = f"projects/{project_id}/databases/{database_id}"
        payload = {
            "database": database_path,
            "structuredPipeline": {
                "pipeline": {
                    "stages": [
                        {
                            "name": "iql",
                            "args": [
                                {"stringValue": query}
                            ],
                        }
                    ]
                },
                "options": {
                    "read_only": {
                        "booleanValue": True
                    }
                },
            },
        }

        try:
            result = _execute_pipeline_rest(endpoint, project_id, database_id, payload)
            results = result.get("results", [])
            return json.dumps({"status": "SUCCESS", "count": len(results), "results": results}, indent=2)
        except Exception as e:
            return json.dumps({"status": "ERROR", "error": str(e)}, indent=2)

    firestore_execute_mongodb.__name__ = tool_name.replace("-", "_")
    firestore_execute_mongodb.__doc__ = description
    return firestore_execute_mongodb
