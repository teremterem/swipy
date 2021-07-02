import re
import uuid
from copy import deepcopy
from dataclasses import asdict
from typing import Dict, Text, Any, List, Callable, Tuple, Optional
from unittest.mock import patch, AsyncMock, MagicMock, call, Mock

import pytest
from aioresponses import aioresponses
from aioresponses.core import RequestCall
from rasa_sdk import Tracker
from rasa_sdk.events import SessionStarted, ActionExecuted, SlotSet, EventType, UserUtteranceReverted
from rasa_sdk.executor import CollectingDispatcher
from yarl import URL

from actions import actions, daily_co
from actions.user_state_machine import UserStateMachine, UserState
from actions.user_vault import UserVault, IUserVault


@pytest.mark.asyncio
@pytest.mark.usefixtures('ddb_unit_test_user', 'wrap_traceback_format_exception')
async def test_action_swiper_error_trace(
        tracker: Tracker,
        dispatcher: CollectingDispatcher,
        domain: Dict[Text, Any],
) -> None:
    class SomeSwiperAction(actions.BaseSwiperAction):
        def name(self) -> Text:
            return 'some_swiper_action'

        def should_update_user_activity_timestamp(self, _tracker: Tracker) -> bool:
            return False

        async def swipy_run(
                self, _dispatcher: CollectingDispatcher,
                _tracker: Tracker,
                _domain: Dict[Text, Any],
                _current_user: UserStateMachine,
                _user_vault: IUserVault,
        ) -> List[Dict[Text, Any]]:
            raise ValueError('something got out of hand')

    actual_events = await SomeSwiperAction().run(dispatcher, tracker, domain)
    assert actual_events == [
        SlotSet('swiper_action_result', 'error'),
        SlotSet(
            'swiper_error',
            "ValueError('something got out of hand')",
        ),
        SlotSet('swiper_error_trace', 'stack trace goes here'),
        SlotSet('swiper_state', 'new'),
    ]
    assert dispatcher.messages == [{
        'attachment': None,
        'buttons': [],
        'custom': {},
        'elements': [],
        'image': None,
        'response': 'utter_error',
        'template': 'utter_error',
        'text': None,
    }]


@pytest.mark.asyncio
@patch.object(UserVault, '_get_user')
async def test_user_vault_cache_not_reused_between_action_runs(
        mock_user_vault_get_user: MagicMock,
        tracker: Tracker,
        dispatcher: CollectingDispatcher,
        domain: Dict[Text, Any],
        ddb_unit_test_user: UserStateMachine,
) -> None:
    mock_user_vault_get_user.return_value = ddb_unit_test_user

    class SomeSwiperAction(actions.BaseSwiperAction):
        def name(self) -> Text:
            return 'some_swiper_action'

        def should_update_user_activity_timestamp(self, _tracker: Tracker) -> bool:
            return False

        async def swipy_run(
                self, _dispatcher: CollectingDispatcher,
                _tracker: Tracker,
                _domain: Dict[Text, Any],
                _current_user: UserStateMachine,
                _user_vault: IUserVault,
        ) -> List[Dict[Text, Any]]:
            _user_vault.get_user('unit_test_user')
            _user_vault.get_user('unit_test_user')
            _user_vault.get_user(_tracker.sender_id)  # which is also 'unit_test_user'
            _user_vault.get_user(_tracker.sender_id)  # which is also 'unit_test_user'
            return []

    action = SomeSwiperAction()

    await action.run(dispatcher, tracker, domain)
    assert mock_user_vault_get_user.mock_calls == [
        call('unit_test_user'),
    ]

    await action.run(dispatcher, tracker, domain)
    assert mock_user_vault_get_user.mock_calls == [
        call('unit_test_user'),
        call('unit_test_user'),  # new run should use new cache
    ]


@pytest.mark.asyncio
@pytest.mark.usefixtures('ddb_unit_test_user')
async def test_common_swiper_slots_are_set_after_action_run(
        tracker: Tracker,
        dispatcher: CollectingDispatcher,
        domain: Dict[Text, Any],
) -> None:
    class SomeSwiperAction(actions.BaseSwiperAction):
        def name(self) -> Text:
            return 'some_swiper_action'

        def should_update_user_activity_timestamp(self, _tracker: Tracker) -> bool:
            return False

        async def swipy_run(
                self, _dispatcher: CollectingDispatcher,
                _tracker: Tracker,
                _domain: Dict[Text, Any],
                _current_user: UserStateMachine,
                _user_vault: IUserVault,
        ) -> List[Dict[Text, Any]]:
            assert _current_user.user_id == 'unit_test_user'
            assert _current_user.state == 'new'
            assert _current_user.partner_id is None

            _user_vault.save(UserStateMachine(
                user_id=_current_user.user_id,
                state=UserState.OK_TO_CHITCHAT,
                partner_id='some_partner_id',
            ))  # save a completely different instance of the current user
            return []

    action = SomeSwiperAction()

    actual_events = await action.run(dispatcher, tracker, domain)
    assert actual_events == [
        SlotSet('swiper_state', 'ok_to_chitchat'),  # the action is expected to use the most recent value of state
        SlotSet('partner_id', 'some_partner_id'),  # the action is expected to use the most recent value of partner_id
    ]
    assert dispatcher.messages == []


@pytest.mark.asyncio
@pytest.mark.usefixtures('ddb_unit_test_user')
async def test_action_session_start_without_slots(
        tracker: Tracker,
        dispatcher: CollectingDispatcher,
        domain: Dict[Text, Any],
) -> None:
    action = actions.ActionSessionStart()
    assert action.name() == 'action_session_start'

    tracker.slots.clear()
    actual_events = await action.run(dispatcher, tracker, domain)
    assert actual_events == [
        SessionStarted(),
        SlotSet('swiper_state', 'new'),  # state taken from UserVault
        ActionExecuted('action_listen'),
    ]
    assert dispatcher.messages == []


