from typing import Text

import pytest

from actions.user_state_machine import UserVault, UserStateMachine


@pytest.fixture
def user_vault() -> UserVault:
    return UserVault()


def _populate_user(
        user_vault: UserVault,
        user_id: Text,
):
    user_state_machine = UserStateMachine(user_id)
    user_vault._users[user_id] = user_state_machine
    return user_state_machine


@pytest.fixture
def user1(user_vault: UserVault) -> UserStateMachine:
    return _populate_user(user_vault, 'existing_user_id1')


@pytest.fixture
def user2(user_vault: UserVault) -> UserStateMachine:
    return _populate_user(user_vault, 'existing_user_id2')


@pytest.fixture
def user3(user_vault: UserVault) -> UserStateMachine:
    return _populate_user(user_vault, 'existing_user_id3')
