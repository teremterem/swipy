import pytest

from actions.user_state_machine import _UserVault, UserStateMachine


@pytest.fixture
def user_vault():
    return _UserVault()


def test_get_new_user(user_vault):
    assert user_vault._users == {}
    user_state_machine = user_vault.get_user('new_user_id')

    assert user_state_machine.id == 'new_user_id'
    assert user_state_machine.state == 'new'
    assert user_state_machine.sub_state is None
    assert user_state_machine.sub_state_with_whom is None
    assert user_state_machine.sub_state_expiration is None

    assert user_vault._users['new_user_id'] is user_state_machine


def test_get_existing_user(user_vault):
    assert user_vault._users == {}
    user_state_machine = UserStateMachine('existing_user_id')
    user_vault._users['existing_user_id'] = user_state_machine

    assert user_vault.get_user('existing_user_id') is user_state_machine
