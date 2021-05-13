import pytest

from actions.user_state_machine import UserVault, UserStateMachine


def test_get_new_user(user_vault: UserVault):
    assert user_vault._users == {}
    user_state_machine = user_vault.get_user('new_user_id')

    assert user_state_machine.user_id == 'new_user_id'
    assert user_state_machine.state == 'new'
    assert user_state_machine.sub_state is None
    assert user_state_machine.sub_state_expiration is None
    assert user_state_machine.related_user_id is None

    assert user_vault._users['new_user_id'] is user_state_machine
    assert len(user_vault._users) == 1


def test_get_existing_user(user_vault: UserVault):
    assert user_vault._users == {}
    user_state_machine = UserStateMachine('existing_user_id')
    user_vault._users['existing_user_id'] = user_state_machine

    assert user_vault.get_user('existing_user_id') is user_state_machine
    assert len(user_vault._users) == 1
