import requests
import json
import sys

url = "http://127.0.0.1:8005/api/meal-plans/generate-v2"
payload = {
    "days": 2,
    "diet_type": "standard",
    "servings": 2,
    "meals_per_day": 1
}
headers = {
    "Content-Type": "application/json"
}

print(f"Sending request to {url}")
try:
    response = requests.post(url, json=payload)
    print(f"Status Code: {response.status_code}")
    print(json.dumps(response.json(), indent=2))
    if response.status_code != 200:
        sys.exit(1)
except Exception as e:
    print(f"Failed: {e}")
    sys.exit(1)
