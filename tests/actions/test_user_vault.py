from typing import List, Dict, Text, Any
from unittest.mock import patch

import pytest

from actions.user_vault import UserVault, UserStateMachine, DdbUserVault
from actions.user_vault import user_vault as user_vault_singleton


def test_user_vault_singleton() -> None:
    assert UserVault == DdbUserVault
    assert isinstance(user_vault_singleton, UserVault)


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
    from actions.aws_resources import user_state_machine_table

    assert len(user_state_machine_table.scan()['Items']) == 1
    assert user_vault.get_user('existing_user_id1') == user1
    assert len(user_state_machine_table.scan()['Items']) == 1


@pytest.mark.usefixtures('user1', 'user3')
@patch('actions.user_vault.secrets.choice')
def test_get_random_user(
        choice_mock,
        user_vault: UserVault,
        user2: UserStateMachine,
) -> None:
    from actions.aws_resources import user_state_machine_table

    choice_mock.return_value = user2

    assert len(user_state_machine_table.scan()['Items']) == 3

    assert user_vault.get_random_user() is user2

    items = user_state_machine_table.scan()['Items']
    assert len(items) == 3
    choice_mock.assert_called_once_with([UserStateMachine(**item) for item in items])


@pytest.mark.usefixtures('create_user_state_machine_table')
def test_no_random_user(user_vault: UserVault) -> None:
    from actions.aws_resources import user_state_machine_table

    assert not user_state_machine_table.scan()['Items']
    assert user_vault.get_random_user() is None
    assert not user_state_machine_table.scan()['Items']


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


@pytest.mark.usefixtures('user1', 'user2', 'user3')
def test_save_new_user(
        user_vault: UserVault,
        scan_of_three_users: List[Dict[Text, Any]],
) -> None:
    from actions.aws_resources import user_state_machine_table

    assert user_state_machine_table.scan()['Items'] == scan_of_three_users
    user_vault.save_user(UserStateMachine('new_ddb_user_was_put'))
    assert user_state_machine_table.scan()['Items'] == [
        {
            'user_id': 'existing_user_id1',
            'related_user_id': None,
            'state': 'new',
            'sub_state': 'some_sub_state',
            'sub_state_expiration': None,
        },
        {
            'user_id': 'existing_user_id2',
            'related_user_id': None,
            'state': 'new',
            'sub_state': None,
            'sub_state_expiration': None,
        },
        {
            'user_id': 'existing_user_id3',
            'related_user_id': None,
            'state': 'new',
            'sub_state': None,
            'sub_state_expiration': None,
        },
        {
            'user_id': 'new_ddb_user_was_put',
            'related_user_id': None,
            'state': 'new',
            'sub_state': None,
            'sub_state_expiration': None,
        },
    ]


@pytest.mark.usefixtures('user1', 'user2', 'user3')
def test_save_existing_user(
        user_vault: UserVault,
        scan_of_three_users: List[Dict[Text, Any]],
) -> None:
    from actions.aws_resources import user_state_machine_table

    assert user_state_machine_table.scan()['Items'] == scan_of_three_users
    user_vault.save_user(UserStateMachine(user_id='existing_user_id1', state='not_so_new'))
    assert user_state_machine_table.scan()['Items'] == [
        {
            'user_id': 'existing_user_id1',
            'related_user_id': None,
            'state': 'not_so_new',  # the value used to be 'new' but we have overridden it
            'sub_state': None,  # the value used to be 'some_sub_state' but we have overridden it with None
            'sub_state_expiration': None,
        },
        {
            'user_id': 'existing_user_id2',
            'related_user_id': None,
            'state': 'new',
            'sub_state': None,
            'sub_state_expiration': None,
        },
        {
            'user_id': 'existing_user_id3',
            'related_user_id': None,
            'state': 'new',
            'sub_state': None,
            'sub_state_expiration': None,
        },
    ]


def test_ddb_user_vault_list_users(
        user_vault: DdbUserVault,
        user1: UserStateMachine,
        user2: UserStateMachine,
        user3: UserStateMachine,
) -> None:
    assert user_vault._list_users() == [user1, user2, user3]


@pytest.mark.usefixtures('user1', 'user3')
def test_ddb_user_vault_get_existing_user(
        user_vault: DdbUserVault,
        user2: UserStateMachine,
) -> None:
    from actions.aws_resources import user_state_machine_table

    assert len(user_state_machine_table.scan()['Items']) == 3
    assert user_vault._get_user('existing_user_id2') == user2
    assert len(user_state_machine_table.scan()['Items']) == 3


@pytest.mark.usefixtures('user1', 'user2', 'user3')
def test_ddb_user_vault_get_nonexistent_user(user_vault: DdbUserVault) -> None:
    from actions.aws_resources import user_state_machine_table

    assert len(user_state_machine_table.scan()['Items']) == 3
    assert user_vault._get_user('there_is_no_such_user') is None
    assert len(user_state_machine_table.scan()['Items']) == 3
