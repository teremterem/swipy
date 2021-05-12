import pytest

from actions.user_state_machine import _UserVault, UserStateMachine


@pytest.fixture
def user_vault():
    return _UserVault()


def test_get_new_user(user_vault):
    assert user_vault._users == {}
    user_state_machine = user_vault.get_user('new_user_id')

    assert user_state_machine.user_id == 'new_user_id'
    assert user_state_machine.state == 'new'
    assert user_state_machine.sub_state is None
    assert user_state_machine.sub_state_expiration is None
    assert user_state_machine.related_user_id is None

    assert user_vault._users['new_user_id'] is user_state_machine
    assert len(user_vault._users) == 1


def test_get_existing_user(user_vault):
    assert user_vault._users == {}
    user_state_machine = UserStateMachine('existing_user_id')
    user_vault._users['existing_user_id'] = user_state_machine

    assert user_vault.get_user('existing_user_id') is user_state_machine
    assert len(user_vault._users) == 1


def test_scenario1():
    """
    user2 -> new
    - user2, do you want to chitchat?
    - no
    - ok to ping you if someone else felt lonely?
    - yes
    user2 -> ok_for_chitchat

    user1 -> new
    - user1, do you want to chitchat?
    """
