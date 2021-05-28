from dataclasses import asdict
from typing import List, Dict, Text, Any, Optional
from unittest.mock import patch, MagicMock

import pytest

from actions.user_state_machine import UserStateMachine, UserState
from actions.user_vault import UserVault, NaiveDdbUserVault


def test_user_vault_implementation_class() -> None:
    assert UserVault == NaiveDdbUserVault


@pytest.mark.usefixtures('create_user_state_machine_table')
def test_get_new_user() -> None:
    from actions.aws_resources import user_state_machine_table

    assert not user_state_machine_table.scan()['Items']

    user_vault = UserVault()
    new_user = user_vault.get_user('new_user_id')

    assert new_user.user_id == 'new_user_id'
    assert new_user.state == 'new'
    assert new_user.partner_id is None
    assert new_user.newbie is True

    assert user_state_machine_table.scan()['Items'] == [{
        'user_id': 'new_user_id',
        'state': 'new',
        'partner_id': None,
        'newbie': True,
    }]
    assert user_vault.get_user('new_user_id') is new_user  # make sure the user was cached


def test_get_existing_user(ddb_user1: UserStateMachine) -> None:
    from actions.aws_resources import user_state_machine_table

    assert len(user_state_machine_table.scan()['Items']) == 1
    user_vault = UserVault()
    fetched_user = user_vault.get_user('existing_user_id1')
    assert fetched_user == ddb_user1
    assert len(user_state_machine_table.scan()['Items']) == 1
    assert user_vault.get_user('existing_user_id1') is fetched_user  # make sure the user was cached


def test_get_user_empty_id() -> None:
    user_vault = UserVault()
    with pytest.raises(ValueError):
        user_vault.get_user('')


@patch.object(UserVault, '_get_user')
def test_get_user_from_cache(
        mock_ddb_get_user: MagicMock,
        user1: UserStateMachine,
) -> None:
    mock_ddb_get_user.return_value = user1

    user_vault = UserVault()
    assert user_vault.get_user('existing_user_id1') is user1
    mock_ddb_get_user.assert_called_once_with('existing_user_id1')
    assert user_vault.get_user('existing_user_id1') is user1
    mock_ddb_get_user.assert_called_once_with('existing_user_id1')  # it should still be one call in total


@patch.object(UserVault, '_get_user')
def test_user_vault_cache_not_reused_between_instances(
        mock_ddb_get_user: MagicMock,
        user1: UserStateMachine,
) -> None:
    mock_ddb_get_user.return_value = user1
    user_id = 'existing_user_id1'

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
        mock_choice: MagicMock,
        mock_list_available_user_dicts: MagicMock,
        ddb_user1: UserStateMachine,
        ddb_user2: UserStateMachine,
        ddb_user3: UserStateMachine,
        newbie_filter: Optional[bool],
) -> None:
    # noinspection PyDataclass
    list_of_dicts = [asdict(ddb_user1), asdict(ddb_user2), asdict(ddb_user3)]

    mock_list_available_user_dicts.return_value = list_of_dicts
    mock_choice.return_value = list_of_dicts[1]

    user_vault = UserVault()
    actual_random_user = user_vault.get_random_available_user(
        exclude_user_id='existing_user_id1',
        newbie=newbie_filter,
    )
    assert actual_random_user == ddb_user2

    mock_list_available_user_dicts.assert_called_once_with(
        exclude_user_id='existing_user_id1',
        newbie=newbie_filter,
    )
    mock_choice.assert_called_once_with(list_of_dicts)

    assert user_vault.get_user(actual_random_user.user_id) is actual_random_user  # make sure the user was cached


@pytest.mark.parametrize('newbie_filter', [True, False, None])
@pytest.mark.parametrize('empty_list_variant', [[], None])
@patch.object(UserVault, '_list_available_user_dicts')
@patch('actions.user_vault.secrets.choice')
def test_no_available_user(
        mock_choice: MagicMock,
        mock_list_available_user_dicts: MagicMock,
        newbie_filter: Optional[bool],
        empty_list_variant: Optional[list],
) -> None:
    mock_list_available_user_dicts.return_value = empty_list_variant
    mock_choice.side_effect = ValueError("secrets.choice shouldn't have been called with None or empty list")

    user_vault = UserVault()
    assert user_vault.get_random_available_user(
        'existing_user_id1',
        newbie=newbie_filter,
    ) is None

    mock_list_available_user_dicts.assert_called_once_with(
        exclude_user_id='existing_user_id1',
        newbie=newbie_filter,
    )
    mock_choice.assert_not_called()


