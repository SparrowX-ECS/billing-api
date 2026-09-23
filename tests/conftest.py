from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient

from app import create_app


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def client(tmp_path, anyio_backend: str) -> AsyncGenerator[AsyncClient, None]:
    application = create_app(f"sqlite:///{tmp_path / 'test.db'}", enable_metrics=False)
    async with AsyncClient(transport=ASGITransport(app=application), base_url="http://test") as test_client:
        yield test_client
