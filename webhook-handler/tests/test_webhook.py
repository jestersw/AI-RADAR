import requests, json

def test_health():
    resp = requests.get('http://localhost:5000/health')
    assert resp.status_code == 200

def test_metrics():
    resp = requests.get('http://localhost:5000/metrics')
    assert resp.status_code == 200

# Для интеграции: тест call webhook с валидным payload сделать позже
