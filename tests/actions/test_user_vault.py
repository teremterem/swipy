from dataclasses import asdict
from typing import List, Dict, Text, Any, Optional
from unittest.mock import patch, MagicMock

import pytest

from actions.user_state_machine import UserStateMachine, UserState
from actions.user_vault import UserVault, DdbUserVault


def test_user_vault_implementation_class() -> None:
    assert UserVault == DdbUserVault


@pytest.mark.usefixtures('create_user_state_machine_table')
def test_get_new_user(user_vault: UserVault) -> None:
    from actions.aws_resources import user_state_machine_table

    assert not user_state_machine_table.scan()['Items']

    user_state_machine = user_vault.get_user('new_user_id')

    assert user_state_machine.user_id == 'new_user_id'
    assert user_state_machine.state == 'new'
    assert user_state_machine.partner_id is None
    assert user_state_machine.newbie is True

    assert user_state_machine_table.scan()['Items'] == [{
        'user_id': 'new_user_id',
        'state': 'new',
        'partner_id': None,
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


@patch.object(UserVault, '_get_user')
def test_get_user_from_cache(
        mock_ddb_get_user: MagicMock,
        user_vault: UserVault,
        user1: UserStateMachine,
) -> None:
    mock_ddb_get_user.return_value = user1

    assert user_vault.get_user('existing_user_id1') is user1
    mock_ddb_get_user.assert_called_once_with('existing_user_id1')
    assert user_vault.get_user('existing_user_id1') is user1
    mock_ddb_get_user.assert_called_once_with('existing_user_id1')  # it should still be one call in total


@patch.object(UserVault, '_get_user')
def test_user_vault_cache_isolation(
        mock_ddb_get_user: MagicMock,
        user3: UserStateMachine,
) -> None:
    mock_ddb_get_user.return_value = user3
    user_id = 'existing_user_id3'

    user_vault1 = UserVault()
    user_vault2 = UserVault()

    user_vault1.get_user(user_id)
    assert mock_ddb_get_user.call_count == 1
    user_vault1.get_user(user_id)
    assert mock_ddb_get_user.call_count == 1

    user_vault2.get_user(user_id)
    assert mock_ddb_get_user.call_count == 2
    user_vault2.get_user(user_id)
    assert mock_ddb_get_user.call_count == 2


@pytest.mark.parametrize('newbie_filter', [True, False, None])
@patch.object(UserVault, '_list_available_user_dicts')
@patch('actions.user_vault.secrets.choice')
def test_get_random_available_user(
        choice_mock: MagicMock,
        list_available_user_dicts_mock: MagicMock,
        user_vault: UserVault,
        user1: UserStateMachine,
        user2: UserStateMachine,
        user3: UserStateMachine,
        newbie_filter: Optional[bool],
) -> None:
    # noinspection PyDataclass
    list_of_dicts = [asdict(user1), asdict(user2), asdict(user3)]

    list_available_user_dicts_mock.return_value = list_of_dicts
    choice_mock.return_value = list_of_dicts[1]

    assert user_vault.get_random_available_user('existing_user_id1', newbie=newbie_filter) == user2

    list_available_user_dicts_mock.assert_called_once_with('existing_user_id1', newbie=newbie_filter)
    choice_mock.assert_called_once_with(list_of_dicts)


@pytest.mark.parametrize('newbie_filter', [True, False, None])
@pytest.mark.parametrize('empty_list_variant', [[], None])
@patch.object(UserVault, '_list_available_user_dicts')
@patch('actions.user_vault.secrets.choice')
def test_no_available_user(
        choice_mock: MagicMock,
        list_available_user_dicts_mock: MagicMock,
        user_vault: UserVault,
        newbie_filter: Optional[bool],
        empty_list_variant: Optional[list],
) -> None:
    list_available_user_dicts_mock.return_value = empty_list_variant
    choice_mock.side_effect = ValueError("secrets.choice shouldn't have been called with None or empty list")

    assert user_vault.get_random_available_user('existing_user_id1', newbie=newbie_filter) is None

    list_available_user_dicts_mock.assert_called_once_with('existing_user_id1', newbie=newbie_filter)
    choice_mock.assert_not_called()


@pytest.mark.usefixtures('ddb_user1', 'ddb_user2', 'ddb_user3')
def test_save_new_user(
        user_vault: UserVault,
        ddb_scan_of_three_users: List[Dict[Text, Any]],
) -> None:
    from actions.aws_resources import user_state_machine_table

    assert user_state_machine_table.scan()['Items'] == ddb_scan_of_three_users
    user_vault.save_user(UserStateMachine('new_ddb_user_was_put'))
    assert user_state_machine_table.scan()['Items'] == [
        {
            'user_id': 'existing_user_id1',
            'state': 'waiting_partner_answer',
            'partner_id': 'existing_user_id2',
            'newbie': False,
        },
        {
            'user_id': 'existing_user_id2',
            'state': 'asked_to_join',
            'partner_id': 'existing_user_id1',
            'newbie': True,
        },
        {
            'user_id': 'existing_user_id3',
            'state': 'new',
            'partner_id': None,
            'newbie': True,
        },
        {
            'user_id': 'new_ddb_user_was_put',
            'state': 'new',
            'partner_id': None,
            'newbie': True,
        },
    ]


@pytest.mark.usefixtures('ddb_user1', 'ddb_user2', 'ddb_user3')
def test_save_existing_user(
        user_vault: UserVault,
        ddb_scan_of_three_users: List[Dict[Text, Any]],
) -> None:
    from actions.aws_resources import user_state_machine_table

    assert user_state_machine_table.scan()['Items'] == ddb_scan_of_three_users
    user_vault.save_user(UserStateMachine(
        user_id='existing_user_id1',
        state=UserState.DO_NOT_DISTURB,
    ))
    assert user_state_machine_table.scan()['Items'] == [
        {
            'user_id': 'existing_user_id1',
            'state': 'do_not_disturb',  # used to be 'waiting_partner_answer' but we have overridden it
            'partner_id': None,  # used to be 'existing_user_id2' but we have overridden it
            'newbie': True,  # used to be False but we have overridden it
        },
        {
            'user_id': 'existing_user_id2',
            'state': 'asked_to_join',
            'partner_id': 'existing_user_id1',
            'newbie': True,
        },
        {
            'user_id': 'existing_user_id3',
            'state': 'new',
            'partner_id': None,
            'newbie': True,
        },
    ]


@pytest.mark.usefixtures(
    'ddb_user1',
    'ddb_available_newbie1',
    'ddb_available_veteran1',
    'ddb_user2',
    'ddb_available_newbie2',
    'ddb_available_veteran2',
    'ddb_user3',
    'ddb_available_newbie3',
    'ddb_available_veteran3',
    'ddb_user4',
)
@pytest.mark.parametrize('newbie_filter, exclude_user_id, expected_ddb_scan', [
    (
            True,
            'available_newbie_id2',
            [
                {
                    'user_id': 'available_newbie_id1',
                    'state': 'ok_for_chitchat',
                    'partner_id': None,
                    'newbie': True,
                },
                {
                    'user_id': 'available_newbie_id3',
                    'state': 'ok_for_chitchat',
                    'partner_id': None,
                    'newbie': True,
                },
            ],
    ),
    (
            False,
            'available_veteran_id2',
            [
                {
                    'user_id': 'available_veteran_id1',
                    'state': 'ok_for_chitchat',
                    'partner_id': None,
                    'newbie': False,
                },
                {
                    'user_id': 'available_veteran_id3',
                    'state': 'ok_for_chitchat',
                    'partner_id': None,
                    'newbie': False,
                },
            ],
    ),
    (
            None,
            'existing_user_id1',
            [
                {
                    'user_id': 'available_newbie_id1',
                    'state': 'ok_for_chitchat',
                    'partner_id': None,
                    'newbie': True,
                },
                {
                    'user_id': 'available_veteran_id1',
                    'state': 'ok_for_chitchat',
                    'partner_id': None,
                    'newbie': False,
                },
                {
                    'user_id': 'available_newbie_id2',
                    'state': 'ok_for_chitchat',
                    'partner_id': None,
                    'newbie': True,
                },
                {
                    'user_id': 'available_veteran_id2',
                    'state': 'ok_for_chitchat',
                    'partner_id': None,
                    'newbie': False,
                },
                {
                    'user_id': 'available_newbie_id3',
                    'state': 'ok_for_chitchat',
                    'partner_id': None,
                    'newbie': True,
                },
                {
                    'user_id': 'available_veteran_id3',
                    'state': 'ok_for_chitchat',
                    'partner_id': None,
                    'newbie': False,
                },
            ],
    ),
])
def test_ddb_user_vault_list_available_user_dicts(
        user_vault: UserVault,
        ddb_scan_of_ten_users: List[Dict[Text, Any]],
        newbie_filter: bool,
        exclude_user_id: Text,
        expected_ddb_scan: List[Dict[Text, Any]],
) -> None:
    from actions.aws_resources import user_state_machine_table

    assert user_state_machine_table.scan()['Items'] == ddb_scan_of_ten_users
    assert user_vault._list_available_user_dicts(exclude_user_id, newbie=newbie_filter) == expected_ddb_scan


@pytest.mark.parametrize('newbie_filter', [True, False, None])
@pytest.mark.usefixtures(
    'ddb_user1',
    'ddb_user2',
    'ddb_user3',
)
def test_ddb_user_vault_list_no_available_users_dicts(
        newbie_filter: Optional[bool],
        user_vault: UserVault,
        ddb_scan_of_three_users: List[Dict[Text, Any]],
) -> None:
    from actions.aws_resources import user_state_machine_table

    assert user_state_machine_table.scan()['Items'] == ddb_scan_of_three_users
    assert user_vault._list_available_user_dicts('existing_user_id1', newbie=newbie_filter) == []


@pytest.mark.usefixtures('ddb_user1', 'ddb_user3')
def test_ddb_user_vault_get_existing_user(
        user_vault: UserVault,
        ddb_user2: UserStateMachine,
) -> None:
    from actions.aws_resources import user_state_machine_table

    assert len(user_state_machine_table.scan()['Items']) == 3
    assert user_vault._get_user('existing_user_id2') == ddb_user2
    assert len(user_state_machine_table.scan()['Items']) == 3


@pytest.mark.usefixtures('ddb_user1', 'ddb_user2', 'ddb_user3')
def test_ddb_user_vault_get_nonexistent_user(user_vault: UserVault) -> None:
    from actions.aws_resources import user_state_machine_table

    assert len(user_state_machine_table.scan()['Items']) == 3
    assert user_vault._get_user('there_is_no_such_user') is None
    assert len(user_state_machine_table.scan()['Items']) == 3
