from unittest.mock import patch

import pytest

from actions.user_state_machine import UserVault, UserStateMachine, user_vault as user_vault_singleton, DdbUserVault


def test_user_vault_singleton() -> None:
    assert isinstance(user_vault_singleton, UserVault)


def test_get_new_user(
        user_vault: UserVault,
) -> None:
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
) -> None:
    assert len(user_vault._users) == 1
    assert user_vault.get_user('existing_user_id1') is user1
    assert len(user_vault._users) == 1


@pytest.mark.usefixtures('user1', 'user3')
@patch('actions.user_state_machine.secrets.choice')
def test_get_random_user(
        choice_mock,
        user_vault: UserVault,
        user2: UserStateMachine,
) -> None:
    choice_mock.return_value = user2

    assert len(user_vault._users) == 3
    assert user_vault.get_random_user() is user2
    assert len(user_vault._users) == 3
    choice_mock.assert_called_once_with(list(user_vault._users.values()))


def test_no_random_user(user_vault: UserVault) -> None:
    assert not user_vault._users
    assert user_vault.get_random_user() is None
    assert not user_vault._users


@patch.object(UserVault, 'get_random_user')
def test_get_random_available_user(
        get_random_user_mock,
        user_vault: UserVault,
        user1: UserStateMachine,
        user2: UserStateMachine,
        user3: UserStateMachine,
) -> None:
    get_random_user_mock.side_effect = [user1, user2, user3]

    assert user_vault.get_random_available_user('existing_user_id1') is user2
    assert get_random_user_mock.call_count == 2


@patch.object(UserVault, 'get_random_user')
def test_no_available_users(
        get_random_user_mock,
        user_vault: UserVault,
        user1: UserStateMachine,
) -> None:
    get_random_user_mock.return_value = user1

    assert user_vault.get_random_available_user('existing_user_id1') is None
    assert get_random_user_mock.call_count == 10


def test_ddb_user_vault_list_users(
        ddb_user_vault: DdbUserVault,
        user1_ddb: UserStateMachine,
        user2_ddb: UserStateMachine,
        user3_ddb: UserStateMachine,
) -> None:
    assert ddb_user_vault._list_users() == [user1_ddb, user2_ddb, user3_ddb]


@pytest.mark.usefixtures('user1', 'user3')
def test_ddb_user_vault_get_user(
        ddb_user_vault: DdbUserVault,
        user2_ddb: UserStateMachine,
) -> None:
    assert ddb_user_vault._get_user('existing_ddb_user_id2') == user2_ddb
