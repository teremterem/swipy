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
def ddb_unit_test_user(create_user_state_machine_table: None, unit_test_user: UserStateMachine) -> UserStateMachine:
    return _save_user_in_ddb(unit_test_user)


@pytest.fixture
def ddb_user1(create_user_state_machine_table: None, user1: UserStateMachine) -> UserStateMachine:
    return _save_user_in_ddb(user1)


@pytest.fixture
def ddb_user2(create_user_state_machine_table: None, user2: UserStateMachine) -> UserStateMachine:
    return _save_user_in_ddb(user2)


@pytest.fixture
def ddb_user3(create_user_state_machine_table: None, user3: UserStateMachine) -> UserStateMachine:
    return _save_user_in_ddb(user3)


@pytest.fixture
def ddb_user4(create_user_state_machine_table: None, user4: UserStateMachine) -> UserStateMachine:
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
    ]


@pytest.fixture
def ddb_scan_of_ten_users() -> List[Dict[Text, Any]]:
    return [
        {
            'user_id': 'existing_user_id1',
            'state': 'waiting_partner_answer',
            'partner_id': 'existing_user_id2',
            'newbie': False,
        },
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
            'user_id': 'existing_user_id2',
            'state': 'asked_to_join',
            'partner_id': 'existing_user_id1',
            'newbie': True,
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
            'user_id': 'existing_user_id3',
            'state': 'new',
            'partner_id': None,
            'newbie': True,
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
        {
            'user_id': 'existing_user_id4',
            'state': 'do_not_disturb',
            'partner_id': None,
            'newbie': True,
        },
    ]
