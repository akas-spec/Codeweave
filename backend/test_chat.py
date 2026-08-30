import urllib.request
import json

req = urllib.request.Request(
    'http://localhost:8000/api/chat',
    data=json.dumps({'question': 'How does routing work?', 'repository_id': 1}).encode('utf-8'),
    headers={'Content-Type': 'application/json'}
)
try:
    with urllib.request.urlopen(req) as response:
        res = json.loads(response.read().decode('utf-8'))
        print(f"Success! Answer length: {len(res.get('answer', ''))}, Sources: {len(res.get('sources', []))}")
except urllib.error.HTTPError as e:
    print(f"HTTP Error {e.code}: {e.read().decode('utf-8')}")
except Exception as e:
    print(f"Error: {e}")
