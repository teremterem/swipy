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
    user1 -> new
    - user1, do you want to chitchat?
    - no
    - ok to ping you if someone else felt lonely?
    - yes
    user1 -> ok_for_chitchat

    user2 -> new
    - user2, do you want to chitchat?
    - yes
    - let me find someone, I will get back to you soon
    user2 -> wants_chitchat

    more than 5(?) minutes have passed for user2 (multiple potential partners were asked and timed out)

    user1 -> ok_for_chitchat
    - user1, there is someone, who would like to chitchat, are you in?
    - yes
    - ok, let me check if they are ready too... will send you a video chat link soon.
    """