@pytest.mark.asyncio
@pytest.mark.parametrize('carry_over_slots_to_new_session, expected_events', [
    (
            True,
            [
                SessionStarted(),
                SlotSet('session_started_metadata', None),  # comes from tests/actions/data/initial_tracker.json
                SlotSet('room_url', None),  # comes from tests/actions/data/initial_tracker.json
                SlotSet('my_slot', 'value'),
                SlotSet('another-slot', 'value2'),
                # two more events (swiper_state slot and action_listen) are appended inside the test itself
            ],
    ),
    (
            False,
            [
                SessionStarted(),
                # two more events (swiper_state slot and action_listen) are appended inside the test itself
            ],
    ),
])
@pytest.mark.usefixtures('create_user_state_machine_table')
async def test_action_session_start_with_slots(
        tracker: Tracker,
        dispatcher: CollectingDispatcher,
        domain: Dict[Text, Any],
        carry_over_slots_to_new_session: bool,
        expected_events: List[EventType],
) -> None:
    from actions.aws_resources import user_state_machine_table
    # noinspection PyDataclass
    user_state_machine_table.put_item(Item=asdict(UserStateMachine(
        user_id='unit_test_user',
        state=UserState.OK_TO_CHITCHAT,
    )))

    # set a few slots on tracker
    tracker.add_slots([
        SlotSet('my_slot', 'value'),
        SlotSet('swiper_state', 'do_not_disturb'),  # expected to be replaced rather than carried over
        SlotSet('partner_id', 'some_old_partner'),  # expected to be replaced rather than carried over
        SlotSet('another-slot', 'value2'),
    ])

    domain['session_config']['carry_over_slots_to_new_session'] = carry_over_slots_to_new_session
    expected_events = expected_events + [
        SlotSet('swiper_state', 'ok_to_chitchat'),  # state taken from UserVault rather than carried over
        SlotSet('partner_id', None),  # partner_id taken from UserVault rather than carried over
        ActionExecuted(action_name='action_listen'),
    ]

    assert await actions.ActionSessionStart().run(dispatcher, tracker, domain) == expected_events
    assert dispatcher.messages == []


@pytest.mark.asyncio
@pytest.mark.usefixtures('create_user_state_machine_table')
@patch('time.time', Mock(return_value=1619945501))
@pytest.mark.parametrize('latest_intent, expected_response_template, source_swiper_state, destination_swiper_state', [
    ('how_it_works', 'utter_how_it_works', 'new', 'ok_to_chitchat'),
    ('start', 'utter_greet_offer_chitchat', 'new', 'ok_to_chitchat'),
    ('greet', 'utter_greet_offer_chitchat', 'new', 'ok_to_chitchat'),

    ('greet', 'utter_greet_offer_chitchat', None, 'ok_to_chitchat'),  # user does not exist yet
    ('greet', 'utter_greet_offer_chitchat', 'new', 'ok_to_chitchat'),
    ('greet', 'utter_greet_offer_chitchat', 'wants_chitchat', 'wants_chitchat'),
    ('greet', 'utter_greet_offer_chitchat', 'ok_to_chitchat', 'ok_to_chitchat'),
    ('greet', 'utter_greet_offer_chitchat', 'waiting_partner_confirm', 'waiting_partner_confirm'),
    ('greet', 'utter_greet_offer_chitchat', 'asked_to_join', 'ok_to_chitchat'),
    ('greet', 'utter_greet_offer_chitchat', 'asked_to_confirm', 'ok_to_chitchat'),
    ('greet', 'utter_greet_offer_chitchat', 'roomed', 'ok_to_chitchat'),
    ('greet', 'utter_greet_offer_chitchat', 'rejected_join', 'ok_to_chitchat'),
    ('greet', 'utter_greet_offer_chitchat', 'rejected_confirm', 'ok_to_chitchat'),
    ('greet', 'utter_greet_offer_chitchat', 'do_not_disturb', 'ok_to_chitchat'),
])
async def test_action_offer_chitchat(
        tracker: Tracker,
        dispatcher: CollectingDispatcher,
        domain: Dict[Text, Any],
        latest_intent: Text,
        expected_response_template: Text,
        source_swiper_state: Optional[Text],
        destination_swiper_state: Text,
) -> None:
    if source_swiper_state:
        user_vault = UserVault()
        user_vault.save(UserStateMachine(
            user_id='unit_test_user',
            state=source_swiper_state,
            partner_id=None,
            newbie=True,
            state_timestamp=1619945501,
            state_timestamp_str='2021-05-02 08:51:41 Z',
        ))

    tracker.latest_message = {'intent_ranking': [{'name': latest_intent}]}

    action = actions.ActionOfferChitchat()
    assert action.name() == 'action_offer_chitchat'

    actual_events = await action.run(dispatcher, tracker, domain)
    assert actual_events == [
        SlotSet('swiper_action_result', 'success'),
        SlotSet('swiper_native', 'unknown'),
        SlotSet('deeplink_data', ''),
        SlotSet('telegram_from', None),
        SlotSet('swiper_state', destination_swiper_state),
    ]
    assert dispatcher.messages == [{
        'attachment': None,
        'buttons': [],
        'custom': {},
        'elements': [],
        'image': None,
        'response': expected_response_template,
        'template': expected_response_template,
        'text': None,
    }]

    user_vault = UserVault()  # create new instance to avoid hitting cache
    assert user_vault.get_user('unit_test_user') == UserStateMachine(
        user_id='unit_test_user',
        state=destination_swiper_state,
        partner_id=None,
        newbie=True,
        state_timestamp=1619945501,
        state_timestamp_str='2021-05-02 08:51:41 Z',
        activity_timestamp=1619945501,
        activity_timestamp_str='2021-05-02 08:51:41 Z',
    )


