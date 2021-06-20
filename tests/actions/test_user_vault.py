from dataclasses import asdict
from typing import List, Dict, Text, Any, Optional
from unittest.mock import patch, MagicMock, call

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
        'state_timestamp': None,
        'state_timestamp_str': None,
        'notes': '',
        'deeplink_data': '',
        'native': 'unknown',
        'teleg_lang_code': None,
        'telegram_from': None,
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


@patch.object(UserVault, '_get_random_available_partner_dict')
def test_get_random_available_partner(
        mock_get_random_available_partner_dict: MagicMock,
        user1: UserStateMachine,
        user2: UserStateMachine,
) -> None:
    # noinspection PyDataclass
    mock_get_random_available_partner_dict.return_value = asdict(user2)

    user_vault = UserVault()
    actual_random_user = user_vault.get_random_available_partner(user1)
    assert actual_random_user == user2

    mock_get_random_available_partner_dict.assert_called_once_with(('wants_chitchat',), 'existing_user_id1')

    assert user_vault.get_user(actual_random_user.user_id) is actual_random_user  # make sure the user was cached


@patch.object(UserVault, '_query_user_dicts')
@patch('actions.user_vault.secrets.choice')
@pytest.mark.parametrize('empty_list_variant', [[], None])
def test_no_available_partner(
        mock_choice: MagicMock,
        mock_list_available_user_dicts: MagicMock,
        user1: UserStateMachine,
        empty_list_variant: Optional[list],
) -> None:
    mock_list_available_user_dicts.return_value = empty_list_variant
    mock_choice.side_effect = ValueError("secrets.choice shouldn't have been called with None or empty list")

    user_vault = UserVault()
    assert user_vault.get_random_available_partner(user1) is None

    assert mock_list_available_user_dicts.mock_calls == [
        call(('wants_chitchat',), 'existing_user_id1'),
        call(('ok_to_chitchat',), 'existing_user_id1'),
        call(('roomed',), 'existing_user_id1'),
    ]
    mock_choice.assert_not_called()


