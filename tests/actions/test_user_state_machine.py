from unittest.mock import patch

import pytest

from actions.user_state_machine import UserVault, UserStateMachine, DdbUserVault
from actions.user_state_machine import user_vault as user_vault_singleton


def test_user_vault_singleton() -> None:
    assert isinstance(user_vault_singleton, UserVault)
    assert UserVault == DdbUserVault


@pytest.mark.usefixtures('create_user_state_machine_table')
def test_get_new_user(user_vault: UserVault) -> None:
    from actions.aws_resources import user_state_machine_table

    assert not user_state_machine_table.scan()['Items']

    user_state_machine = user_vault.get_user('new_user_id')

    assert user_state_machine.user_id == 'new_user_id'
    assert user_state_machine.state == 'new'
    assert user_state_machine.sub_state is None
    assert user_state_machine.sub_state_expiration is None
    assert user_state_machine.related_user_id is None

    assert user_state_machine_table.scan()['Items'] == [{
        'user_id': 'new_user_id',
        'related_user_id': None,
        'state': 'new',
        'sub_state': None,
        'sub_state_expiration': None,
    }]


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
    from actions.aws_resources import user_state_machine_table

    assert len(user_state_machine_table.scan()['Items']) == 1
    assert ddb_user_vault._get_user('existing_ddb_user_id2') == user2_ddb
    assert len(user_state_machine_table.scan()['Items']) == 1


@pytest.mark.usefixtures('create_user_state_machine_table')
def test_ddb_user_vault_put_user(
        ddb_user_vault: DdbUserVault,
) -> None:
    from actions.aws_resources import user_state_machine_table

    assert not user_state_machine_table.scan()['Items']
    ddb_user_vault._put_user(UserStateMachine('new_ddb_user_was_put'))
    assert user_state_machine_table.scan()['Items'] == [{
        'user_id': 'new_ddb_user_was_put',
        'related_user_id': None,
        'state': 'new',
        'sub_state': None,
        'sub_state_expiration': None,
    }]
