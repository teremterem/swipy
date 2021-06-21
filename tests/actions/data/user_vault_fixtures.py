from dataclasses import asdict
from typing import List, Dict, Text, Any

import pytest

from actions.user_state_machine import UserStateMachine


def _save_user_in_ddb(user_state_machine: UserStateMachine) -> UserStateMachine:
    from actions.aws_resources import user_state_machine_table

    # noinspection PyDataclass
    user_state_machine_table.put_item(Item=asdict(user_state_machine))
    return user_state_machine


@pytest.fixture
def ddb_unit_test_user(
        create_user_state_machine_table: None,
        unit_test_user: UserStateMachine,
) -> UserStateMachine:
    return _save_user_in_ddb(unit_test_user)


@pytest.fixture
def ddb_user1(
        create_user_state_machine_table: None,
        user1: UserStateMachine,
) -> UserStateMachine:
    return _save_user_in_ddb(user1)


@pytest.fixture
def ddb_user2(
        create_user_state_machine_table: None,
        user2: UserStateMachine,
) -> UserStateMachine:
    return _save_user_in_ddb(user2)


@pytest.fixture
def ddb_user3(
        create_user_state_machine_table: None,
        user3: UserStateMachine,
) -> UserStateMachine:
    return _save_user_in_ddb(user3)


@pytest.fixture
def ddb_user4(
        create_user_state_machine_table: None,
        user4: UserStateMachine,
) -> UserStateMachine:
    return _save_user_in_ddb(user4)


@pytest.fixture
def ddb_available_newbie1(
        create_user_state_machine_table: None,
        available_newbie1: UserStateMachine,
) -> UserStateMachine:
    return _save_user_in_ddb(available_newbie1)


@pytest.fixture
def ddb_available_newbie2(
        create_user_state_machine_table: None,
        available_newbie2: UserStateMachine,
) -> UserStateMachine:
    return _save_user_in_ddb(available_newbie2)


@pytest.fixture
def ddb_available_newbie3(
        create_user_state_machine_table: None,
        available_newbie3: UserStateMachine,
) -> UserStateMachine:
    return _save_user_in_ddb(available_newbie3)


@pytest.fixture
def ddb_available_veteran1(
        create_user_state_machine_table: None,
        available_veteran1: UserStateMachine,
) -> UserStateMachine:
    return _save_user_in_ddb(available_veteran1)


@pytest.fixture
def ddb_available_veteran2(
        create_user_state_machine_table: None,
        available_veteran2: UserStateMachine,
) -> UserStateMachine:
    return _save_user_in_ddb(available_veteran2)


@pytest.fixture
def ddb_available_veteran3(
        create_user_state_machine_table: None,
        available_veteran3: UserStateMachine,
) -> UserStateMachine:
    return _save_user_in_ddb(available_veteran3)


@pytest.fixture
def ddb_scan_of_three_users() -> List[Dict[Text, Any]]:
    return [
        {
            'user_id': 'existing_user_id1',
            'state': 'waiting_partner_join',
            'partner_id': 'existing_user_id2',
            'newbie': False,
            'state_timestamp': None,
            'state_timestamp_str': None,
            'state_timeout_ts': None,
            'state_timeout_ts_str': None,
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
            'state_timeout_ts': None,
            'state_timeout_ts_str': None,
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
            'state_timeout_ts': None,
            'state_timeout_ts_str': None,
            'notes': '',
            'deeplink_data': '',
            'native': 'unknown',
            'teleg_lang_code': None,
            'telegram_from': None,
        },
    ]


