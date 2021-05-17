from dataclasses import asdict
from typing import List, Dict, Text, Any

import pytest

from actions.user_vault import UserStateMachine


def _populate_user(user_state_machine: UserStateMachine) -> UserStateMachine:
    from actions.aws_resources import user_state_machine_table

    user_state_machine_table.put_item(Item=asdict(user_state_machine))
    return user_state_machine


@pytest.fixture
def unit_test_user(create_user_state_machine_table) -> UserStateMachine:
    return _populate_user(UserStateMachine('unit_test_user'))


@pytest.fixture
def user1(create_user_state_machine_table) -> UserStateMachine:
    return _populate_user(UserStateMachine(
        user_id='existing_user_id1',
        sub_state='some_sub_state',
    ))


@pytest.fixture
def user2(create_user_state_machine_table) -> UserStateMachine:
    return _populate_user(UserStateMachine('existing_user_id2'))


@pytest.fixture
def user3(create_user_state_machine_table) -> UserStateMachine:
    return _populate_user(UserStateMachine('existing_user_id3'))


@pytest.fixture
def scan_of_three_users() -> List[Dict[Text, Any]]:
    return [
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
    ]