@pytest.mark.asyncio
@pytest.mark.usefixtures('create_user_state_machine_table', 'wrap_actions_datetime_now')
@patch('time.time', Mock(return_value=1619945501))
@patch.object(UserVault, '_get_random_available_partner_dict')
@patch('telebot.apihelper._make_request')
@pytest.mark.parametrize(
    'user_has_photo, tracker_latest_message, expect_as_reminder, source_swiper_state, expect_dry_run, '
    'partner_blocked_bot',
    [
        (True, {}, False, 'new', False, True),
        (False, {'intent': None}, False, 'new', False, False),
        (True, {'intent': {'name': None}}, False, 'new', False, False),
        (False, {'intent': {'name': 'videochat'}}, False, 'new', False, False),
        (True, {'intent': {'name': 'videochat'}}, False, 'wants_chitchat', False, False),
        (False, {'intent': {'name': 'EXTERNAL_find_partner'}}, True, 'wants_chitchat', False, False),
        (True, {'intent': {'name': 'EXTERNAL_find_partner'}}, True, 'asked_to_join', True, False),
    ],
)
async def test_action_find_partner(
        mock_telebot_make_request: MagicMock,
        mock_get_random_available_partner_dict: MagicMock,
        mock_aioresponses: aioresponses,
        tracker: Tracker,
        dispatcher: CollectingDispatcher,
        domain: Dict[Text, Any],
        available_newbie1: UserStateMachine,
        telegram_user_profile_photo: Dict[Text, Any],
        telegram_user_profile_photo_make_request_call: call,
        rasa_callbacks_expected_req_builder: Callable[
            [Text, Text, Dict[Text, Any]], Tuple[Tuple[Text, URL], RequestCall]
        ],
        external_intent_response: Dict[Text, Any],
        user_has_photo: bool,
        tracker_latest_message: Dict[Text, Any],
        expect_as_reminder: bool,
        source_swiper_state: Text,
        expect_dry_run: bool,
        partner_blocked_bot: bool,
) -> None:
    user_vault = UserVault()
    user_vault.save(UserStateMachine(
        user_id='unit_test_user',
        state=source_swiper_state,
    ))

    # noinspection PyDataclass
    mock_get_random_available_partner_dict.return_value = asdict(available_newbie1)

    if user_has_photo:
        mock_telebot_make_request.return_value = telegram_user_profile_photo
    else:
        mock_telebot_make_request.return_value = {'photos': [], 'total_count': 0}

    if partner_blocked_bot:
        # ActionFindPartner should NOT fail because of rasa_callbacks.ask_to_join() failure
        mock_aioresponses.post(re.compile(r'.*'), payload={'status': 'failure'})
    else:
        mock_aioresponses.post(re.compile(r'.*'), payload=external_intent_response)

    tracker.latest_message = tracker_latest_message

    tracker.add_slots([
        SlotSet('partner_search_start_ts', '1619945450'),
    ])

    action = actions.ActionFindPartner()
    assert action.name() == 'action_find_partner'

    actual_events = await action.run(dispatcher, tracker, domain)

    if expect_dry_run:
        assert actual_events == [
            UserUtteranceReverted(),
            SlotSet('swiper_state', source_swiper_state),
        ]
        mock_get_random_available_partner_dict.assert_not_called()
        mock_telebot_make_request.assert_not_called()
        assert mock_aioresponses.requests == {}

    else:
        if expect_as_reminder:
            expected_events = [
                UserUtteranceReverted(),
            ]
        else:
            expected_events = [
                SlotSet('swiper_action_result', 'success'),
                SlotSet('partner_search_start_ts', '1619945501'),
            ]
        expected_events.extend([
            {
                'date_time': '2021-05-25T00:00:05',
                'entities': None,
                'event': 'reminder',
                'intent': 'EXTERNAL_find_partner',
                'kill_on_user_msg': False,
                'name': 'EXTERNAL_find_partner',
                'timestamp': None,
            },
            SlotSet('swiper_state', 'wants_chitchat'),
        ])
        assert actual_events == expected_events

        mock_get_random_available_partner_dict.assert_called_once_with(
            [
                'wants_chitchat',
                'ok_to_chitchat',
                'waiting_partner_confirm',
                'asked_to_join',
                'asked_to_confirm',
                'roomed',
                'rejected_join',
                'rejected_confirm',
            ],
            'unit_test_user',
        )
        assert mock_telebot_make_request.mock_calls == [
            telegram_user_profile_photo_make_request_call,
        ]
        expected_req_key, expected_req_call = rasa_callbacks_expected_req_builder(
            'available_newbie_id1',
            'EXTERNAL_ask_to_join',
            {
                'partner_id': 'unit_test_user',
                'partner_photo_file_id': 'biggest_profile_pic_file_id' if user_has_photo else None,
            },
        )
        assert mock_aioresponses.requests == {expected_req_key: [expected_req_call]}

    if expect_as_reminder:
        assert dispatcher.messages == []
    else:
        assert dispatcher.messages == [{
            'attachment': None,
            'buttons': [],
            'custom': {},
            'elements': [],
            'image': None,
            'response': 'utter_ok_arranging_chitchat',
            'template': 'utter_ok_arranging_chitchat',
            'text': None,
        }]

    user_vault = UserVault()
    assert user_vault.get_user('unit_test_user') == UserStateMachine(
        user_id='unit_test_user',
        state=source_swiper_state if expect_dry_run else 'wants_chitchat',
        partner_id=None,
        newbie=True,
        state_timestamp=0 if expect_as_reminder else 1619945501,
        state_timestamp_str=None if expect_as_reminder else '2021-05-02 08:51:41 Z',
        activity_timestamp=0 if expect_as_reminder else 1619945501,
        activity_timestamp_str=None if expect_as_reminder else '2021-05-02 08:51:41 Z',
    )