@pytest.fixture
def user_dicts() -> List[Dict[Text, Any]]:
    return [
        {
            'user_id': 'wants_chitchat_id1',
            'state': 'wants_chitchat',
            'partner_id': 'existing_user_id2',
            'newbie': False,
            'state_timestamp': 1619900555,
            'state_timestamp_str': None,
            'state_timeout_ts': None,
            'state_timeout_ts_str': None,
            'notes': 'some note',
            'deeplink_data': '',
            'native': 'unknown',
            'teleg_lang_code': None,
            'telegram_from': None,
        },
        {
            'user_id': 'wants_chitchat_id2',
            'state': 'wants_chitchat',
            'partner_id': None,
            'newbie': True,
            'state_timestamp': 1619900444,
            'state_timestamp_str': None,
            'state_timeout_ts': None,
            'state_timeout_ts_str': None,
            'notes': '',
            'deeplink_data': '',
            'native': 'unknown',
            'teleg_lang_code': None,
            'telegram_from': None,
        },
        {
            'user_id': 'wants_chitchat_id3',
            'state': 'wants_chitchat',
            'partner_id': None,
            'newbie': False,
            'state_timestamp': 1619900777,
            'state_timestamp_str': None,
            'state_timeout_ts': None,
            'state_timeout_ts_str': None,
            'notes': '',
            'deeplink_data': '',
            'native': 'unknown',
            'teleg_lang_code': None,
            'telegram_from': None,
        },
        {
            'user_id': 'wants_chitchat_id4',
            'state': 'wants_chitchat',
            'partner_id': None,
            'newbie': False,
            'state_timestamp': None,
            'state_timestamp_str': None,
            'state_timeout_ts': None,
            'state_timeout_ts_str': None,
            'notes': '',
            'deeplink_data': '',
            'native': 'unknown',
            'teleg_lang_code': None,
            'telegram_from': None,
        },
        {
            'user_id': 'asked_to_join_id1',
            'state': 'asked_to_join',
            'partner_id': 'existing_user_id1',
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
        },
        {
            'user_id': 'ok_to_chitchat_id1',
            'state': 'ok_to_chitchat',
            'partner_id': None,
            'newbie': True,
            'state_timestamp': 1619900222,
            'state_timestamp_str': None,
            'state_timeout_ts': None,
            'state_timeout_ts_str': None,
            'notes': '',
            'deeplink_data': '',
            'native': 'unknown',
            'teleg_lang_code': None,
            'telegram_from': None,
        },
        {
            'user_id': 'ok_to_chitchat_id2',
            'state': 'ok_to_chitchat',
            'partner_id': None,
            'newbie': False,
            'state_timestamp': 1619900999,
            'state_timestamp_str': None,
            'state_timeout_ts': None,
            'state_timeout_ts_str': None,
            'notes': '',
            'deeplink_data': '',
            'native': 'unknown',
            'teleg_lang_code': None,
            'telegram_from': None,
        },
        {
            'user_id': 'ok_to_chitchat_id3',
            'state': 'ok_to_chitchat',
            'partner_id': None,
            'newbie': True,
            'state_timestamp': 1619909999,
            'state_timestamp_str': None,
            'state_timeout_ts': None,
            'state_timeout_ts_str': None,
            'notes': '',
            'deeplink_data': '',
            'native': 'unknown',
            'teleg_lang_code': None,
            'telegram_from': None,
        },
        {
            'user_id': 'ok_to_chitchat_id4',
            'state': 'ok_to_chitchat',
            'partner_id': None,
            'newbie': False,
            'state_timestamp': 1619900111,
            'state_timestamp_str': None,
            'state_timeout_ts': None,
            'state_timeout_ts_str': None,
            'notes': '',
            'deeplink_data': '',
            'native': 'unknown',
            'teleg_lang_code': None,
            'telegram_from': None,
        },
        {
            'user_id': 'ok_to_chitchat_id5',
            'state': 'ok_to_chitchat',
            'partner_id': None,
            'newbie': False,
            'state_timestamp': None,
            'state_timestamp_str': None,
            'state_timeout_ts': None,
            'state_timeout_ts_str': None,
            'notes': '',
            'deeplink_data': '',
            'native': 'unknown',
            'teleg_lang_code': None,
            'telegram_from': None,
        },
        {
            'user_id': 'new_id1',
            'state': 'new',
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
        },
        {
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
        },
        {
            'user_id': 'roomed_id1',
            'state': 'roomed',
            'partner_id': 'some_partner_id',
            'newbie': True,
            'state_timestamp': 1619900001,
            'state_timestamp_str': None,
            'state_timeout_ts': None,
            'state_timeout_ts_str': None,
            'notes': '',
            'deeplink_data': '',
            'native': 'unknown',
            'teleg_lang_code': None,
            'telegram_from': None,
        },
        {
            'user_id': 'roomed_id2',
            'state': 'roomed',
            'partner_id': 'some_partner_id',
            'newbie': True,
            'state_timestamp': 1622999999,
            'state_timestamp_str': None,
            'state_timeout_ts': 1623999999,
            'state_timeout_ts_str': None,
            'notes': '',
            'deeplink_data': '',
            'native': 'unknown',
            'teleg_lang_code': None,
            'telegram_from': None,
        },
    ]
