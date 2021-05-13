import pytest

from actions.user_state_machine import UserVault


@pytest.fixture
def user_vault() -> UserVault:
    return UserVault()