@pytest.mark.asyncio
@pytest.mark.usefixtures('ddb_unit_test_user', 'wrap_actions_datetime_now')
@patch('time.time', Mock(return_value=1619945501))
@patch.object(UserVault, '_get_random_available_partner_dict')
async def test_action_find_partner_no_one(
        mock_get_random_available_partner_dict: MagicMock,
        mock_aioresponses: aioresponses,
        tracker: Tracker,
        dispatcher: CollectingDispatcher,
        domain: Dict[Text, Any],
) -> None:
    mock_get_random_available_partner_dict.return_value = None

    actual_events = await actions.ActionFindPartner().run(dispatcher, tracker, domain)
    assert actual_events == [
        SlotSet('swiper_action_result', 'success'),
        SlotSet('partner_search_start_ts', '1619945501'),
        {
            'date_time': '2021-05-25T00:00:05',
            'entities': None,
            'event': 'reminder',
            'intent': 'EXTERNAL_find_partner',
            'kill_on_user_msg': False,
            'name': 'EXTERNAL_find_partner',
            'timestamp': None,
        },
        SlotSet('swiper_state', 'wants_chitchat'),
    ]

    assert dispatcher.messages == [
        {
            'attachment': None,
            'buttons': [],
            'custom': {},
            'elements': [],
            'image': None,
            'response': 'utter_ok_arranging_chitchat',
            'template': 'utter_ok_arranging_chitchat',
            'text': None,
        },
    ]

    mock_get_random_available_partner_dict.assert_called_once_with(
        [
            'wants_chitchat',
            'ok_to_chitchat',
            'waiting_partner_confirm',
            'asked_to_join',
            'asked_to_confirm',
            'roomed',
            'rejected_join',
            'rejected_confirm',
        ],
        'unit_test_user',
    )
    assert mock_aioresponses.requests == {}  # rasa_callbacks.ask_to_join() not called

    user_vault = UserVault()
    assert user_vault.get_user('unit_test_user') == UserStateMachine(
        user_id='unit_test_user',
        state='wants_chitchat',
        partner_id=None,
        newbie=True,
        state_timestamp=1619945501,
        state_timestamp_str='2021-05-02 08:51:41 Z',
        activity_timestamp=1619945501,
        activity_timestamp_str='2021-05-02 08:51:41 Z',
    )


@pytest.mark.asyncio
@pytest.mark.usefixtures('create_user_state_machine_table', 'wrap_traceback_format_exception')
@patch('time.time', Mock(return_value=1619945501))
@patch('uuid.uuid4', Mock(return_value=uuid.UUID('aaaabbbb-cccc-dddd-eeee-ffff11112222')))
@pytest.mark.parametrize(
    'source_swiper_state, latest_intent, destination_swiper_state, set_photo_slot, expected_response_template',
    [
        ('roomed', 'EXTERNAL_ask_to_join', 'asked_to_join', True, 'utter_someone_wants_to_chat_photo'),
        ('roomed', 'EXTERNAL_ask_to_join', 'asked_to_join', False, 'utter_someone_wants_to_chat'),
        ('roomed', 'EXTERNAL_ask_to_confirm', 'asked_to_confirm', True, 'utter_found_someone_check_ready_photo'),
        ('roomed', 'EXTERNAL_ask_to_confirm', 'asked_to_confirm', False, 'utter_found_someone_check_ready'),
        ('roomed', 'some_irrelevant_intent', None, True, None),
        ('roomed', None, None, True, None),

        ('new', 'EXTERNAL_ask_to_join', 'asked_to_join', False, 'utter_someone_wants_to_chat'),
        ('wants_chitchat', 'EXTERNAL_ask_to_join', 'asked_to_join', False, 'utter_someone_wants_to_chat'),
        ('ok_to_chitchat', 'EXTERNAL_ask_to_join', 'asked_to_join', False, 'utter_someone_wants_to_chat'),
        ('waiting_partner_confirm', 'EXTERNAL_ask_to_join', 'asked_to_join', False, 'utter_someone_wants_to_chat'),
        ('asked_to_join', 'EXTERNAL_ask_to_join', 'asked_to_join', False, 'utter_someone_wants_to_chat'),
        ('asked_to_confirm', 'EXTERNAL_ask_to_join', 'asked_to_join', False, 'utter_someone_wants_to_chat'),
        ('rejected_join', 'EXTERNAL_ask_to_join', 'asked_to_join', False, 'utter_someone_wants_to_chat'),
        ('rejected_confirm', 'EXTERNAL_ask_to_join', 'asked_to_join', False, 'utter_someone_wants_to_chat'),
        ('do_not_disturb', 'EXTERNAL_ask_to_join', 'asked_to_join', False, 'utter_someone_wants_to_chat'),
    ],
)
async def test_action_ask_to_join(
        tracker: Tracker,
        dispatcher: CollectingDispatcher,
        domain: Dict[Text, Any],
        source_swiper_state: Text,
        latest_intent: Text,
        destination_swiper_state: Optional[Text],
        set_photo_slot: bool,
        expected_response_template: Optional[Text],
) -> None:
    user_vault = UserVault()
    user_vault.save(UserStateMachine(
        user_id='unit_test_user',
        state=source_swiper_state,
        partner_id='previous_asker',
        newbie=True,
    ))

    if latest_intent:
        tracker.latest_message = {'intent': {'name': latest_intent}}

    tracker.add_slots([
        SlotSet('partner_id', 'new_asker'),
    ])
    if set_photo_slot:
        tracker.add_slots([
            SlotSet('partner_photo_file_id', 'some photo file id'),
        ])

    action = actions.ActionAskToJoin()
    assert action.name() == 'action_ask_to_join'

    actual_events = await action.run(dispatcher, tracker, domain)
    if destination_swiper_state:
        assert actual_events == [
            SlotSet('swiper_action_result', 'success'),
            SlotSet('swiper_state', destination_swiper_state),
        ]

        expected_response = {
            'attachment': None,
            'buttons': [],
            'custom': {},
            'elements': [],
            'image': None,
            'response': expected_response_template,
            'template': expected_response_template,
            'text': None,
        }
        if set_photo_slot:
            expected_response['partner_photo_file_id'] = 'some photo file id'

    else:  # an error is expected (and hence we do not expect swiper state to change)
        assert actual_events == [
            SlotSet('swiper_action_result', 'error'),
            SlotSet(
                'swiper_error',
                f"SwiperError(\"'action_ask_to_join' was triggered by an unexpected "
                f"intent ({repr(latest_intent)}) - either 'EXTERNAL_ask_to_join' or "
                f"'EXTERNAL_ask_to_confirm' was expected\")",
            ),
            SlotSet(
                'swiper_error_trace',
                'stack trace goes here',
            ),
            SlotSet('swiper_state', source_swiper_state),
            SlotSet('partner_id', 'previous_asker'),
        ]

        expected_response = {
            'attachment': None,
            'buttons': [],
            'custom': {},
            'elements': [],
            'image': None,
            'response': 'utter_error',
            'template': 'utter_error',
            'text': None,
        }

    assert dispatcher.messages == [expected_response]

    user_vault = UserVault()  # create new instance to avoid hitting cache
    assert user_vault.get_user('unit_test_user') == UserStateMachine(
        user_id='unit_test_user',
        state=destination_swiper_state if destination_swiper_state else source_swiper_state,
        partner_id='new_asker' if destination_swiper_state else 'previous_asker',
        newbie=True,
        state_timestamp=1619945501 if destination_swiper_state else 0,
        state_timestamp_str='2021-05-02 08:51:41 Z' if destination_swiper_state else None,
        state_timeout_ts=1619945501 + (60 * 60 * 4) if destination_swiper_state else 0,
        state_timeout_ts_str='2021-05-02 12:51:41 Z' if destination_swiper_state else None,
    )


