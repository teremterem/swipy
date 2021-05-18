from dataclasses import asdict
from typing import List, Dict, Text, Any

import pytest

from actions.user_state_machine import UserStateMachine, UserState


def _populate_user(user_state_machine: UserStateMachine) -> UserStateMachine:
    from actions.aws_resources import user_state_machine_table

    # noinspection PyDataclass
    user_state_machine_table.put_item(Item=asdict(user_state_machine))
    return user_state_machine


@pytest.fixture
def ddb_unit_test_user(create_user_state_machine_table) -> UserStateMachine:
    return _populate_user(UserStateMachine('unit_test_user'))


@pytest.fixture
def ddb_user1(create_user_state_machine_table) -> UserStateMachine:
    return _populate_user(UserStateMachine(
        user_id='existing_user_id1',
        state=UserState.WAITING_PARTNER_ANSWER,
        partner_id='existing_user_id2',
        newbie=False,
    ))


@pytest.fixture
def ddb_user2(create_user_state_machine_table) -> UserStateMachine:
    return _populate_user(UserStateMachine(
        user_id='existing_user_id2',
        state=UserState.ASKED_TO_JOIN,
        partner_id='existing_user_id1',
    ))


@pytest.fixture
def ddb_user3(create_user_state_machine_table) -> UserStateMachine:
    return _populate_user(UserStateMachine(
        user_id='existing_user_id3',
    ))


@pytest.fixture
def ddb_user4(create_user_state_machine_table) -> UserStateMachine:
    return _populate_user(UserStateMachine(
        user_id='existing_user_id4',
        state=UserState.DO_NOT_DISTURB,
    ))


@pytest.fixture
def ddb_available_newbie1(create_user_state_machine_table) -> UserStateMachine:
    return _populate_user(UserStateMachine(
        user_id='available_newbie_id1',
        state=UserState.OK_FOR_CHITCHAT,
        newbie=True,
    ))


@pytest.fixture
def ddb_available_newbie2(create_user_state_machine_table) -> UserStateMachine:
    return _populate_user(UserStateMachine(
        user_id='available_newbie_id2',
        state=UserState.OK_FOR_CHITCHAT,
        newbie=True,
    ))


@pytest.fixture
def ddb_available_newbie3(create_user_state_machine_table) -> UserStateMachine:
    return _populate_user(UserStateMachine(
        user_id='available_newbie_id3',
        state=UserState.OK_FOR_CHITCHAT,
        newbie=True,
    ))


@pytest.fixture
def ddb_available_veteran1(create_user_state_machine_table) -> UserStateMachine:
    return _populate_user(UserStateMachine(
        user_id='available_veteran_id1',
        state=UserState.OK_FOR_CHITCHAT,
        newbie=False,
    ))


@pytest.fixture
def ddb_available_veteran2(create_user_state_machine_table) -> UserStateMachine:
    return _populate_user(UserStateMachine(
        user_id='available_veteran_id2',
        state=UserState.OK_FOR_CHITCHAT,
        newbie=False,
    ))


@pytest.fixture
def ddb_available_veteran3(create_user_state_machine_table) -> UserStateMachine:
    return _populate_user(UserStateMachine(
        user_id='available_veteran_id3',
        state=UserState.OK_FOR_CHITCHAT,
        newbie=False,
    ))


@pytest.fixture
def scan_of_three_users() -> List[Dict[Text, Any]]:
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
def scan_of_ten_users() -> List[Dict[Text, Any]]:
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
