import pytest


@pytest.mark.django_db
def test_swagger_docs_endpoint_returns_success(client):
    response = client.get("/api/docs/")
    assert response.status_code == 200