@pytest.mark.asyncio
@pytest.mark.usefixtures('create_user_state_machine_table', 'wrap_actions_datetime_now')
@patch('time.time', Mock(return_value=1619945501))  # "now"
@patch('actions.daily_co.create_room', wraps=daily_co.create_room)
async def test_action_accept_invitation_create_room(
        wrap_daily_co_create_room: AsyncMock,
        mock_aioresponses: aioresponses,
        tracker: Tracker,
        dispatcher: CollectingDispatcher,
        domain: Dict[Text, Any],
        daily_co_create_room_expected_req: Tuple[Text, call],
        rasa_callbacks_expected_req_builder: Callable[
            [Text, Text, Dict[Text, Any]], Tuple[Tuple[Text, URL], RequestCall]
        ],
        new_room1: Dict[Text, Any],
        external_intent_response: Dict[Text, Any],
) -> None:
    mock_aioresponses.post(re.compile(r'https://api\.daily-unittest\.co/.*'), payload=new_room1)
    # noinspection HttpUrlsUsage
    mock_aioresponses.post(re.compile(r'http://rasa-unittest:5005/.*'), payload=external_intent_response)

    user_vault = UserVault()
    user_vault.save(UserStateMachine(
        user_id='an_asker',
        state='waiting_partner_confirm',
        partner_id='unit_test_user',
        newbie=True,
        state_timeout_ts=1619945501 + 1,  # we still have 1 second before the confirmation timeout
    ))
    user_vault.save(UserStateMachine(
        user_id='unit_test_user',
        state='asked_to_confirm',
        partner_id='an_asker',
        newbie=True,
    ))

    action = actions.ActionAcceptInvitation()
    assert action.name() == 'action_accept_invitation'

    actual_events = await action.run(dispatcher, tracker, domain)
    assert actual_events == [
        SlotSet('swiper_action_result', 'room_url_ready'),
        SlotSet('room_url', 'https://swipy.daily.co/pytestroom'),
        SlotSet('swiper_state', 'roomed'),
        SlotSet('partner_id', 'an_asker'),
    ]
    assert dispatcher.messages == [{
        'attachment': None,
        'buttons': [],
        'custom': {},
        'elements': [],
        'image': None,
        'response': 'utter_room_url',
        'template': 'utter_room_url',
        'text': None,
        'room_url': 'https://swipy.daily.co/pytestroom',
    }]

    rasa_callbacks_join_room_req_key, rasa_callbacks_join_room_req_call = rasa_callbacks_expected_req_builder(
        'an_asker',
        'EXTERNAL_join_room',
        {
            'partner_id': 'unit_test_user',
            'room_url': 'https://swipy.daily.co/pytestroom',
        },
    )
    expected_requests = {
        daily_co_create_room_expected_req[0]: [daily_co_create_room_expected_req[1]],
        rasa_callbacks_join_room_req_key: [rasa_callbacks_join_room_req_call],
    }
    assert mock_aioresponses.requests == expected_requests

    # make sure correct sender_id was passed (for logging purposes)
    wrap_daily_co_create_room.assert_called_once_with('unit_test_user')

    user_vault = UserVault()  # create new instance to avoid hitting cache
    assert user_vault.get_user('unit_test_user') == UserStateMachine(
        user_id='unit_test_user',
        state='roomed',
        partner_id='an_asker',
        newbie=False,  # accepting the very first video chitchat graduates the user from newbie
        state_timestamp=1619945501,
        state_timestamp_str='2021-05-02 08:51:41 Z',
        state_timeout_ts=1619945501 + (60 * 60 * 4),
        state_timeout_ts_str='2021-05-02 12:51:41 Z',
        activity_timestamp=1619945501,
        activity_timestamp_str='2021-05-02 08:51:41 Z',
    )


