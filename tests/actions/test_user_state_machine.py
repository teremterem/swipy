from unittest.mock import patch

import pytest

from actions.user_state_machine import UserVault, UserStateMachine


def test_get_new_user(
        user_vault: UserVault,
):
    assert user_vault._users == {}
    user_state_machine = user_vault.get_user('new_user_id')

    assert user_state_machine.user_id == 'new_user_id'
    assert user_state_machine.state == 'new'
    assert user_state_machine.sub_state is None
    assert user_state_machine.sub_state_expiration is None
    assert user_state_machine.related_user_id is None

    assert user_vault._users['new_user_id'] is user_state_machine
    assert len(user_vault._users) == 1


def test_get_existing_user(
        user_vault: UserVault,
        user1: UserStateMachine,
):
    assert len(user_vault._users) == 1
    assert user_vault.get_user('existing_user_id1') is user1
    assert len(user_vault._users) == 1


@pytest.mark.usefixtures('user1', 'user3')
@patch('actions.user_state_machine.secrets.choice')
def test_get_random_user(
        choice_mock,
        user_vault: UserVault,
        user2: UserStateMachine,
):
    def _choice_mock(inp):
        assert set(inp) == set(user_vault._users.values())
        return user2

    choice_mock.side_effect = _choice_mock

    assert len(user_vault._users) == 3
    assert user_vault.get_random_user() is user2
    assert len(user_vault._users) == 3