@pytest.mark.usefixtures('ddb_user1', 'ddb_user2', 'ddb_user3')
def test_save_new_user(ddb_scan_of_three_users: List[Dict[Text, Any]]) -> None:
    from actions.aws_resources import user_state_machine_table

    user_to_save = UserStateMachine(
        user_id='new_ddb_user_was_put',
        notes='some other note',
    )

    assert user_state_machine_table.scan()['Items'] == ddb_scan_of_three_users
    user_vault = UserVault()
    user_vault.save(user_to_save)
    assert user_state_machine_table.scan()['Items'] == [
        {
            'user_id': 'existing_user_id1',
            'state': 'waiting_partner_join',
            'partner_id': 'existing_user_id2',
            'newbie': False,
            'state_timestamp': None,
            'state_timestamp_str': None,
            'notes': 'some note',
            'deeplink_data': '',
            'native': 'unknown',
            'teleg_lang_code': None,
            'telegram_from': None,
        },
        {
            'user_id': 'existing_user_id2',
            'state': 'asked_to_join',
            'partner_id': 'existing_user_id1',
            'newbie': True,
            'state_timestamp': None,
            'state_timestamp_str': None,
            'notes': '',
            'deeplink_data': '',
            'native': 'unknown',
            'teleg_lang_code': None,
            'telegram_from': None,
        },
        {
            'user_id': 'existing_user_id3',
            'state': 'new',
            'partner_id': None,
            'newbie': True,
            'state_timestamp': None,
            'state_timestamp_str': None,
            'notes': '',
            'deeplink_data': '',
            'native': 'unknown',
            'teleg_lang_code': None,
            'telegram_from': None,
        },
        {
            'user_id': 'new_ddb_user_was_put',
            'state': 'new',
            'partner_id': None,
            'newbie': True,
            'state_timestamp': None,
            'state_timestamp_str': None,
            'notes': 'some other note',
            'deeplink_data': '',
            'native': 'unknown',
            'teleg_lang_code': None,
            'telegram_from': None,
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
            'state': 'do_not_disturb',  # used to be 'waiting_partner_join' but we have overridden it
            'partner_id': None,  # used to be 'existing_user_id2' but we have overridden it
            'newbie': True,  # used to be False but we have overridden it
            'state_timestamp': None,
            'state_timestamp_str': None,
            'notes': '',  # TODO oleksandr: note value is lost in this case... should I worry about it ?
            'deeplink_data': '',
            'native': 'unknown',
            'teleg_lang_code': None,
            'telegram_from': None,
        },
        {
            'user_id': 'existing_user_id2',
            'state': 'asked_to_join',
            'partner_id': 'existing_user_id1',
            'newbie': True,
            'state_timestamp': None,
            'state_timestamp_str': None,
            'notes': '',
            'deeplink_data': '',
            'native': 'unknown',
            'teleg_lang_code': None,
            'telegram_from': None,
        },
        {
            'user_id': 'existing_user_id3',
            'state': 'new',
            'partner_id': None,
            'newbie': True,
            'state_timestamp': None,
            'state_timestamp_str': None,
            'notes': '',
            'deeplink_data': '',
            'native': 'unknown',
            'teleg_lang_code': None,
            'telegram_from': None,
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
@pytest.mark.parametrize('exclude_user_id, expected_ddb_scan', [
    (
            'available_veteran_id2',
            [
                {
                    'user_id': 'available_newbie_id1',
                    'state': 'ok_to_chitchat',
                    'partner_id': None,
                    'newbie': True,
                    'state_timestamp': None,
                    'state_timestamp_str': None,
                    'notes': '',
                    'deeplink_data': '',
                    'native': 'unknown',
                    'teleg_lang_code': None,
                    'telegram_from': None,
                },
                {
                    'user_id': 'available_veteran_id1',
                    'state': 'ok_to_chitchat',
                    'partner_id': None,
                    'newbie': False,
                    'state_timestamp': None,
                    'state_timestamp_str': None,
                    'notes': '',
                    'deeplink_data': '',
                    'native': 'unknown',
                    'teleg_lang_code': None,
                    'telegram_from': None,
                },
                {
                    'user_id': 'available_newbie_id2',
                    'state': 'ok_to_chitchat',
                    'partner_id': None,
                    'newbie': True,
                    'state_timestamp': None,
                    'state_timestamp_str': None,
                    'notes': '',
                    'deeplink_data': '',
                    'native': 'unknown',
                    'teleg_lang_code': None,
                    'telegram_from': None,
                },
                {
                    'user_id': 'available_newbie_id3',
                    'state': 'ok_to_chitchat',
                    'partner_id': None,
                    'newbie': True,
                    'state_timestamp': None,
                    'state_timestamp_str': None,
                    'notes': '',
                    'deeplink_data': '',
                    'native': 'unknown',
                    'teleg_lang_code': None,
                    'telegram_from': None,
                },
                {
                    'user_id': 'available_veteran_id3',
                    'state': 'ok_to_chitchat',
                    'partner_id': None,
                    'newbie': False,
                    'state_timestamp': None,
                    'state_timestamp_str': None,
                    'notes': '',
                    'deeplink_data': '',
                    'native': 'unknown',
                    'teleg_lang_code': None,
                    'telegram_from': None,
                },
            ],
    ),
    (
            'existing_user_id1',
            [
                {
                    'user_id': 'available_newbie_id1',
                    'state': 'ok_to_chitchat',
                    'partner_id': None,
                    'newbie': True,
                    'state_timestamp': None,
                    'state_timestamp_str': None,
                    'notes': '',
                    'deeplink_data': '',
                    'native': 'unknown',
                    'teleg_lang_code': None,
                    'telegram_from': None,
                },
                {
                    'user_id': 'available_veteran_id1',
                    'state': 'ok_to_chitchat',
                    'partner_id': None,
                    'newbie': False,
                    'state_timestamp': None,
                    'state_timestamp_str': None,
                    'notes': '',
                    'deeplink_data': '',
                    'native': 'unknown',
                    'teleg_lang_code': None,
                    'telegram_from': None,
                },
                {
                    'user_id': 'available_newbie_id2',
                    'state': 'ok_to_chitchat',
                    'partner_id': None,
                    'newbie': True,
                    'state_timestamp': None,
                    'state_timestamp_str': None,
                    'notes': '',
                    'deeplink_data': '',
                    'native': 'unknown',
                    'teleg_lang_code': None,
                    'telegram_from': None,
                },
                {
                    'user_id': 'available_veteran_id2',
                    'state': 'ok_to_chitchat',
                    'partner_id': None,
                    'newbie': False,
                    'state_timestamp': None,
                    'state_timestamp_str': None,
                    'notes': '',
                    'deeplink_data': '',
                    'native': 'unknown',
                    'teleg_lang_code': None,
                    'telegram_from': None,
                },
                {
                    'user_id': 'available_newbie_id3',
                    'state': 'ok_to_chitchat',
                    'partner_id': None,
                    'newbie': True,
                    'state_timestamp': None,
                    'state_timestamp_str': None,
                    'notes': '',
                    'deeplink_data': '',
                    'native': 'unknown',
                    'teleg_lang_code': None,
                    'telegram_from': None,
                },
                {
                    'user_id': 'available_veteran_id3',
                    'state': 'ok_to_chitchat',
                    'partner_id': None,
                    'newbie': False,
                    'state_timestamp': None,
                    'state_timestamp_str': None,
                    'notes': '',
                    'deeplink_data': '',
                    'native': 'unknown',
                    'teleg_lang_code': None,
                    'telegram_from': None,
                },
            ],
    ),
])
def test_ddb_user_vault_query_user_dicts(
        ddb_scan_of_ten_users: List[Dict[Text, Any]],
        exclude_user_id: Text,
        expected_ddb_scan: List[Dict[Text, Any]],
) -> None:
    from actions.aws_resources import user_state_machine_table

    assert user_state_machine_table.scan()['Items'] == ddb_scan_of_ten_users
    user_vault = UserVault()
    actual_ddb_scan = user_vault._query_user_dicts(
        ('wants_chitchat', 'ok_to_chitchat', 'roomed'),
        exclude_user_id=exclude_user_id,
    )
    assert actual_ddb_scan == expected_ddb_scan


@pytest.mark.usefixtures(
    'ddb_user1',
    'ddb_user2',
    'ddb_user3',
)
def test_ddb_user_vault_query_users_dicts_none_available(ddb_scan_of_three_users: List[Dict[Text, Any]]) -> None:
    from actions.aws_resources import user_state_machine_table

    assert user_state_machine_table.scan()['Items'] == ddb_scan_of_three_users
    user_vault = UserVault()
    assert user_vault._query_user_dicts(
        ('wants_chitchat', 'ok_to_chitchat', 'roomed'),
        exclude_user_id='existing_user_id1',
    ) == []


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