@pytest.mark.asyncio
@pytest.mark.parametrize('partner', [
    UserStateMachine(
        user_id='an_asker',
        state='wants_chitchat',
        partner_id=None,
    ),
    UserStateMachine(
        user_id='an_asker',
        state='waiting_partner_confirm',
        partner_id='unit_test_user',
        state_timeout_ts=1619945501 - 1,  # we are 1 second late, now we have to confirm again
    )
])
@pytest.mark.usefixtures('create_user_state_machine_table', 'wrap_actions_datetime_now')
@patch('time.time', Mock(return_value=1619945501))  # "now"
@patch('telebot.apihelper._make_request')
async def test_action_accept_invitation_confirm_with_asker(
        mock_telebot_make_request: MagicMock,
        mock_aioresponses: aioresponses,
        tracker: Tracker,
        dispatcher: CollectingDispatcher,
        domain: Dict[Text, Any],
        telegram_user_profile_photo: Dict[Text, Any],
        telegram_user_profile_photo_make_request_call: call,
        rasa_callbacks_expected_req_builder: Callable[
            [Text, Text, Dict[Text, Any]], Tuple[Tuple[Text, URL], RequestCall]
        ],
        external_intent_response: Dict[Text, Any],
        partner: UserStateMachine,
) -> None:
    mock_telebot_make_request.return_value = telegram_user_profile_photo
    mock_aioresponses.post(re.compile(r'.*'), payload=external_intent_response)

    user_vault = UserVault()
    user_vault.save(partner)
    user_vault.save(UserStateMachine(
        user_id='unit_test_user',
        state='asked_to_join',
        partner_id='an_asker',
        newbie=True,
    ))

    actual_events = await actions.ActionAcceptInvitation().run(dispatcher, tracker, domain)
    assert actual_events == [
        SlotSet('swiper_action_result', 'partner_has_been_asked'),
        {
            'date_time': '2021-05-25T00:01:00',
            'entities': None,
            'event': 'reminder',
            'intent': 'EXTERNAL_expire_partner_confirmation',
            'kill_on_user_msg': False,
            'name': 'EXTERNAL_expire_partner_confirmation',
            'timestamp': None
        },
        SlotSet('swiper_state', 'waiting_partner_confirm'),
        SlotSet('partner_id', 'an_asker'),
    ]
    assert dispatcher.messages == [{
        'attachment': None,
        'buttons': [],
        'custom': {},
        'elements': [],
        'image': None,
        'response': 'utter_checking_if_partner_ready_too',
        'template': 'utter_checking_if_partner_ready_too',
        'text': None,
    }]

    assert mock_telebot_make_request.mock_calls == [
        telegram_user_profile_photo_make_request_call,
    ]

    rasa_callbacks_ask_if_ready_req_key, rasa_callbacks_ask_if_ready_req_call = rasa_callbacks_expected_req_builder(
        'an_asker',
        'EXTERNAL_ask_to_confirm',
        {
            'partner_id': 'unit_test_user',
            'partner_photo_file_id': 'biggest_profile_pic_file_id',
        },
    )
    assert mock_aioresponses.requests == {
        rasa_callbacks_ask_if_ready_req_key: [rasa_callbacks_ask_if_ready_req_call],
    }

    user_vault = UserVault()  # create new instance to avoid hitting cache
    assert user_vault.get_user('unit_test_user') == UserStateMachine(
        user_id='unit_test_user',
        state='waiting_partner_confirm',
        partner_id='an_asker',
        newbie=True,
        state_timestamp=1619945501,
        state_timestamp_str='2021-05-02 08:51:41 Z',
        state_timeout_ts=1619945501 + 60,  # 'waiting_partner_confirm' times out in 1 minute
        state_timeout_ts_str='2021-05-02 08:52:41 Z',
        activity_timestamp=1619945501,
        activity_timestamp_str='2021-05-02 08:51:41 Z',
    )


@pytest.mark.asyncio
@pytest.mark.parametrize('partner', [
    UserStateMachine(
        user_id='an_asker',
        state='new',
        partner_id='unit_test_user',
    ),
    UserStateMachine(
        user_id='an_asker',
        state='do_not_disturb',
        partner_id='unit_test_user',
    ),
])
@pytest.mark.usefixtures('create_user_state_machine_table', 'wrap_actions_datetime_now')
@patch('time.time', Mock(return_value=1619945501))
async def test_action_accept_invitation_partner_not_waiting(
        mock_aioresponses: aioresponses,
        tracker: Tracker,
        dispatcher: CollectingDispatcher,
        domain: Dict[Text, Any],
        partner: UserStateMachine,
) -> None:
    user_vault = UserVault()
    user_vault.save(partner)
    user_vault.save(UserStateMachine(
        user_id='unit_test_user',
        state='asked_to_join',
        partner_id='an_asker',
    ))

    actual_events = await actions.ActionAcceptInvitation().run(dispatcher, tracker, domain)
    assert actual_events == [
        SlotSet('swiper_action_result', 'partner_not_waiting_anymore'),
        SlotSet('partner_search_start_ts', '1619945501'),
        {
            'date_time': '2021-05-25T00:00:02',
            'entities': None,
            'event': 'reminder',
            'intent': 'EXTERNAL_find_partner',
            'kill_on_user_msg': False,
            'name': 'EXTERNAL_find_partner',
            'timestamp': None,
        },
        SlotSet('swiper_state', 'wants_chitchat'),
    ]
    assert dispatcher.messages == [{
        'attachment': None,
        'buttons': [],
        'custom': {},
        'elements': [],
        'image': None,
        'response': 'utter_partner_already_gone',
        'template': 'utter_partner_already_gone',
        'text': None,
    }]

    # neither daily_co.create_room() nor rasa_callbacks.join_room() are called
    assert mock_aioresponses.requests == {}

    user_vault = UserVault()  # create new instance to avoid hitting cache
    assert user_vault.get_user('unit_test_user') == UserStateMachine(
        user_id='unit_test_user',
        state='wants_chitchat',
        partner_id=None,
        state_timestamp=1619945501,
        state_timestamp_str='2021-05-02 08:51:41 Z',
        activity_timestamp=1619945501,
        activity_timestamp_str='2021-05-02 08:51:41 Z',
    )


@pytest.mark.asyncio
@pytest.mark.parametrize('current_user', [
    UserStateMachine(
        user_id='unit_test_user',
        state='asked_to_join',
        partner_id='',
        newbie=True,
    ),
    UserStateMachine(
        user_id='unit_test_user',
        state='asked_to_join',
        partner_id=None,
        newbie=True,
    ),
])
@pytest.mark.usefixtures('create_user_state_machine_table', 'wrap_traceback_format_exception')
@patch('time.time', Mock(return_value=1619945501))  # "now"
async def test_action_accept_invitation_no_partner_id(
        mock_aioresponses: aioresponses,
        tracker: Tracker,
        dispatcher: CollectingDispatcher,
        domain: Dict[Text, Any],
        current_user: UserStateMachine,
) -> None:
    user_vault = UserVault()
    user_vault.save(UserStateMachine(
        user_id='an_asker',
        state='waiting_partner_confirm',
        partner_id='unit_test_user',
        newbie=True,
    ))
    user_vault.save(current_user)

    actual_events = await actions.ActionAcceptInvitation().run(dispatcher, tracker, domain)
    expected_events = [
        SlotSet('swiper_action_result', 'error'),
        SlotSet(
            'swiper_error',
            "ValueError('user_id cannot be empty')",
        ),
        SlotSet(
            'swiper_error_trace',
            'stack trace goes here',
        ),
        SlotSet('swiper_state', current_user.state),
    ]
    if current_user.partner_id is not None:
        # None is not expected to be set explicitly (None is the value that the slot had already)
        expected_events.append(SlotSet('partner_id', current_user.partner_id))

    assert actual_events == expected_events

    assert dispatcher.messages == [{
        'attachment': None,
        'buttons': [],
        'custom': {},
        'elements': [],
        'image': None,
        'response': 'utter_error',
        'template': 'utter_error',
        'text': None,
    }]

    # neither daily_co.create_room() nor rasa_callbacks.join_room() are called
    assert mock_aioresponses.requests == {}

    user_vault = UserVault()  # create new instance to avoid hitting cache
    new_current_user = deepcopy(current_user)  # deep-copy just in case
    new_current_user.activity_timestamp = 1619945501
    new_current_user.activity_timestamp_str = '2021-05-02 08:51:41 Z'
    assert user_vault.get_user('unit_test_user') == new_current_user


