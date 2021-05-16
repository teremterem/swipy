from dataclasses import asdict
from typing import Text

import pytest

from actions.user_state_machine import UserStateMachine


def _populate_user(user_id: Text) -> UserStateMachine:
    from actions.aws_resources import user_state_machine_table

    user_state_machine = UserStateMachine(user_id)
    user_state_machine_table.put_item(Item=asdict(user_state_machine))
    return user_state_machine


@pytest.fixture
def unit_test_user(create_user_state_machine_table) -> UserStateMachine:
    return _populate_user('unit_test_user')


@pytest.fixture
def user1(create_user_state_machine_table) -> UserStateMachine:
    return _populate_user('existing_user_id1')


@pytest.fixture
def user2(create_user_state_machine_table) -> UserStateMachine:
    return _populate_user('existing_user_id2')


@pytest.fixture
def user3(create_user_state_machine_table) -> UserStateMachine:
    return _populate_user('existing_user_id3')
