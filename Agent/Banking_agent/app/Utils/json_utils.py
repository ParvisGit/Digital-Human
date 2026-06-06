import json

def safe_json_load(input_data):
    if isinstance(input_data, dict):
        return input_data
    if isinstance(input_data, str):
        cleaned = input_data.strip()
        if cleaned.startswith("{{") and cleaned.endswith("}}"):
            cleaned = cleaned[1:-1]
        return json.loads(cleaned)
    raise ValueError("Invalid input type")
