import pytest
from aioresponses import aioresponses

pytest_plugins = [
    "tests.actions.data.user_state_machine_fixtures",
]


@pytest.fixture
def mock_aioresponses() -> aioresponses:
    with aioresponses() as m:
        yield m
