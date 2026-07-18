import google.auth
import google.auth.transport.requests
import requests
from typing import Dict, Any

def query_data_via_rest(
    project_id: str,
    location: str,
    prompt: str,
    context_dict: Dict[str, Any],
    api_endpoint: str = None
) -> Dict[str, Any]:
    """
    Sends direct REST HTTP request to GDA's queryData endpoint, bypassing gRPC client library constraints.
    """
    # 1. Resolve credentials via GCP Application Default Credentials
    credentials, _ = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    auth_req = google.auth.transport.requests.Request()
    credentials.refresh(auth_req)

    # 2. Build GDA REST Endpoint URL
    host = api_endpoint or "geminidataanalytics.googleapis.com"
    url = f"https://{host}/v1beta/projects/{project_id}/locations/{location}:queryData"

    # 3. Construct JSON Payload directly
    payload = {
        "prompt": prompt,
        "context": context_dict,
        "generationOptions": {
            "generateQueryResult": True,
            "generateExplanation": True,
            "generateDisambiguationQuestion": True
        }
    }
    headers = {
        "Authorization": f"Bearer {credentials.token}",
        "Content-Type": "application/json",
    }

    response = requests.post(url, headers=headers, json=payload, timeout=300)
    if response.status_code >= 400:
        import sys
        print("[ERROR] GDA REST API Response on Error:", response.text)
        sys.stdout.flush()
    response.raise_for_status()
    
    # 4. Map JSON response keys back to standard generator format
    res_json = response.json()
    return {
        "generated_sql": res_json.get("generatedQuery"),
        "other": {
            "intent_explanation": res_json.get("intentExplanation", ""),
            "disambiguation_question": list(res_json.get("disambiguationQuestions", []))
        }
    }
