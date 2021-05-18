from typing import List, Dict, Text, Any
from unittest.mock import patch

import pytest

from actions.user_state_machine import UserStateMachine, UserState
from actions.user_vault import UserVault, DdbUserVault
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
    assert user_state_machine.related_user_id is None
    assert user_state_machine.newbie is True

    assert user_state_machine_table.scan()['Items'] == [{
        'user_id': 'new_user_id',
        'state': 'new',
        'related_user_id': None,
        'newbie': True,
    }]


def test_get_existing_user(
        user_vault: UserVault,
        ddb_user1: UserStateMachine,
) -> None:
    from actions.aws_resources import user_state_machine_table

    assert len(user_state_machine_table.scan()['Items']) == 1
    assert user_vault.get_user('existing_user_id1') == ddb_user1
    assert len(user_state_machine_table.scan()['Items']) == 1


@pytest.mark.usefixtures('ddb_user1', 'ddb_user3')
@patch('actions.user_vault.secrets.choice')
def test_get_random_user(
        choice_mock,
        user_vault: UserVault,
        ddb_user2: UserStateMachine,
) -> None:
    from actions.aws_resources import user_state_machine_table

    choice_mock.return_value = ddb_user2

    assert len(user_state_machine_table.scan()['Items']) == 3

    assert user_vault.get_random_user() is ddb_user2

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
        ddb_user1: UserStateMachine,
        ddb_user2: UserStateMachine,
        ddb_user3: UserStateMachine,
) -> None:
    get_random_user_mock.side_effect = [ddb_user1, ddb_user2, ddb_user3]

    assert user_vault.get_random_available_user('existing_user_id1') is ddb_user2
    assert get_random_user_mock.call_count == 2


@patch.object(UserVault, 'get_random_user')
def test_no_available_users(
        get_random_user_mock,
        user_vault: UserVault,
        ddb_user1: UserStateMachine,
) -> None:
    get_random_user_mock.return_value = ddb_user1

    assert user_vault.get_random_available_user('existing_user_id1') is None
    assert get_random_user_mock.call_count == 10


@pytest.mark.usefixtures('ddb_user1', 'ddb_user2', 'ddb_user3')
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
            'state': 'waiting_partner_answer',
            'related_user_id': 'some_related_user_id',
            'newbie': False,
        },
        {
            'user_id': 'existing_user_id2',
            'state': 'new',
            'related_user_id': None,
            'newbie': True,
        },
        {
            'user_id': 'existing_user_id3',
            'state': 'new',
            'related_user_id': None,
            'newbie': True,
        },
        {
            'user_id': 'new_ddb_user_was_put',
            'state': 'new',
            'related_user_id': None,
            'newbie': True,
        },
    ]


@pytest.mark.usefixtures('ddb_user1', 'ddb_user2', 'ddb_user3')
def test_save_existing_user(
        user_vault: UserVault,
        scan_of_three_users: List[Dict[Text, Any]],
) -> None:
    from actions.aws_resources import user_state_machine_table

    assert user_state_machine_table.scan()['Items'] == scan_of_three_users
    user_vault.save_user(UserStateMachine(
        user_id='existing_user_id1',
        state=UserState.DO_NOT_DISTURB,
    ))
    assert user_state_machine_table.scan()['Items'] == [
        {
            'user_id': 'existing_user_id1',
            'state': 'do_not_disturb',  # used to be 'waiting_partner_answer' but we have overridden it
            'related_user_id': None,  # used to be 'some_related_user_id' but we have overridden it
            'newbie': True,  # used to be False but we have overridden it
        },
        {
            'user_id': 'existing_user_id2',
            'state': 'new',
            'related_user_id': None,
            'newbie': True,
        },
        {
            'user_id': 'existing_user_id3',
            'state': 'new',
            'related_user_id': None,
            'newbie': True,
        },
    ]


def test_ddb_user_vault_list_users(
        user_vault: DdbUserVault,
        ddb_user1: UserStateMachine,
        ddb_user2: UserStateMachine,
        ddb_user3: UserStateMachine,
) -> None:
    assert user_vault._list_users() == [ddb_user1, ddb_user2, ddb_user3]


@pytest.mark.usefixtures('ddb_user1', 'ddb_user3')
def test_ddb_user_vault_get_existing_user(
        user_vault: DdbUserVault,
        ddb_user2: UserStateMachine,
) -> None:
    from actions.aws_resources import user_state_machine_table

    assert len(user_state_machine_table.scan()['Items']) == 3
    assert user_vault._get_user('existing_user_id2') == ddb_user2
    assert len(user_state_machine_table.scan()['Items']) == 3


@pytest.mark.usefixtures('ddb_user1', 'ddb_user2', 'ddb_user3')
def test_ddb_user_vault_get_nonexistent_user(user_vault: DdbUserVault) -> None:
    from actions.aws_resources import user_state_machine_table

    assert len(user_state_machine_table.scan()['Items']) == 3
    assert user_vault._get_user('there_is_no_such_user') is None
    assert len(user_state_machine_table.scan()['Items']) == 3
