import requests

url = 'http://localhost:11434/api/generate'
payload = {
    'model': 'phi3',
    'prompt': 'test',
    'temperature': 0.0,
    'max_tokens': 10,
    'stream': False,
}

try:
    response = requests.post(url, json=payload, timeout=10)
    print('STATUS', response.status_code)
    print('TEXT', response.text)
except Exception as exc:
    print('ERROR', repr(exc))