@pytest.mark.usefixtures('ddb_user1', 'ddb_user2', 'ddb_user3')
def test_save_new_user(ddb_scan_of_three_users: List[Dict[Text, Any]]) -> None:
    from actions.aws_resources import user_state_machine_table

    user_to_save = UserStateMachine('new_ddb_user_was_put')

    assert user_state_machine_table.scan()['Items'] == ddb_scan_of_three_users
    user_vault = UserVault()
    user_vault.save(user_to_save)
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
    assert user_vault.get_user(user_to_save.user_id) is user_to_save  # make sure the user was cached


@pytest.mark.usefixtures('ddb_user1', 'ddb_user2', 'ddb_user3')
def test_save_existing_user(ddb_scan_of_three_users: List[Dict[Text, Any]]) -> None:
    from actions.aws_resources import user_state_machine_table

    user_to_save = UserStateMachine(
        user_id='existing_user_id1',
        state=UserState.DO_NOT_DISTURB,
    )

    assert user_state_machine_table.scan()['Items'] == ddb_scan_of_three_users
    user_vault = UserVault()
    user_vault.save(user_to_save)
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
    assert user_vault.get_user(user_to_save.user_id) is user_to_save  # make sure the user was cached


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
                    'state': 'ok_to_chitchat',
                    'partner_id': None,
                    'newbie': True,
                },
                {
                    'user_id': 'available_newbie_id3',
                    'state': 'ok_to_chitchat',
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
                    'state': 'ok_to_chitchat',
                    'partner_id': None,
                    'newbie': False,
                },
                {
                    'user_id': 'available_veteran_id3',
                    'state': 'ok_to_chitchat',
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
                    'state': 'ok_to_chitchat',
                    'partner_id': None,
                    'newbie': True,
                },
                {
                    'user_id': 'available_veteran_id1',
                    'state': 'ok_to_chitchat',
                    'partner_id': None,
                    'newbie': False,
                },
                {
                    'user_id': 'available_newbie_id2',
                    'state': 'ok_to_chitchat',
                    'partner_id': None,
                    'newbie': True,
                },
                {
                    'user_id': 'available_veteran_id2',
                    'state': 'ok_to_chitchat',
                    'partner_id': None,
                    'newbie': False,
                },
                {
                    'user_id': 'available_newbie_id3',
                    'state': 'ok_to_chitchat',
                    'partner_id': None,
                    'newbie': True,
                },
                {
                    'user_id': 'available_veteran_id3',
                    'state': 'ok_to_chitchat',
                    'partner_id': None,
                    'newbie': False,
                },
            ],
    ),
])
def test_ddb_user_vault_list_available_user_dicts(
        ddb_scan_of_ten_users: List[Dict[Text, Any]],
        newbie_filter: bool,
        exclude_user_id: Text,
        expected_ddb_scan: List[Dict[Text, Any]],
) -> None:
    from actions.aws_resources import user_state_machine_table

    assert user_state_machine_table.scan()['Items'] == ddb_scan_of_ten_users
    user_vault = UserVault()
    assert user_vault._list_available_user_dicts(exclude_user_id, newbie=newbie_filter) == expected_ddb_scan


@pytest.mark.parametrize('newbie_filter', [True, False, None])
@pytest.mark.usefixtures(
    'ddb_user1',
    'ddb_user2',
    'ddb_user3',
)
def test_ddb_user_vault_list_no_available_users_dicts(
        newbie_filter: Optional[bool],
        ddb_scan_of_three_users: List[Dict[Text, Any]],
) -> None:
    from actions.aws_resources import user_state_machine_table

    assert user_state_machine_table.scan()['Items'] == ddb_scan_of_three_users
    user_vault = UserVault()
    assert user_vault._list_available_user_dicts('existing_user_id1', newbie=newbie_filter) == []


@pytest.mark.usefixtures('ddb_user1', 'ddb_user3')
def test_ddb_user_vault_get_existing_user(ddb_user2: UserStateMachine) -> None:
    from actions.aws_resources import user_state_machine_table

    assert len(user_state_machine_table.scan()['Items']) == 3
    user_vault = UserVault()
    assert user_vault._get_user('existing_user_id2') == ddb_user2
    assert len(user_state_machine_table.scan()['Items']) == 3


@pytest.mark.usefixtures('ddb_user1', 'ddb_user2', 'ddb_user3')
def test_ddb_user_vault_get_nonexistent_user() -> None:
    from actions.aws_resources import user_state_machine_table

    assert len(user_state_machine_table.scan()['Items']) == 3
    user_vault = UserVault()
    assert user_vault._get_user('there_is_no_such_user') is None
    assert len(user_state_machine_table.scan()['Items']) == 3
