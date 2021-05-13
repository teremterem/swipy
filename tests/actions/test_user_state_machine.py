import pytest

from actions.user_state_machine import UserVault, UserStateMachine


def test_get_new_user(
        user_vault: UserVault,
):
    assert user_vault._users == {}
    user_state_machine = user_vault.get_user('new_user_id')

    assert user_state_machine.user_id == 'new_user_id'
    assert user_state_machine.state == 'new'
    assert user_state_machine.sub_state is None
    assert user_state_machine.sub_state_expiration is None
    assert user_state_machine.related_user_id is None

    assert user_vault._users['new_user_id'] is user_state_machine
    assert len(user_vault._users) == 1


def test_get_existing_user(
        user_vault: UserVault,
        user1: UserStateMachine,
):
    assert len(user_vault._users) == 1
    assert user_vault.get_user('existing_user_id1') is user1
    assert len(user_vault._users) == 1


@pytest.mark.usefixtures('user1', 'user3')
def test_get_random_user(
        user_vault: UserVault,
        user2: UserStateMachine,
):
    assert len(user_vault._users) == 3
    assert user_vault.get_random_user() is user2
    assert len(user_vault._users) == 3