@pytest.mark.asyncio
@pytest.mark.parametrize('source_swiper_state, wrong_partner, action_allowed', [
    ('new', False, False),
    ('wants_chitchat', False, False),
    ('ok_to_chitchat', False, False),
    ('waiting_partner_confirm', False, True),
    ('asked_to_join', False, False),
    ('asked_to_confirm', False, True),
    ('roomed', False, False),
    ('rejected_join', False, False),
    ('rejected_confirm', False, False),
    ('do_not_disturb', False, False),

    ('waiting_partner_confirm', True, False),
    ('asked_to_confirm', True, False),
])
@pytest.mark.usefixtures('create_user_state_machine_table', 'wrap_traceback_format_exception')
@patch('time.time', Mock(return_value=1619945501))
async def test_action_join_room(
        tracker: Tracker,
        dispatcher: CollectingDispatcher,
        domain: Dict[Text, Any],
        source_swiper_state: Text,
        wrong_partner: bool,
        action_allowed: bool,
) -> None:
    action = actions.ActionJoinRoom()
    assert action.name() == 'action_join_room'

    user_vault = UserVault()
    user_vault.save(UserStateMachine(
        user_id='unit_test_user',  # the asker
        state=source_swiper_state,
        partner_id='expected_partner',
        newbie=True,
    ))

    tracker.add_slots([
        SlotSet('partner_id', 'unexpected_partner' if wrong_partner else 'expected_partner'),
    ])

    actual_events = await action.run(dispatcher, tracker, domain)

    user_vault = UserVault()  # create new instance to avoid hitting cache

    if action_allowed:
        assert actual_events == [
            SlotSet('swiper_action_result', 'success'),
            SlotSet('swiper_state', 'roomed'),
        ]
        assert dispatcher.messages == [{
            'attachment': None,
            'buttons': [],
            'custom': {},
            'elements': [],
            'image': None,
            'response': 'utter_partner_ready_room_url',
            'template': 'utter_partner_ready_room_url',
            'text': None,
        }]
        assert user_vault.get_user('unit_test_user') == UserStateMachine(
            user_id='unit_test_user',  # the asker
            state='roomed',
            partner_id='expected_partner',
            newbie=False,  # accepting the very first video chitchat graduates the user from newbie
            state_timestamp=1619945501,
            state_timestamp_str='2021-05-02 08:51:41 Z',
            state_timeout_ts=1619945501 + (60 * 60 * 4),
            state_timeout_ts_str='2021-05-02 12:51:41 Z',
        )

    else:
        expected_events = [
            SlotSet('swiper_action_result', 'error'),
            SlotSet(
                'swiper_error',

                'SwiperStateMachineError("partner_id that was passed (\'unexpected_partner\') differs from partner_id '
                'that was set before (\'expected_partner\')")' if wrong_partner else

                f"MachineError(\"Can't trigger event join_room from state {source_swiper_state}!\")",
            ),
            SlotSet(
                'swiper_error_trace',
                'stack trace goes here',
            ),
            SlotSet('swiper_state', source_swiper_state),  # state has not changed
        ]
        if wrong_partner:
            # 'partner_id' slot was initially set to 'unexpected_partner', and hence is expected to be "reverted"
            expected_events.append(SlotSet('partner_id', 'expected_partner'))

        assert actual_events == expected_events

        assert dispatcher.messages == [{
            'attachment': None,
            'buttons': [],
            'custom': {},
            'elements': [],
            'image': None,
            'response': 'utter_error',
            'template': 'utter_error',
            'text': None,
        }]
        assert user_vault.get_user('unit_test_user') == UserStateMachine(  # the state of current user has not changed
            user_id='unit_test_user',  # the asker
            state=source_swiper_state,
            partner_id='expected_partner',
            newbie=True,
        )


@pytest.mark.asyncio
@pytest.mark.usefixtures('create_user_state_machine_table')
@patch('time.time', Mock(return_value=1619945501))
@pytest.mark.parametrize('source_swiper_state', [
    'new',
    'wants_chitchat',
    'ok_to_chitchat',
    'waiting_partner_confirm',
    'asked_to_join',
    'asked_to_confirm',
    'roomed',
    'rejected_join',
    'rejected_confirm',
    'do_not_disturb',
])
async def test_action_do_not_disturb(
        tracker: Tracker,
        dispatcher: CollectingDispatcher,
        domain: Dict[Text, Any],
        source_swiper_state: Text,
) -> None:
    user_vault = UserVault()
    user_vault.save(UserStateMachine(
        user_id='unit_test_user',
        state=source_swiper_state,
        partner_id='',
        newbie=True,
    ))

    action = actions.ActionDoNotDisturb()
    assert action.name() == 'action_do_not_disturb'

    actual_events = await action.run(dispatcher, tracker, domain)
    assert actual_events == [
        SlotSet('swiper_action_result', 'success'),
        SlotSet('swiper_state', 'do_not_disturb'),
    ]
    assert dispatcher.messages == [{
        'attachment': None,
        'buttons': [],
        'custom': {},
        'elements': [],
        'image': None,
        'response': 'utter_hope_to_see_you_later',
        'template': 'utter_hope_to_see_you_later',
        'text': None,
    }]

    user_vault = UserVault()  # create new instance to avoid hitting cache
    assert user_vault.get_user('unit_test_user') == UserStateMachine(
        user_id='unit_test_user',
        state='do_not_disturb',
        partner_id=None,
        newbie=True,
        state_timestamp=1619945501,
        state_timestamp_str='2021-05-02 08:51:41 Z',
        activity_timestamp=1619945501,
        activity_timestamp_str='2021-05-02 08:51:41 Z',
    )


