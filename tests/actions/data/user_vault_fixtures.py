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
        state=UserState.OK_FOR_CHITCHAT,
        related_user_id='some_related_user_id',
    ))


@pytest.fixture
def ddb_user2(create_user_state_machine_table) -> UserStateMachine:
    return _populate_user(UserStateMachine('existing_user_id2'))


@pytest.fixture
def ddb_user3(create_user_state_machine_table) -> UserStateMachine:
    return _populate_user(UserStateMachine('existing_user_id3'))


@pytest.fixture
def scan_of_three_users() -> List[Dict[Text, Any]]:
    return [
        {
            'user_id': 'existing_user_id1',
            'state': 'ok_for_chitchat',
            'related_user_id': 'some_related_user_id',
        },
        {
            'user_id': 'existing_user_id2',
            'state': 'new',
            'related_user_id': None,
        },
        {
            'user_id': 'existing_user_id3',
            'state': 'new',
            'related_user_id': None,
        },
    ]
