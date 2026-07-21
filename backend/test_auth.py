import asyncio
from app.main import app
from fastapi.testclient import TestClient

async def test():
    # Register a user
    client = TestClient(app)
    response = client.post('/api/v1/auth/register', json={
        'email': 'test2@test.com',
        'password': 'password123',
        'full_name': 'Test User'
    })
    print('Registration response:', response.status_code, response.json())

    # Login
    response = client.post('/api/v1/auth/login', json={
        'email': 'test2@test.com',
        'password': 'password123'
    })
    print('Login response:', response.status_code, response.json())

asyncio.run(test())