@pytest.mark.asyncio
@pytest.mark.usefixtures('create_user_state_machine_table', 'wrap_traceback_format_exception')
@patch('time.time', Mock(return_value=1619945501))
@pytest.mark.parametrize('source_swiper_state, destination_swiper_state', [
    ('new', None),
    ('wants_chitchat', None),
    ('ok_to_chitchat', None),
    ('waiting_partner_confirm', None),
    ('asked_to_join', 'rejected_join'),
    ('asked_to_confirm', 'rejected_confirm'),
    ('roomed', None),
    ('rejected_join', None),
    ('rejected_confirm', None),
    ('do_not_disturb', None),
])
async def test_action_reject_invitation(
        tracker: Tracker,
        dispatcher: CollectingDispatcher,
        domain: Dict[Text, Any],
        source_swiper_state: Text,
        destination_swiper_state: Text,
) -> None:
    user_vault = UserVault()
    user_vault.save(UserStateMachine(
        user_id='unit_test_user',
        state=source_swiper_state,
        partner_id='',
        newbie=True,
    ))

    action = actions.ActionRejectInvitation()
    assert action.name() == 'action_reject_invitation'

    actual_events = await action.run(dispatcher, tracker, domain)

    user_vault = UserVault()  # create new instance to avoid hitting cache

    if destination_swiper_state:
        assert actual_events == [
            SlotSet('swiper_action_result', 'success'),
            SlotSet('swiper_state', destination_swiper_state),
            SlotSet('partner_id', ''),
        ]
        assert dispatcher.messages == [{
            'attachment': None,
            'buttons': [],
            'custom': {},
            'elements': [],
            'image': None,
            'response': 'utter_declined',
            'template': 'utter_declined',
            'text': None,
        }]
        assert user_vault.get_user('unit_test_user') == UserStateMachine(
            user_id='unit_test_user',
            state=destination_swiper_state,
            partner_id='',
            newbie=True,
            state_timestamp=1619945501,
            state_timestamp_str='2021-05-02 08:51:41 Z',
            state_timeout_ts=1619945501 + (60 * 60 * 4),
            state_timeout_ts_str='2021-05-02 12:51:41 Z',
            activity_timestamp=1619945501,
            activity_timestamp_str='2021-05-02 08:51:41 Z',
        )

    else:  # an error is expected
        assert actual_events == [
            SlotSet('swiper_action_result', 'error'),
            SlotSet(
                'swiper_error',
                f"MachineError(\"Can't trigger event reject from state {source_swiper_state}!\")",
            ),
            SlotSet(
                'swiper_error_trace',
                'stack trace goes here',
            ),
            SlotSet('swiper_state', source_swiper_state),
            SlotSet('partner_id', ''),
        ]
        assert dispatcher.messages == [{
            'attachment': None,
            'buttons': [],
            'custom': {},
            'elements': [],
            'image': None,
            'response': 'utter_error',
            'template': 'utter_error',
            'text': None,
        }]
        assert user_vault.get_user('unit_test_user') == UserStateMachine(
            user_id='unit_test_user',
            state=source_swiper_state,
            partner_id='',
            newbie=True,
            activity_timestamp=1619945501,
            activity_timestamp_str='2021-05-02 08:51:41 Z',
        )


@pytest.mark.asyncio
@pytest.mark.parametrize('source_swiper_state, action_has_effect', [
    ('new', False),
    ('wants_chitchat', False),
    ('ok_to_chitchat', False),
    ('waiting_partner_confirm', True),
    ('asked_to_join', False),
    ('asked_to_confirm', False),
    ('roomed', False),
    ('rejected_join', False),
    ('rejected_confirm', False),
    ('do_not_disturb', False),
])
@pytest.mark.usefixtures('create_user_state_machine_table', 'wrap_actions_datetime_now')
@patch('time.time', Mock(return_value=1619945501))
async def test_action_expire_partner_confirmation(
        tracker: Tracker,
        dispatcher: CollectingDispatcher,
        domain: Dict[Text, Any],
        source_swiper_state: Text,
        action_has_effect: bool,
) -> None:
    user_vault = UserVault()
    user_vault.save(UserStateMachine(
        user_id='unit_test_user',
        state=source_swiper_state,
        partner_id='',
        newbie=True,
    ))

    action = actions.ActionExpirePartnerConfirmation()
    assert action.name() == 'action_expire_partner_confirmation'

    actual_events = await action.run(dispatcher, tracker, domain)

    if action_has_effect:
        assert actual_events == [
            SlotSet('swiper_action_result', 'success'),
            SlotSet('partner_search_start_ts', '1619945501'),
            {
                'date_time': '2021-05-25T00:00:02',
                'entities': None,
                'event': 'reminder',
                'intent': 'EXTERNAL_find_partner',
                'kill_on_user_msg': False,
                'name': 'EXTERNAL_find_partner',
                'timestamp': None,
            },
            SlotSet('swiper_state', source_swiper_state),
            SlotSet('partner_id', ''),
        ]
        assert dispatcher.messages == [{
            'attachment': None,
            'buttons': [],
            'custom': {},
            'elements': [],
            'image': None,
            'response': 'utter_partner_already_gone',
            'template': 'utter_partner_already_gone',
            'text': None,
        }]

    else:
        assert actual_events == [
            UserUtteranceReverted(),
            SlotSet('swiper_state', source_swiper_state),
            SlotSet('partner_id', ''),
        ]
        assert dispatcher.messages == []

    user_vault = UserVault()  # create new instance to avoid hitting cache
    assert user_vault.get_user('unit_test_user') == UserStateMachine(  # the state of current user has not changed
        user_id='unit_test_user',
        state=source_swiper_state,
        partner_id='',
        newbie=True,
    )
