import pytest

from actions.user_state_machine import UserStateMachine, UserState


@pytest.fixture
def unit_test_user() -> UserStateMachine:
    return UserStateMachine(
        user_id='unit_test_user',
        roomed_partner_ids=['roomed_unit_test_partner1', 'roomed_unit_test_partner2'],
        rejected_partner_ids=['rejected_unit_test_partner1', 'rejected_unit_test_partner2'],
        seen_partner_ids=['seen_unit_test_partner1', 'seen_unit_test_partner2'],
    )


@pytest.fixture
def user1() -> UserStateMachine:
    return UserStateMachine(
        user_id='existing_user_id1',
        state=UserState.WAITING_PARTNER_CONFIRM,
        partner_id='existing_user_id2',
        roomed_partner_ids=['roomed_partner1', 'roomed_partner2', 'roomed_partner3'],
        rejected_partner_ids=['rejected_partner1', 'rejected_partner2', 'rejected_partner3'],
        seen_partner_ids=['seen_partner1', 'seen_partner2', 'seen_partner3'],
        newbie=False,
        notes='some note',
    )


@pytest.fixture
def user2() -> UserStateMachine:
    return UserStateMachine(
        user_id='existing_user_id2',
        state=UserState.ASKED_TO_JOIN,
        partner_id='existing_user_id1',
    )


@pytest.fixture
def user3() -> UserStateMachine:
    return UserStateMachine(
        user_id='existing_user_id3',
    )


@pytest.fixture
def user4() -> UserStateMachine:
    return UserStateMachine(
        user_id='existing_user_id4',
        state=UserState.DO_NOT_DISTURB,
    )


@pytest.fixture
def available_newbie1() -> UserStateMachine:
    return UserStateMachine(
        user_id='available_newbie_id1',
        state=UserState.OK_TO_CHITCHAT,
        newbie=True,
    )


@pytest.fixture
def available_newbie2() -> UserStateMachine:
    return UserStateMachine(
        user_id='available_newbie_id2',
        state=UserState.OK_TO_CHITCHAT,
        newbie=True,
    )


@pytest.fixture
def available_newbie3() -> UserStateMachine:
    return UserStateMachine(
        user_id='available_newbie_id3',
        state=UserState.OK_TO_CHITCHAT,
        newbie=True,
    )


@pytest.fixture
def available_veteran1() -> UserStateMachine:
    return UserStateMachine(
        user_id='available_veteran_id1',
        state=UserState.OK_TO_CHITCHAT,
        newbie=False,
    )


@pytest.fixture
def available_veteran2() -> UserStateMachine:
    return UserStateMachine(
        user_id='available_veteran_id2',
        state=UserState.OK_TO_CHITCHAT,
        newbie=False,
    )


@pytest.fixture
def available_veteran3() -> UserStateMachine:
    return UserStateMachine(
        user_id='available_veteran_id3',
        state=UserState.OK_TO_CHITCHAT,
        newbie=False,
    )
