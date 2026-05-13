from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health():
    res = client.get('/health')
    assert res.status_code == 200
    assert res.json()['status'] == 'ok'

def test_dev_user_and_about():
    assert client.get('/auth/dev-user').json()['email'] == 'demo@example.com'
    about = client.get('/about').json()
    assert about['product'] == 'MyGardenOS'

def test_mock_device_search():
    res = client.get('/devices/search')
    assert res.status_code == 200
    assert isinstance(res.json(), list)
