from dataclasses import asdict
from decimal import Decimal
from typing import List, Dict, Text, Any
from unittest.mock import patch, MagicMock, call, Mock

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

    assert new_user._user_vault is user_vault

    assert new_user.user_id == 'new_user_id'
    assert new_user.state == 'new'
    assert new_user.partner_id is None
    assert new_user.newbie is True

    assert user_state_machine_table.scan()['Items'] == [{
        'user_id': 'new_user_id',
        'state': 'new',
        'partner_id': None,
        'latest_room_name': None,
        'roomed_partner_ids': [],
        'rejected_partner_ids': [],
        'seen_partner_ids': [],
        'newbie': True,
        'state_timestamp': Decimal(0),
        'state_timestamp_str': None,
        'state_timeout_ts': Decimal(0),
        'state_timeout_ts_str': None,
        'activity_timestamp': Decimal(0),
        'activity_timestamp_str': None,
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

    assert fetched_user._user_vault is user_vault

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
    assert actual_random_user._user_vault is user_vault

    mock_get_random_available_partner_dict.assert_called_once_with(
        [
            'wants_chitchat',
            'ok_to_chitchat',
            'waiting_partner_confirm',
            'asked_to_join',
            'asked_to_confirm',
            'roomed',
            'rejected_join',
            'rejected_confirm',
        ],
        'existing_user_id1',
        [
            'existing_user_id1',
            'roomed_partner1',
            'roomed_partner2',
            'roomed_partner3',
            'rejected_partner1',
            'rejected_partner2',
            'rejected_partner3',
        ],
    )

    assert user_vault.get_user(actual_random_user.user_id) is actual_random_user  # make sure the user was cached

    # _get_random_available_partner_from_tiers did not corrupt the original lists by internal concatenation
    assert user1.roomed_partner_ids == ['roomed_partner1', 'roomed_partner2', 'roomed_partner3']
    assert user1.rejected_partner_ids == ['rejected_partner1', 'rejected_partner2', 'rejected_partner3']
    assert user1.seen_partner_ids == ['seen_partner1', 'seen_partner2', 'seen_partner3']


@patch.object(UserVault, '_get_random_available_partner_dict')
def test_get_random_available_partner_none(
        mock_get_random_available_partner_dict: MagicMock,
        user1: UserStateMachine,
) -> None:
    mock_get_random_available_partner_dict.return_value = None

    user_vault = UserVault()
    assert user_vault.get_random_available_partner(user1) is None

    assert mock_get_random_available_partner_dict.mock_calls == [
        call(
            [
                'wants_chitchat',
                'ok_to_chitchat',
                'waiting_partner_confirm',
                'asked_to_join',
                'asked_to_confirm',
                'roomed',
                'rejected_join',
                'rejected_confirm',
            ],
            'existing_user_id1',
            [
                'existing_user_id1',
                'roomed_partner1',
                'roomed_partner2',
                'roomed_partner3',
                'rejected_partner1',
                'rejected_partner2',
                'rejected_partner3',
            ],
        ),
    ]


@pytest.mark.usefixtures('ddb_user1', 'ddb_user2', 'ddb_user3')
def test_save_new_user(ddb_scan_of_three_users: List[Dict[Text, Any]]) -> None:
    from actions.aws_resources import user_state_machine_table

    user_to_save = UserStateMachine(
        user_id='new_ddb_user_was_put',
        notes='some other note',
    )

    assert user_to_save._user_vault is None
    assert user_state_machine_table.scan()['Items'] == ddb_scan_of_three_users

    user_vault = UserVault()
    user_vault.save(user_to_save)

    assert user_to_save._user_vault is user_vault
    assert user_state_machine_table.scan()['Items'] == [
        {
            'user_id': 'existing_user_id1',
            'state': 'waiting_partner_confirm',
            'partner_id': 'existing_user_id2',
            'latest_room_name': None,
            'roomed_partner_ids': ['roomed_partner1', 'roomed_partner2', 'roomed_partner3'],
            'rejected_partner_ids': ['rejected_partner1', 'rejected_partner2', 'rejected_partner3'],
            'seen_partner_ids': ['seen_partner1', 'seen_partner2', 'seen_partner3'],
            'newbie': False,
            'state_timestamp': Decimal(0),
            'state_timestamp_str': None,
            'state_timeout_ts': Decimal(0),
            'state_timeout_ts_str': None,
            'activity_timestamp': Decimal(0),
            'activity_timestamp_str': None,
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
            'latest_room_name': None,
            'roomed_partner_ids': [],
            'rejected_partner_ids': [],
            'seen_partner_ids': [],
            'newbie': True,
            'state_timestamp': Decimal(0),
            'state_timestamp_str': None,
            'state_timeout_ts': Decimal(0),
            'state_timeout_ts_str': None,
            'activity_timestamp': Decimal(0),
            'activity_timestamp_str': None,
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
            'latest_room_name': None,
            'roomed_partner_ids': [],
            'rejected_partner_ids': [],
            'seen_partner_ids': [],
            'newbie': True,
            'state_timestamp': Decimal(0),
            'state_timestamp_str': None,
            'state_timeout_ts': Decimal(0),
            'state_timeout_ts_str': None,
            'activity_timestamp': Decimal(0),
            'activity_timestamp_str': None,
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
            'latest_room_name': None,
            'roomed_partner_ids': [],
            'rejected_partner_ids': [],
            'seen_partner_ids': [],
            'newbie': True,
            'state_timestamp': Decimal(0),
            'state_timestamp_str': None,
            'state_timeout_ts': Decimal(0),
            'state_timeout_ts_str': None,
            'activity_timestamp': Decimal(0),
            'activity_timestamp_str': None,
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

    assert user_to_save._user_vault is None
    assert user_state_machine_table.scan()['Items'] == ddb_scan_of_three_users

    user_vault = UserVault()
    user_vault.save(user_to_save)

    assert user_to_save._user_vault is user_vault
    assert user_state_machine_table.scan()['Items'] == [
        {
            'user_id': 'existing_user_id1',
            'state': 'do_not_disturb',  # used to be 'waiting_partner_join' but we have overridden it
            'partner_id': None,  # used to be 'existing_user_id2' but we have overridden it
            'latest_room_name': None,
            'roomed_partner_ids': [],  # used to contain 3 ids but we have overridden it
            'rejected_partner_ids': [],  # used to contain 3 ids but we have overridden it
            'seen_partner_ids': [],  # used to contain 3 ids but we have overridden it
            'newbie': True,  # used to be False but we have overridden it
            'state_timestamp': Decimal(0),
            'state_timestamp_str': None,
            'state_timeout_ts': Decimal(0),
            'state_timeout_ts_str': None,
            'activity_timestamp': Decimal(0),
            'activity_timestamp_str': None,
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
            'latest_room_name': None,
            'roomed_partner_ids': [],
            'rejected_partner_ids': [],
            'seen_partner_ids': [],
            'newbie': True,
            'state_timestamp': Decimal(0),
            'state_timestamp_str': None,
            'state_timeout_ts': Decimal(0),
            'state_timeout_ts_str': None,
            'activity_timestamp': Decimal(0),
            'activity_timestamp_str': None,
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
            'latest_room_name': None,
            'roomed_partner_ids': [],
            'rejected_partner_ids': [],
            'seen_partner_ids': [],
            'newbie': True,
            'state_timestamp': Decimal(0),
            'state_timestamp_str': None,
            'state_timeout_ts': Decimal(0),
            'state_timeout_ts_str': None,
            'activity_timestamp': Decimal(0),
            'activity_timestamp_str': None,
            'notes': '',
            'deeplink_data': '',
            'native': 'unknown',
            'teleg_lang_code': None,
            'telegram_from': None,
        },
    ]
    assert user_vault.get_user(user_to_save.user_id) is user_to_save  # make sure the user was cached


@pytest.mark.parametrize('current_timestamp, expected_partner_dict', [
    (
            1624000039,  # "roomed" partner was active the most recently and the state has already timed out
            {  # expect "roomed" partner to be returned
                'user_id': 'roomed_id2',
                'state': 'roomed',
                'partner_id': 'some_partner_id',
                'latest_room_name': None,
                'roomed_partner_ids': [],
                'rejected_partner_ids': [],
                'newbie': True,
                'state_timestamp': Decimal(0),
                'state_timestamp_str': None,
                'state_timeout_ts': Decimal(1623999999),
                'state_timeout_ts_str': None,
                'activity_timestamp': Decimal(1622999999),
                'activity_timestamp_str': None,
                'notes': '',
                'deeplink_data': '',
                'native': 'unknown',
                'teleg_lang_code': None,
                'telegram_from': None,
            },
    ),
    (
            1623999990,  # even though "roomed" partner was active the most recently, the state hasn't timed out yet
            {  # expect another recently active partner to be returned
                'user_id': 'ok_to_chitchat_id2',
                'state': 'ok_to_chitchat',
                'partner_id': None,
                'latest_room_name': None,
                'roomed_partner_ids': [],
                'rejected_partner_ids': [],
                'newbie': False,
                'state_timestamp': Decimal(0),
                'state_timestamp_str': None,
                'state_timeout_ts': Decimal(0),
                'state_timeout_ts_str': None,
                'activity_timestamp': Decimal(1619900999),
                'activity_timestamp_str': None,
                'notes': '',
                'deeplink_data': '',
                'native': 'unknown',
                'teleg_lang_code': None,
                'telegram_from': None,
            },
    ),
])
@pytest.mark.usefixtures('create_user_state_machine_table')
def test_ddb_get_random_available_partner_dict(
        user_dicts: List[Dict[Text, Any]],
        current_timestamp: int,
        expected_partner_dict: Dict[Text, Any],
) -> None:
    from actions.aws_resources import user_state_machine_table

    for item in user_dicts:
        user_state_machine_table.put_item(Item=item)
    assert user_state_machine_table.scan()['Items'] == user_dicts  # I don't know why I keep doing this

    user_vault = UserVault()
    with patch('time.time', Mock(return_value=current_timestamp)):
        partner_dict = user_vault._get_random_available_partner_dict(
            ('wants_chitchat', 'ok_to_chitchat', 'fake_state', 'roomed'),  # let's forget about "tiers" here
            'ok_to_chitchat_id3',
            ['roomed_id2_3', 'some_exclude_id', 'ok_to_chitchat_id3', 'ok_to_chitchat_id2_3', 'another_exclude_id'],
        )
    assert partner_dict == expected_partner_dict


@pytest.mark.usefixtures('create_user_state_machine_table')
def test_ddb_get_random_available_partner_dict_none() -> None:
    from actions.aws_resources import user_state_machine_table

    user_state_machine_table.put_item(Item={
        'user_id': 'do_not_disturb_id1',
        'state': 'do_not_disturb',
        'partner_id': None,
        'newbie': True,
        'state_timestamp': 1619999999,
        'state_timestamp_str': None,
        'state_timeout_ts': None,
        'state_timeout_ts_str': None,
        'notes': '',
        'deeplink_data': '',
        'native': 'unknown',
        'teleg_lang_code': None,
        'telegram_from': None,
    })
    assert len(user_state_machine_table.scan()['Items']) == 1  # I don't know why I keep doing this

    user_vault = UserVault()
    partner_dict = user_vault._get_random_available_partner_dict(
        ('wants_chitchat', 'ok_to_chitchat', 'fake_state', 'roomed'),  # let's forget about "tiers" here
        'ok_to_chitchat_id3',
        ['ok_to_chitchat_id3', 'one_more_exclude_id'],
    )
    assert partner_dict is None


@pytest.mark.usefixtures('create_user_state_machine_table')
def test_ddb_get_random_available_partner_dict_current_user_excluded_by_all() -> None:
    from actions.aws_resources import user_state_machine_table

    user_state_machine_table.put_item(Item={
        'user_id': 'roomed_id2_1',
        'state': 'roomed',
        'partner_id': 'some_partner_id',
        'roomed_partner_ids': ['some_excluded_partner'],
        'rejected_partner_ids': ['ok_to_chitchat_id3'],
        'newbie': True,
        'state_timestamp': Decimal(0),
        'state_timestamp_str': None,
        'state_timeout_ts': Decimal(1624000009),
        'state_timeout_ts_str': None,
        'activity_timestamp': Decimal(1623000009),
        'activity_timestamp_str': None,
        'notes': '',
        'deeplink_data': '',
        'native': 'unknown',
        'teleg_lang_code': None,
        'telegram_from': None,
    })
    user_state_machine_table.put_item(Item={
        'user_id': 'ok_to_chitchat_id2_1',
        'state': 'ok_to_chitchat',
        'partner_id': None,
        'roomed_partner_ids': ['ok_to_chitchat_id3', 'excluded_partner1', 'excluded_partner2'],
        'rejected_partner_ids': [],
        'newbie': False,
        'state_timestamp': Decimal(0),
        'state_timestamp_str': None,
        'state_timeout_ts': Decimal(0),
        'state_timeout_ts_str': None,
        'activity_timestamp': Decimal(1619901009),
        'activity_timestamp_str': None,
        'notes': '',
        'deeplink_data': '',
        'native': 'unknown',
        'teleg_lang_code': None,
        'telegram_from': None,
    })
    assert len(user_state_machine_table.scan()['Items']) == 2

    user_vault = UserVault()
    partner_dict = user_vault._get_random_available_partner_dict(
        ('wants_chitchat', 'ok_to_chitchat', 'fake_state', 'roomed'),  # let's forget about "tiers" here
        'ok_to_chitchat_id3',
        ['ok_to_chitchat_id3', 'one_more_exclude_id'],
    )
    assert partner_dict is None


@pytest.mark.usefixtures('ddb_user1', 'ddb_user3')
def test_ddb_get_existing_user(ddb_user2: UserStateMachine) -> None:
    from actions.aws_resources import user_state_machine_table

    assert len(user_state_machine_table.scan()['Items']) == 3
    user_vault = UserVault()
    assert user_vault._get_user('existing_user_id2') == ddb_user2
    assert len(user_state_machine_table.scan()['Items']) == 3


@pytest.mark.usefixtures('ddb_user1', 'ddb_user2', 'ddb_user3')
def test_ddb_get_nonexistent_user() -> None:
    from actions.aws_resources import user_state_machine_table

    assert len(user_state_machine_table.scan()['Items']) == 3
    user_vault = UserVault()
    assert user_vault._get_user('there_is_no_such_user') is None
    assert len(user_state_machine_table.scan()['Items']) == 3
