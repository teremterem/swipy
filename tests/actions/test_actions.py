import re
import uuid
from copy import deepcopy
from dataclasses import asdict
from typing import Dict, Text, Any, List, Callable, Tuple, Optional, Type
from unittest.mock import patch, AsyncMock, MagicMock, call, Mock

import pytest
from aioresponses import aioresponses
from aioresponses.core import RequestCall
from rasa_sdk import Tracker
from rasa_sdk.events import SessionStarted, ActionExecuted, SlotSet, EventType, UserUtteranceReverted, FollowupAction
from rasa_sdk.executor import CollectingDispatcher
from yarl import URL

from actions import actions, daily_co
from actions.user_state_machine import UserStateMachine, UserState
from actions.user_vault import UserVault, IUserVault

UTTER_ERROR_TEXT = 'Ouch! Something went wrong 🤖'

UTTER_HOW_IT_WORKS_TEXT = """\
I can arrange video chitchat with another human for you 🎥 🗣 ☎️

Here is how it works:

- I find someone who also wants to chitchat.
- I confirm with you and them that you are both ready.
- I send both of you a video chat link.

<b>Would you like to give it a try?</b>"""

UTTER_CANNOT_HELP_WITH_THAT_TEXT = """\
I'm sorry, but I cannot help you with that 🤖

<b>Would you like to practice your spoken English 🇬🇧 \
on a video call with a stranger?</b>"""

UTTER_LOST_TRACK_OF_CONVERSATION_TEXT = """\
Forgive me, but I've lost track of our conversation 🤖

<b>Would you like to practice your spoken English 🇬🇧 \
on a video call with a stranger?</b>"""

UTTER_GREET_OFFER_CHITCHAT_TEXT = """\
Hi, my name is Swipy 🙂

I can connect you with a stranger in a video chat \
so you could practice your English speaking skills 🇬🇧

<b>Would you like to give it a try?</b>"""

UTTER_OK_ARRANGING_CHITCHAT_TEXT = """\
Great! Let me find someone for you to chitchat with 🗣

I will get back to you within two minutes ⏳"""

UTTER_ROOM_URL_TEXT = """\
Awesome! ✅ 🎉

<b>Please follow this link to join the video call:</b>

https://swipy.daily.co/anothertestroom"""

UTTER_PARTNER_READY_ROOM_URL_TEXT = """\
Done! ✅ 🎉

<b>Please follow this link to join the video call:</b>

https://swipy.daily.co/anothertestroom"""

UTTER_THAT_PERSON_ALREADY_GONE_TEXT = """\
That person has become unavailable 😵

Fear not!

I am already looking for someone else to connect you with \
and will get back to you within two minutes ⏳"""

UTTER_FIRST_NAME_ALREADY_GONE_TEXT = """\
<b><i>unitTest firstName10</i></b> has become unavailable 😵

Fear not!

I am already looking for someone else to connect you with \
and will get back to you within two minutes ⏳"""

UTTER_CHECKING_IF_THAT_PERSON_READY_TOO_TEXT = """\
Just a moment, I'm checking if that person is ready too...

Please don't go anywhere - <b>this will take one minute or less</b> ⏳"""

UTTER_CHECKING_IF_FIRST_NAME_READY_TOO_TEXT = """\
Just a moment, I'm checking if <b><i>unitTest firstName20</i></b> is ready too...

Please don't go anywhere - <b>this will take one minute or less</b> ⏳"""

UTTER_ASK_TO_JOIN_SOMEONE_TEXT = """\
Hey! Someone is looking to chitchat 🗣

<b>Would you like to join a video call?</b> 🎥 ☎️"""

UTTER_ASK_TO_JOIN_THIS_PERSON_TEXT = """\
Hey! This person is looking to chitchat 🗣

<b>Would you like to join a video call?</b> 🎥 ☎️"""

UTTER_ASK_TO_JOIN_FIRST_NAME_TEXT = """\
Hey! <b><i>unitTest firstName30</i></b> is looking to chitchat 🗣

<b>Would you like to join a video call?</b> 🎥 ☎️"""

UTTER_ASK_TO_CONFIRM_SOMEONE_TEXT = """\
Hey! Someone is willing to chitchat with 👉 you 👈

<b>Are you ready for a video call?</b> 🎥 ☎️"""

UTTER_ASK_TO_CONFIRM_THIS_PERSON_TEXT = """\
Hey! This person is willing to chitchat with 👉 you 👈

<b>Are you ready for a video call?</b> 🎥 ☎️"""

UTTER_ASK_TO_CONFIRM_FIRST_NAME_TEXT = """\
Hey! <b><i>unitTest firstName30</i></b> is willing to chitchat with 👉 you 👈

<b>Are you ready for a video call?</b> 🎥 ☎️"""

UTTER_INVITATION_DECLINED = """\
Ok, declined ❌

Should you decide that you want to practice your English speaking skills 🇬🇧 \
on a video call with a stranger just let me know 😉"""

UTTER_DND = 'Ok, I will not be sending invitations anymore 🛑'

REMOVE_KEYBOARD_MARKUP = '{"remove_keyboard":true}'
RESTART_COMMAND_MARKUP = (
    '{"keyboard":['

    '[{"text":"/restart"}]'

    '],"resize_keyboard":true,"one_time_keyboard":true}'
)
CANCEL_MARKUP = (
    '{"keyboard":['

    '[{"text":"Cancel"}]'

    '],"resize_keyboard":true,"one_time_keyboard":true}'
)
STOP_THE_CALL_MARKUP = (
    '{"keyboard":['

    '[{"text":"❌ Stop the call"}]'

    '],"resize_keyboard":true,"one_time_keyboard":true}'
)
YES_NO_SOMEONE_ELSE_MARKUP = (
    '{"keyboard":['

    '[{"text":"Yes"}],'
    '[{"text":"No"}],'
    '[{"text":"Connect me with someone else"}]'

    '],"resize_keyboard":true,"one_time_keyboard":true}'
)
YES_NO_MARKUP = (
    '{"keyboard":['

    '[{"text":"Yes"}],'
    '[{"text":"No"}]'

    '],"resize_keyboard":true,"one_time_keyboard":true}'
)
YES_NO_HOW_DOES_IT_WORK_MARKUP = (
    '{"keyboard":['

    '[{"text":"Yes"}],'
    '[{"text":"No"}],'
    '[{"text":"How does it work?"}]'

    '],"resize_keyboard":true,"one_time_keyboard":true}'
)


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
        'custom': {
            'text': UTTER_ERROR_TEXT,
            'parse_mode': 'html',
            'reply_markup': RESTART_COMMAND_MARKUP,
        },
        'elements': [],
        'image': None,
        'response': None,
        'template': None,
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
@pytest.mark.parametrize('action_class_to_test, expected_action_name, override_expected_response_text', [
    (actions.ActionOfferChitchat, 'action_offer_chitchat', None),
    (actions.ActionDefaultFallback, 'action_default_fallback', UTTER_LOST_TRACK_OF_CONVERSATION_TEXT),
])
@pytest.mark.parametrize('greeting_makes_user_ok_to_chitchat', [
    None,  # default - expected to be equivalent to False
    True,
])
@pytest.mark.parametrize('latest_intent, source_swiper_state, destination_swiper_state, expected_response_text', [
    ('help', 'new', 'ok_to_chitchat', UTTER_HOW_IT_WORKS_TEXT),
    ('out_of_scope', 'new', 'ok_to_chitchat', UTTER_CANNOT_HELP_WITH_THAT_TEXT),
    ('start', 'new', 'ok_to_chitchat', UTTER_GREET_OFFER_CHITCHAT_TEXT),
    ('greet', 'new', 'ok_to_chitchat', UTTER_GREET_OFFER_CHITCHAT_TEXT),

    ('some_test_intent', None, 'ok_to_chitchat', UTTER_GREET_OFFER_CHITCHAT_TEXT),  # user does not exist yet
    ('some_test_intent', 'new', 'ok_to_chitchat', UTTER_GREET_OFFER_CHITCHAT_TEXT),
    ('some_test_intent', 'wants_chitchat', 'wants_chitchat', UTTER_GREET_OFFER_CHITCHAT_TEXT),
    ('some_test_intent', 'ok_to_chitchat', 'ok_to_chitchat', UTTER_GREET_OFFER_CHITCHAT_TEXT),
    ('some_test_intent', 'waiting_partner_confirm', 'waiting_partner_confirm', UTTER_GREET_OFFER_CHITCHAT_TEXT),
    ('some_test_intent', 'asked_to_join', 'ok_to_chitchat', UTTER_GREET_OFFER_CHITCHAT_TEXT),
    ('some_test_intent', 'asked_to_confirm', 'ok_to_chitchat', UTTER_GREET_OFFER_CHITCHAT_TEXT),
    ('some_test_intent', 'roomed', 'ok_to_chitchat', UTTER_GREET_OFFER_CHITCHAT_TEXT),
    ('some_test_intent', 'rejected_join', 'ok_to_chitchat', UTTER_GREET_OFFER_CHITCHAT_TEXT),
    ('some_test_intent', 'rejected_confirm', 'ok_to_chitchat', UTTER_GREET_OFFER_CHITCHAT_TEXT),
    ('some_test_intent', 'do_not_disturb', 'ok_to_chitchat', UTTER_GREET_OFFER_CHITCHAT_TEXT),
    ('some_test_intent', 'bot_blocked', 'ok_to_chitchat', UTTER_GREET_OFFER_CHITCHAT_TEXT),
    ('some_test_intent', 'user_banned', 'user_banned', UTTER_GREET_OFFER_CHITCHAT_TEXT),
])
async def test_action_offer_chitchat_and_default_fallback(
        tracker: Tracker,
        dispatcher: CollectingDispatcher,
        domain: Dict[Text, Any],
        action_class_to_test: Type[actions.ActionOfferChitchat],
        expected_action_name: Text,
        override_expected_response_text: Optional[Text],
        greeting_makes_user_ok_to_chitchat: Optional[bool],
        latest_intent: Text,
        source_swiper_state: Optional[Text],
        destination_swiper_state: Text,
        expected_response_text: Text,
) -> None:
    if source_swiper_state is None:
        user_is_brand_new = True

        source_swiper_state = 'new'  # this is the expected default
    else:
        user_is_brand_new = False

        user_vault = UserVault()
        user_vault.save(UserStateMachine(
            user_id='unit_test_user',
            state=source_swiper_state,
            partner_id=None,
            roomed_partner_ids=['roomed_partner1'],
            rejected_partner_ids=['rejected_partner1', 'rejected_partner2'],
            seen_partner_ids=['seen_partner1', 'seen_partner2', 'seen_partner3'],
            newbie=True,
            state_timestamp=1619945501,
            state_timestamp_str='2021-05-02 08:51:41 Z',
        ))

    tracker.latest_message = {'intent_ranking': [{'name': latest_intent}]}

    action = action_class_to_test()
    assert action.name() == expected_action_name

    if greeting_makes_user_ok_to_chitchat is None:
        greeting_makes_user_ok_to_chitchat = False  # this is the expected default

        actual_events = await action.run(dispatcher, tracker, domain)
    else:
        with patch.object(
                actions,
                'GREETING_MAKES_USER_OK_TO_CHITCHAT',
                greeting_makes_user_ok_to_chitchat,
        ):
            actual_events = await action.run(dispatcher, tracker, domain)

    if source_swiper_state == 'user_banned':
        assert actual_events == [
            SlotSet('swiper_state', 'user_banned'),
        ]
        assert dispatcher.messages == []
    else:
        assert actual_events == [
            SlotSet('swiper_action_result', 'success'),
            SlotSet('deeplink_data', ''),
            SlotSet('telegram_from', None),
            SlotSet(
                'swiper_state',
                destination_swiper_state if greeting_makes_user_ok_to_chitchat else source_swiper_state,
            ),
        ]

        if override_expected_response_text:
            expected_response_text = override_expected_response_text
        assert dispatcher.messages == [{
            'attachment': None,
            'buttons': [],
            'custom': {
                'text': expected_response_text,
                'parse_mode': 'html',
                'reply_markup':
                    YES_NO_MARKUP
                    if expected_response_text == UTTER_HOW_IT_WORKS_TEXT else
                    YES_NO_HOW_DOES_IT_WORK_MARKUP,
            },
            'elements': [],
            'image': None,
            'response': None,
            'template': None,
            'text': None,
        }]

    if user_is_brand_new and not greeting_makes_user_ok_to_chitchat:
        expected_state_timestamp = 0
        expected_state_timestamp_str = None
    else:
        expected_state_timestamp = 1619945501
        expected_state_timestamp_str = '2021-05-02 08:51:41 Z'

    user_vault = UserVault()  # create new instance to avoid hitting cache
    assert user_vault.get_user('unit_test_user') == UserStateMachine(
        user_id='unit_test_user',
        state=destination_swiper_state if greeting_makes_user_ok_to_chitchat else source_swiper_state,
        partner_id=None,
        roomed_partner_ids=[] if user_is_brand_new else ['roomed_partner1'],
        rejected_partner_ids=[] if user_is_brand_new else ['rejected_partner1', 'rejected_partner2'],
        seen_partner_ids=[] if user_is_brand_new else ['seen_partner1', 'seen_partner2', 'seen_partner3'],
        newbie=True,
        state_timestamp=expected_state_timestamp,
        state_timestamp_str=expected_state_timestamp_str,
        activity_timestamp=1619945501,
        activity_timestamp_str='2021-05-02 08:51:41 Z',
    )


@pytest.mark.asyncio
@pytest.mark.usefixtures('create_user_state_machine_table')
@patch('time.time', Mock(return_value=1619945501))
async def test_action_rewind(
        tracker: Tracker,
        dispatcher: CollectingDispatcher,
        domain: Dict[Text, Any],
) -> None:
    action = actions.ActionRewind()
    assert action.name() == 'action_rewind'

    actual_events = await action.run(dispatcher, tracker, domain)
    assert actual_events == [
        UserUtteranceReverted(),
        SlotSet('swiper_state', 'new'),
    ]
    assert dispatcher.messages == []

    user_vault = UserVault()
    assert user_vault.get_user('unit_test_user') == UserStateMachine(
        user_id='unit_test_user',
        activity_timestamp=1619945501,  # activity timestamp was updated
        activity_timestamp_str='2021-05-02 08:51:41 Z',
    )


@pytest.mark.asyncio
@pytest.mark.usefixtures('create_user_state_machine_table', 'wrap_actions_datetime_now')
@patch('time.time', Mock(return_value=1619945501))
@patch.object(UserVault, '_get_random_available_partner_dict')
@patch('telebot.apihelper._make_request')
@pytest.mark.parametrize(
    'user_has_photo, user_has_name, tracker_latest_message, expect_as_reminder, source_swiper_state, expect_dry_run, '
    'partner_blocked_bot',
    [
        (True, True, {}, False, 'new', False, True),
        (False, True, {'intent': None}, False, 'new', False, False),
        (True, False, {'intent': {'name': None}}, False, 'new', False, False),
        (False, False, {'intent': {'name': 'videochat'}}, False, 'new', False, False),
        (True, None, {'intent': {'name': 'videochat'}}, False, 'wants_chitchat', False, False),
        (False, None, {'intent': {'name': 'EXTERNAL_find_partner'}}, True, 'wants_chitchat', False, False),
        (True, True, {'intent': {'name': 'EXTERNAL_find_partner'}}, True, 'asked_to_join', True, False),
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
        user_has_name: Optional[bool],
        tracker_latest_message: Dict[Text, Any],
        expect_as_reminder: bool,
        source_swiper_state: Text,
        expect_dry_run: bool,
        partner_blocked_bot: bool,
) -> None:
    current_user = UserStateMachine(
        user_id='unit_test_user',
        state=source_swiper_state,
        roomed_partner_ids=['roomed_partner1'],
        rejected_partner_ids=['rejected_partner1', 'rejected_partner2'],
        seen_partner_ids=['seen_partner1', 'seen_partner2', 'seen_partner3'],
    )
    if user_has_name:
        current_user.telegram_from = {'first_name': 'unit_test_first_name'}
    elif user_has_name is False:
        current_user.telegram_from = {'first_name': ''}
    # else (user_has_name is None) => we are not setting telegram_from at all

    user_vault = UserVault()
    user_vault.save(current_user)

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
                'name': 'unit_test_userEXTERNAL_find_partner',
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
                'take_a_break',
            ],
            'unit_test_user',
            [
                'unit_test_user',
                'roomed_partner1',
                'rejected_partner1',
                'rejected_partner2',
            ],
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
                'partner_first_name': 'unit_test_first_name' if user_has_name else None,
            },
        )
        assert mock_aioresponses.requests == {expected_req_key: [expected_req_call]}

    assert dispatcher.messages == []

    user_vault = UserVault()
    assert user_vault.get_user('unit_test_user') == UserStateMachine(
        user_id='unit_test_user',
        state=source_swiper_state if expect_dry_run else 'wants_chitchat',
        partner_id=None,
        roomed_partner_ids=['roomed_partner1'],
        rejected_partner_ids=['rejected_partner1', 'rejected_partner2'],
        seen_partner_ids=['seen_partner1', 'seen_partner2', 'seen_partner3'] if expect_as_reminder else [],
        newbie=True,
        state_timestamp=0 if expect_as_reminder else 1619945501,
        state_timestamp_str=None if expect_as_reminder else '2021-05-02 08:51:41 Z',
        activity_timestamp=0 if expect_as_reminder else 1619945501,
        activity_timestamp_str=None if expect_as_reminder else '2021-05-02 08:51:41 Z',
        telegram_from=current_user.telegram_from,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize('previous_action_result, clear_rejected_flag, expect_rejected_cleared', [
    ('partner_was_not_found', None, True),
    ('success', None, False),
    (None, None, False),
    ('partner_was_not_found', True, True),
    ('success', True, False),
    (None, True, False),
    ('partner_was_not_found', False, False),
    ('success', False, False),
    (None, False, False),
])
@pytest.mark.usefixtures('ddb_unit_test_user', 'wrap_actions_datetime_now')
@patch('time.time', Mock(return_value=1619945501))
@patch.object(UserVault, '_get_random_available_partner_dict')
async def test_action_find_partner_no_one(
        mock_get_random_available_partner_dict: MagicMock,
        mock_aioresponses: aioresponses,
        tracker: Tracker,
        dispatcher: CollectingDispatcher,
        domain: Dict[Text, Any],
        previous_action_result: Optional[Text],
        clear_rejected_flag: Optional[bool],
        expect_rejected_cleared: bool,
) -> None:
    mock_get_random_available_partner_dict.return_value = None

    if previous_action_result:
        tracker.add_slots([
            SlotSet('swiper_action_result', previous_action_result),
        ])

    if clear_rejected_flag is None:

        actual_events = await actions.ActionFindPartner().run(dispatcher, tracker, domain)

    else:
        with patch.object(
                actions,
                'CLEAR_REJECTED_LIST_WHEN_NO_ONE_FOUND',
                clear_rejected_flag,
        ):
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
            'name': 'unit_test_userEXTERNAL_find_partner',
            'timestamp': None,
        },
        SlotSet('swiper_state', 'wants_chitchat'),
    ]
    assert dispatcher.messages == []

    expected_excluded_partner_ids = [
        'unit_test_user',
        'roomed_unit_test_partner1',
        'roomed_unit_test_partner2',
    ]
    if not expect_rejected_cleared:
        expected_excluded_partner_ids.extend([
            'rejected_unit_test_partner1',
            'rejected_unit_test_partner2',
        ])
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
            'take_a_break',
        ],
        'unit_test_user',
        expected_excluded_partner_ids,
    )
    assert mock_aioresponses.requests == {}  # rasa_callbacks.ask_to_join() not called

    user_vault = UserVault()
    assert user_vault.get_user('unit_test_user') == UserStateMachine(
        user_id='unit_test_user',
        state='wants_chitchat',
        partner_id=None,
        roomed_partner_ids=['roomed_unit_test_partner1', 'roomed_unit_test_partner2'],
        rejected_partner_ids=[] if expect_rejected_cleared else [
            'rejected_unit_test_partner1',
            'rejected_unit_test_partner2',
        ],
        seen_partner_ids=[],  # cleared
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
    'source_swiper_state, latest_intent, destination_swiper_state, set_photo_slot, set_name_slot, '
    'expected_response_text',
    [
        ('roomed', 'EXTERNAL_ask_to_join', 'asked_to_join', True, True, UTTER_ASK_TO_JOIN_FIRST_NAME_TEXT),
        ('roomed', 'EXTERNAL_ask_to_join', 'asked_to_join', False, True, UTTER_ASK_TO_JOIN_FIRST_NAME_TEXT),
        ('roomed', 'EXTERNAL_ask_to_join', 'asked_to_join', True, False, UTTER_ASK_TO_JOIN_THIS_PERSON_TEXT),
        ('roomed', 'EXTERNAL_ask_to_join', 'asked_to_join', False, False, UTTER_ASK_TO_JOIN_SOMEONE_TEXT),
        ('roomed', 'EXTERNAL_ask_to_confirm', 'asked_to_confirm', True, True, UTTER_ASK_TO_CONFIRM_FIRST_NAME_TEXT),
        ('roomed', 'EXTERNAL_ask_to_confirm', 'asked_to_confirm', False, True, UTTER_ASK_TO_CONFIRM_FIRST_NAME_TEXT),
        ('roomed', 'EXTERNAL_ask_to_confirm', 'asked_to_confirm', True, False, UTTER_ASK_TO_CONFIRM_THIS_PERSON_TEXT),
        ('roomed', 'EXTERNAL_ask_to_confirm', 'asked_to_confirm', False, False, UTTER_ASK_TO_CONFIRM_SOMEONE_TEXT),
        ('roomed', 'some_irrelevant_intent', None, True, True, None),
        ('roomed', None, None, True, True, None),

        ('new', 'EXTERNAL_ask_to_join', 'asked_to_join', False, False, UTTER_ASK_TO_JOIN_SOMEONE_TEXT),
        ('wants_chitchat', 'EXTERNAL_ask_to_join', 'asked_to_join', False, False, UTTER_ASK_TO_JOIN_SOMEONE_TEXT),
        ('ok_to_chitchat', 'EXTERNAL_ask_to_join', 'asked_to_join', False, False, UTTER_ASK_TO_JOIN_SOMEONE_TEXT),
        ('waiting_partner_confirm', 'EXTERNAL_ask_to_join', 'asked_to_join', False, False,
         UTTER_ASK_TO_JOIN_SOMEONE_TEXT),
        ('asked_to_join', 'EXTERNAL_ask_to_join', 'asked_to_join', False, False, UTTER_ASK_TO_JOIN_SOMEONE_TEXT),
        ('asked_to_confirm', 'EXTERNAL_ask_to_join', 'asked_to_join', False, False, UTTER_ASK_TO_JOIN_SOMEONE_TEXT),
        ('rejected_join', 'EXTERNAL_ask_to_join', 'asked_to_join', False, False, UTTER_ASK_TO_JOIN_SOMEONE_TEXT),
        ('rejected_confirm', 'EXTERNAL_ask_to_join', 'asked_to_join', False, False, UTTER_ASK_TO_JOIN_SOMEONE_TEXT),
        ('do_not_disturb', 'EXTERNAL_ask_to_join', 'asked_to_join', False, False, UTTER_ASK_TO_JOIN_SOMEONE_TEXT),
    ],
)
async def test_action_ask_to_join(
        tracker: Tracker,
        dispatcher: CollectingDispatcher,
        domain: Dict[Text, Any],
        wrap_random_randint: MagicMock,
        source_swiper_state: Text,
        latest_intent: Text,
        destination_swiper_state: Optional[Text],
        set_photo_slot: bool,
        set_name_slot: bool,
        expected_response_text: Optional[Text],
) -> None:
    user_vault = UserVault()
    user_vault.save(UserStateMachine(
        user_id='unit_test_user',
        state=source_swiper_state,
        partner_id='previous_asker',
        roomed_partner_ids=['roomed_partner1'],
        rejected_partner_ids=['rejected_partner1', 'rejected_partner2'],
        seen_partner_ids=['seen_partner1', 'seen_partner2', 'seen_partner3'],
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
    if set_name_slot:
        tracker.add_slots([
            SlotSet('partner_first_name', 'unitTest firstName30'),
        ])

    action = actions.ActionAskToJoin()
    assert action.name() == 'action_ask_to_join'

    actual_events = await action.run(dispatcher, tracker, domain)
    if destination_swiper_state:
        assert actual_events == [
            SlotSet('swiper_action_result', 'user_has_been_asked'),
            SlotSet('swiper_state', destination_swiper_state),
        ]

        if set_photo_slot:
            custom_dict = {
                'photo': 'some photo file id',
                'caption': expected_response_text,
                'parse_mode': 'html',
                'reply_markup': YES_NO_SOMEONE_ELSE_MARKUP,
            }
        else:
            custom_dict = {
                'text': expected_response_text,
                'parse_mode': 'html',
                'reply_markup': YES_NO_SOMEONE_ELSE_MARKUP,
            }
        expected_response = {
            'attachment': None,
            'buttons': [],
            'custom': custom_dict,
            'elements': [],
            'image': None,
            'response': None,
            'template': None,
            'text': None,
        }

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
            'custom': {
                'text': UTTER_ERROR_TEXT,
                'parse_mode': 'html',
                'reply_markup': RESTART_COMMAND_MARKUP,
            },
            'elements': [],
            'image': None,
            'response': None,
            'template': None,
            'text': None,
        }

    assert dispatcher.messages == [expected_response]

    user_vault = UserVault()  # create new instance to avoid hitting cache

    if destination_swiper_state:
        assert user_vault.get_user('unit_test_user') == UserStateMachine(
            user_id='unit_test_user',
            state=destination_swiper_state,
            partner_id='new_asker',
            roomed_partner_ids=['roomed_partner1'],
            rejected_partner_ids=['rejected_partner1', 'rejected_partner2'],
            seen_partner_ids=['new_asker'],
            newbie=True,
            state_timestamp=1619945501,
            state_timestamp_str='2021-05-02 08:51:41 Z',
            state_timeout_ts=1619945501 + (60 * 60 * 5),
            state_timeout_ts_str='2021-05-02 13:51:41 Z',
        )
        wrap_random_randint.assert_called_once_with(60 * 60 * 4, 60 * 60 * (24 * 2 - 5))

    else:  # an error is expected (and hence we do not expect swiper state to change)
        assert user_vault.get_user('unit_test_user') == UserStateMachine(
            user_id='unit_test_user',
            state=source_swiper_state,
            partner_id='previous_asker',
            roomed_partner_ids=['roomed_partner1'],
            rejected_partner_ids=['rejected_partner1', 'rejected_partner2'],
            seen_partner_ids=['seen_partner1', 'seen_partner2', 'seen_partner3'],
            newbie=True,
            state_timestamp=0,
            state_timestamp_str=None,
            state_timeout_ts=0,
            state_timeout_ts_str=None,
        )


@pytest.mark.asyncio
@pytest.mark.usefixtures('create_user_state_machine_table', 'wrap_actions_datetime_now')
@patch('time.time', Mock(return_value=1619945501))  # "now"
@patch('actions.daily_co.create_room', wraps=daily_co.create_room)
@patch('telebot.apihelper._make_request', Mock())
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
        roomed_partner_ids=['roomed_partner1'],
        rejected_partner_ids=['rejected_partner1', 'rejected_partner2'],
        seen_partner_ids=['seen_partner1', 'seen_partner2', 'seen_partner3'],
        newbie=True,
    ))

    tracker.events.append({
        'event': 'action',
        'name': 'action_ask_to_join',
    })

    action = actions.ActionAcceptInvitation()
    assert action.name() == 'action_accept_invitation'

    actual_events = await action.run(dispatcher, tracker, domain)
    assert actual_events == [
        SlotSet('swiper_action_result', 'room_url_ready'),
        SlotSet('room_url', 'https://swipy.daily.co/pytestroom'),
        SlotSet('room_name', 'pytestroom'),
        FollowupAction('action_join_room'),
        SlotSet('swiper_state', 'asked_to_confirm'),
        SlotSet('partner_id', 'an_asker'),
    ]
    assert dispatcher.messages == []

    rasa_callbacks_join_room_req_key, rasa_callbacks_join_room_req_call = rasa_callbacks_expected_req_builder(
        'an_asker',
        'EXTERNAL_join_room',
        {
            'partner_id': 'unit_test_user',
            'room_url': 'https://swipy.daily.co/pytestroom',
            'room_name': 'pytestroom',
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
        state='asked_to_confirm',
        partner_id='an_asker',
        roomed_partner_ids=['roomed_partner1'],
        rejected_partner_ids=['rejected_partner1', 'rejected_partner2'],
        seen_partner_ids=['seen_partner1', 'seen_partner2', 'seen_partner3'],
        newbie=True,
        activity_timestamp=1619945501,
        activity_timestamp_str='2021-05-02 08:51:41 Z',
    )


@pytest.mark.asyncio
@pytest.mark.parametrize('partner, expected_response_text', [
    (
            UserStateMachine(
                user_id='an_asker',
                state='wants_chitchat',
                partner_id=None,
                telegram_from={'first_name': 'unitTest firstName20'},
            ),
            UTTER_CHECKING_IF_FIRST_NAME_READY_TOO_TEXT,
    ),
    (
            UserStateMachine(
                user_id='an_asker',
                state='wants_chitchat',
                partner_id=None,
                telegram_from={'first_name': ''},
            ),
            UTTER_CHECKING_IF_THAT_PERSON_READY_TOO_TEXT,
    ),
    (
            UserStateMachine(
                user_id='an_asker',
                state='waiting_partner_confirm',
                partner_id='unit_test_user',
                state_timeout_ts=1619945501 - 1,  # we are 1 second late, now we have to confirm again
            ),
            UTTER_CHECKING_IF_THAT_PERSON_READY_TOO_TEXT,
    ),
    (
            UserStateMachine(
                user_id='an_asker',
                state='wants_chitchat',
                partner_id=None,
                seen_partner_ids=['unit_test_user'],  # this should NOT prevent confirmation from being sent
            ),
            UTTER_CHECKING_IF_THAT_PERSON_READY_TOO_TEXT,
    ),
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
        expected_response_text: Text,
) -> None:
    mock_telebot_make_request.return_value = telegram_user_profile_photo
    mock_aioresponses.post(re.compile(r'.*'), payload=external_intent_response)

    user_vault = UserVault()
    user_vault.save(partner)
    user_vault.save(UserStateMachine(
        user_id='unit_test_user',
        state='asked_to_join',
        partner_id='an_asker',
        roomed_partner_ids=['roomed_partner1'],
        rejected_partner_ids=['rejected_partner1', 'rejected_partner2'],
        seen_partner_ids=['seen_partner1', 'seen_partner2', 'seen_partner3'],
        newbie=True,
    ))

    tracker.events.append({
        'event': 'action',
        'name': 'action_ask_to_join',
    })

    actual_events = await actions.ActionAcceptInvitation().run(dispatcher, tracker, domain)
    assert actual_events == [
        SlotSet('swiper_action_result', 'partner_has_been_asked'),
        {
            'date_time': '2021-05-25T00:01:00',
            'entities': None,
            'event': 'reminder',
            'intent': 'EXTERNAL_expire_partner_confirmation',
            'kill_on_user_msg': False,
            'name': 'unit_test_userEXTERNAL_expire_partner_confirmation',
            'timestamp': None
        },
        SlotSet('swiper_state', 'waiting_partner_confirm'),
        SlotSet('partner_id', 'an_asker'),
    ]
    assert dispatcher.messages == [{
        'attachment': None,
        'buttons': [],
        'custom': {
            'text': expected_response_text,
            'parse_mode': 'html',
            'reply_markup': CANCEL_MARKUP,
        },
        'elements': [],
        'image': None,
        'response': None,
        'template': None,
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
            'partner_first_name': None,
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
        roomed_partner_ids=['roomed_partner1'],
        rejected_partner_ids=['rejected_partner1', 'rejected_partner2'],
        seen_partner_ids=['seen_partner1', 'seen_partner2', 'seen_partner3'],
        newbie=True,
        state_timestamp=1619945501,
        state_timestamp_str='2021-05-02 08:51:41 Z',
        state_timeout_ts=1619945501 + 60,  # 'waiting_partner_confirm' times out in 1 minute
        state_timeout_ts_str='2021-05-02 08:52:41 Z',
        activity_timestamp=1619945501,
        activity_timestamp_str='2021-05-02 08:51:41 Z',
    )


@pytest.mark.asyncio
@pytest.mark.parametrize('partner, expected_response_text', [
    (
            UserStateMachine(
                user_id='an_asker',
                state='new',
                partner_id='unit_test_user',
                telegram_from={'first_name': 'unitTest firstName10'},
            ),
            UTTER_FIRST_NAME_ALREADY_GONE_TEXT,
    ),
    (
            UserStateMachine(
                user_id='an_asker',
                state='new',
                partner_id='unit_test_user',
                telegram_from={'first_name': ''},
            ),
            UTTER_THAT_PERSON_ALREADY_GONE_TEXT,
    ),
    (
            UserStateMachine(
                user_id='an_asker',
                state='do_not_disturb',
                partner_id='unit_test_user',
            ),
            UTTER_THAT_PERSON_ALREADY_GONE_TEXT,
    ),
    (
            UserStateMachine(
                user_id='an_asker',
                state='wants_chitchat',
                partner_id=None,
                roomed_partner_ids=['unit_test_user'],  # asker is available but current user is excluded
            ),
            UTTER_THAT_PERSON_ALREADY_GONE_TEXT,
    ),
    (
            UserStateMachine(
                user_id='an_asker',
                state='wants_chitchat',
                partner_id=None,
                rejected_partner_ids=['unit_test_user'],  # asker is available but current user is excluded
            ),
            UTTER_THAT_PERSON_ALREADY_GONE_TEXT,
    ),
])
@pytest.mark.usefixtures('create_user_state_machine_table', 'wrap_actions_datetime_now')
@patch('time.time', Mock(return_value=1619945501))
@patch('telebot.apihelper._make_request', Mock())
async def test_action_accept_invitation_partner_not_waiting(
        mock_aioresponses: aioresponses,
        tracker: Tracker,
        dispatcher: CollectingDispatcher,
        domain: Dict[Text, Any],
        partner: UserStateMachine,
        expected_response_text: Text,
) -> None:
    user_vault = UserVault()
    user_vault.save(partner)
    user_vault.save(UserStateMachine(
        user_id='unit_test_user',
        state='asked_to_join',
        partner_id='an_asker',
        roomed_partner_ids=['roomed_partner1'],
        rejected_partner_ids=['rejected_partner1', 'rejected_partner2'],
        seen_partner_ids=['seen_partner1', 'seen_partner2', 'seen_partner3'],
    ))

    tracker.events.append({
        'event': 'action',
        'name': 'action_ask_to_join',
    })

    actual_events = await actions.ActionAcceptInvitation().run(dispatcher, tracker, domain)
    assert actual_events == [
        SlotSet('swiper_action_result', 'partner_not_waiting_anymore'),
        FollowupAction('action_find_partner'),
        SlotSet('swiper_state', 'asked_to_join'),  # action_find_partner will later change it to request_chitchat
        SlotSet('partner_id', 'an_asker'),
    ]
    assert dispatcher.messages == [{
        'attachment': None,
        'buttons': [],
        'custom': {
            'text': expected_response_text,
            'parse_mode': 'html',
            'reply_markup': CANCEL_MARKUP,
        },
        'elements': [],
        'image': None,
        'response': None,
        'template': None,
        'text': None,
    }]

    # neither daily_co.create_room() nor rasa_callbacks.join_room() are called
    assert mock_aioresponses.requests == {}

    user_vault = UserVault()  # create new instance to avoid hitting cache
    assert user_vault.get_user('unit_test_user') == UserStateMachine(
        user_id='unit_test_user',
        state='asked_to_join',
        partner_id='an_asker',
        roomed_partner_ids=['roomed_partner1'],
        rejected_partner_ids=['rejected_partner1', 'rejected_partner2'],
        seen_partner_ids=['seen_partner1', 'seen_partner2', 'seen_partner3'],
        activity_timestamp=1619945501,
        activity_timestamp_str='2021-05-02 08:51:41 Z',
    )


@pytest.mark.asyncio
@pytest.mark.parametrize('current_user', [
    UserStateMachine(
        user_id='unit_test_user',
        state='asked_to_join',
        partner_id='',
        roomed_partner_ids=['roomed_partner1'],
        rejected_partner_ids=['rejected_partner1', 'rejected_partner2'],
        seen_partner_ids=['seen_partner1', 'seen_partner2', 'seen_partner3'],
        newbie=True,
    ),
    UserStateMachine(
        user_id='unit_test_user',
        state='asked_to_join',
        partner_id=None,
        roomed_partner_ids=['roomed_partner1'],
        rejected_partner_ids=['rejected_partner1', 'rejected_partner2'],
        seen_partner_ids=['seen_partner1', 'seen_partner2', 'seen_partner3'],
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
    new_current_user = deepcopy(current_user)  # deep-copy just in case
    new_current_user.activity_timestamp = 1619945501
    new_current_user.activity_timestamp_str = '2021-05-02 08:51:41 Z'

    user_vault = UserVault()
    user_vault.save(UserStateMachine(
        user_id='an_asker',
        state='waiting_partner_confirm',
        partner_id='unit_test_user',
        newbie=True,
    ))
    user_vault.save(current_user)

    tracker.events.append({
        'event': 'action',
        'name': 'action_ask_to_join',
    })

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
        'custom': {
            'text': UTTER_ERROR_TEXT,
            'parse_mode': 'html',
            'reply_markup': RESTART_COMMAND_MARKUP,
        },
        'elements': [],
        'image': None,
        'response': None,
        'template': None,
        'text': None,
    }]

    # neither daily_co.create_room() nor rasa_callbacks.join_room() are called
    assert mock_aioresponses.requests == {}

    user_vault = UserVault()  # create new instance to avoid hitting cache
    assert user_vault.get_user('unit_test_user') == new_current_user


@pytest.mark.asyncio
@pytest.mark.parametrize('latest_intent, source_swiper_state, wrong_partner, action_allowed, expect_as_external', [
    ('some_test_intent', 'new', False, False, False),
    ('some_test_intent', 'wants_chitchat', False, False, False),
    ('some_test_intent', 'ok_to_chitchat', False, False, False),
    ('affirm', 'waiting_partner_confirm', False, True, False),
    ('EXTERNAL_join_room', 'waiting_partner_confirm', False, True, True),
    ('some_test_intent', 'asked_to_join', False, False, False),
    ('some_test_intent', 'asked_to_confirm', False, True, False),
    ('EXTERNAL_join_room', 'asked_to_confirm', False, True, True),
    ('some_test_intent', 'roomed', False, False, False),
    ('some_test_intent', 'rejected_join', False, False, False),
    ('some_test_intent', 'rejected_confirm', False, False, False),
    ('some_test_intent', 'do_not_disturb', False, False, False),

    ('some_test_intent', 'waiting_partner_confirm', True, False, False),
    ('some_test_intent', 'asked_to_confirm', True, False, False),
])
@pytest.mark.usefixtures(
    'create_user_state_machine_table',
    'wrap_traceback_format_exception',
    'wrap_actions_datetime_now',
)
@patch('time.time', Mock(return_value=1619945501))
async def test_action_join_room(
        tracker: Tracker,
        dispatcher: CollectingDispatcher,
        domain: Dict[Text, Any],
        wrap_random_randint: MagicMock,
        latest_intent: Text,
        source_swiper_state: Text,
        wrong_partner: bool,
        action_allowed: bool,
        expect_as_external: bool,
) -> None:
    user_vault = UserVault()
    user_vault.save(UserStateMachine(
        user_id='unit_test_user',  # the asker
        state=source_swiper_state,
        partner_id='expected_partner',
        roomed_partner_ids=['roomed_partner1'],
        rejected_partner_ids=['rejected_partner1', 'rejected_partner2'],
        seen_partner_ids=['seen_partner1', 'seen_partner2', 'seen_partner3'],
        newbie=True,
    ))

    tracker.add_slots([
        SlotSet('partner_id', 'unexpected_partner' if wrong_partner else 'expected_partner'),
        SlotSet('room_url', 'https://swipy.daily.co/anothertestroom'),
        SlotSet('room_name', 'anothertestroom'),
    ])
    tracker.latest_message = {'intent': {'name': latest_intent}}

    action = actions.ActionJoinRoom()
    assert action.name() == 'action_join_room'

    actual_events = await action.run(dispatcher, tracker, domain)

    user_vault = UserVault()  # create new instance to avoid hitting cache

    if action_allowed:
        assert actual_events == [
            SlotSet('swiper_action_result', 'success'),
            {
                'date_time': '2021-05-25T00:30:00',
                'entities': {'disposed_room_name': 'anothertestroom'},
                'event': 'reminder',
                'intent': 'EXTERNAL_room_expiration_report',
                'kill_on_user_msg': False,
                'name': 'unit_test_userEXTERNAL_room_expiration_report',
                'timestamp': None,
            },
            SlotSet('swiper_state', 'roomed'),
        ]
        assert dispatcher.messages == [{
            'attachment': None,
            'buttons': [],
            'custom': {
                'text': UTTER_PARTNER_READY_ROOM_URL_TEXT if expect_as_external else UTTER_ROOM_URL_TEXT,
                'parse_mode': 'html',
                'reply_markup': STOP_THE_CALL_MARKUP,
            },
            'elements': [],
            'image': None,
            'response': None,
            'template': None,
            'text': None,
        }]
        assert user_vault.get_user('unit_test_user') == UserStateMachine(
            user_id='unit_test_user',  # the asker
            state='roomed',
            partner_id='expected_partner',
            latest_room_name='anothertestroom',
            roomed_partner_ids=['roomed_partner1', 'expected_partner'],
            rejected_partner_ids=['rejected_partner1', 'rejected_partner2'],
            seen_partner_ids=['seen_partner1', 'seen_partner2', 'seen_partner3'],
            newbie=False,  # accepting the very first video chitchat graduates the user from newbie
            state_timestamp=1619945501,
            state_timestamp_str='2021-05-02 08:51:41 Z',
            state_timeout_ts=1619945501 + (60 * 60 * 5),
            state_timeout_ts_str='2021-05-02 13:51:41 Z',
            activity_timestamp=0 if expect_as_external else 1619945501,
            activity_timestamp_str=None if expect_as_external else '2021-05-02 08:51:41 Z',
        )
        wrap_random_randint.assert_called_once_with(60 * 60 * 4, 60 * 60 * (24 * 2 - 5))

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
            'custom': {
                'text': UTTER_ERROR_TEXT,
                'parse_mode': 'html',
                'reply_markup': RESTART_COMMAND_MARKUP,
            },
            'elements': [],
            'image': None,
            'response': None,
            'template': None,
            'text': None,
        }]
        assert user_vault.get_user('unit_test_user') == UserStateMachine(  # the state of current user has not changed
            user_id='unit_test_user',  # the asker
            state=source_swiper_state,
            partner_id='expected_partner',
            roomed_partner_ids=['roomed_partner1'],
            rejected_partner_ids=['rejected_partner1', 'rejected_partner2'],
            seen_partner_ids=['seen_partner1', 'seen_partner2', 'seen_partner3'],
            newbie=True,
            activity_timestamp=0 if expect_as_external else 1619945501,
            activity_timestamp_str=None if expect_as_external else '2021-05-02 08:51:41 Z',
        )
        wrap_random_randint.assert_not_called()


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
        roomed_partner_ids=['roomed_partner1'],
        rejected_partner_ids=['rejected_partner1', 'rejected_partner2'],
        seen_partner_ids=['seen_partner1', 'seen_partner2', 'seen_partner3'],
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
        'custom': {
            'text': UTTER_DND,
            'parse_mode': 'html',
            'reply_markup': RESTART_COMMAND_MARKUP,
        },
        'elements': [],
        'image': None,
        'response': None,
        'template': None,
        'text': None,
    }]

    user_vault = UserVault()  # create new instance to avoid hitting cache
    assert user_vault.get_user('unit_test_user') == UserStateMachine(
        user_id='unit_test_user',
        state='do_not_disturb',
        partner_id=None,
        roomed_partner_ids=['roomed_partner1'],
        rejected_partner_ids=['rejected_partner1', 'rejected_partner2'],
        seen_partner_ids=['seen_partner1', 'seen_partner2', 'seen_partner3'],
        newbie=True,
        state_timestamp=1619945501,
        state_timestamp_str='2021-05-02 08:51:41 Z',
        activity_timestamp=1619945501,
        activity_timestamp_str='2021-05-02 08:51:41 Z',
    )


@pytest.mark.asyncio
@pytest.mark.usefixtures('create_user_state_machine_table', 'wrap_traceback_format_exception')
@patch('time.time', Mock(return_value=1619945501))
@pytest.mark.parametrize('latest_intent, source_swiper_state, destination_swiper_state, attempt_to_reject_partner', [
    ('some_intent', 'new', None, False),
    ('some_intent', 'wants_chitchat', None, False),
    ('some_intent', 'ok_to_chitchat', None, False),
    ('some_intent', 'waiting_partner_confirm', 'rejected_join', False),
    ('some_intent', 'asked_to_join', 'rejected_join', False),
    ('some_intent', 'asked_to_confirm', 'rejected_confirm', False),
    ('videochat', 'waiting_partner_confirm', 'rejected_join', True),
    ('videochat', 'asked_to_join', 'rejected_join', True),
    ('videochat', 'asked_to_confirm', 'rejected_confirm', True),
    ('some_intent', 'roomed', None, False),
    ('videochat', 'roomed', None, True),
    ('some_intent', 'rejected_join', None, False),
    ('some_intent', 'rejected_confirm', None, False),
    ('some_intent', 'do_not_disturb', None, False),
])
async def test_action_reject_invitation(
        tracker: Tracker,
        dispatcher: CollectingDispatcher,
        domain: Dict[Text, Any],
        wrap_random_randint: MagicMock,
        latest_intent: Text,
        source_swiper_state: Text,
        destination_swiper_state: Text,
        attempt_to_reject_partner: bool,
) -> None:
    user_vault = UserVault()
    user_vault.save(UserStateMachine(
        user_id='unit_test_user',
        state=source_swiper_state,
        partner_id='some_test_partner_id',
        roomed_partner_ids=['roomed_partner1'],
        rejected_partner_ids=['rejected_partner1', 'rejected_partner2'],
        seen_partner_ids=['seen_partner1', 'seen_partner2', 'seen_partner3'],
        newbie=True,
    ))

    tracker.events.append({
        'event': 'action',
        'name': 'action_ask_to_join',
    })
    tracker.latest_message = {'intent_ranking': [{'name': latest_intent}]}

    action = actions.ActionRejectInvitation()
    assert action.name() == 'action_reject_invitation'

    actual_events = await action.run(dispatcher, tracker, domain)

    user_vault = UserVault()  # create new instance to avoid hitting cache

    if destination_swiper_state:
        expected_events = [
            SlotSet('swiper_action_result', 'success'),
        ]
        if attempt_to_reject_partner:
            expected_events.append(FollowupAction('action_find_partner'))
        expected_events.extend([
            SlotSet('swiper_state', destination_swiper_state),
            SlotSet('partner_id', 'some_test_partner_id'),
        ])
        assert actual_events == expected_events

        if attempt_to_reject_partner:
            assert dispatcher.messages == [{
                'attachment': None,
                'buttons': [],
                'custom': {},
                'elements': [],
                'image': None,
                'response': 'utter_ok_looking_for_partner',
                'template': 'utter_ok_looking_for_partner',
                'text': None,
            }]
        else:
            assert dispatcher.messages == [{
                'attachment': None,
                'buttons': [],
                'custom': {
                    'text': UTTER_INVITATION_DECLINED,
                    'parse_mode': 'html',
                    'reply_markup': RESTART_COMMAND_MARKUP,
                },
                'elements': [],
                'image': None,
                'response': None,
                'template': None,
                'text': None,
            }]

        expected_rejection_list = ['rejected_partner1', 'rejected_partner2']
        if attempt_to_reject_partner:
            expected_rejection_list.append('some_test_partner_id')

        assert user_vault.get_user('unit_test_user') == UserStateMachine(
            user_id='unit_test_user',
            state=destination_swiper_state,
            partner_id='some_test_partner_id',
            roomed_partner_ids=['roomed_partner1'],
            rejected_partner_ids=expected_rejection_list,
            seen_partner_ids=['seen_partner1', 'seen_partner2', 'seen_partner3'],
            newbie=True,
            state_timestamp=1619945501,
            state_timestamp_str='2021-05-02 08:51:41 Z',
            state_timeout_ts=1619945501 + (60 * 60 * 5),
            state_timeout_ts_str='2021-05-02 13:51:41 Z',
            activity_timestamp=1619945501,
            activity_timestamp_str='2021-05-02 08:51:41 Z',
        )
        wrap_random_randint.assert_called_once_with(60 * 60 * 4, 60 * 60 * (24 * 2 - 5))

    else:  # an error is expected
        assert actual_events == [
            SlotSet('swiper_action_result', 'error'),
            SlotSet(
                'swiper_error',
                f"MachineError(\"Can't trigger event "
                f"{'reject_partner' if attempt_to_reject_partner else 'reject_invitation'} "
                f"from state {source_swiper_state}!\")",
            ),
            SlotSet(
                'swiper_error_trace',
                'stack trace goes here',
            ),
            SlotSet('swiper_state', source_swiper_state),
            SlotSet('partner_id', 'some_test_partner_id'),
        ]
        assert dispatcher.messages == [{
            'attachment': None,
            'buttons': [],
            'custom': {
                'text': UTTER_ERROR_TEXT,
                'parse_mode': 'html',
                'reply_markup': RESTART_COMMAND_MARKUP,
            },
            'elements': [],
            'image': None,
            'response': None,
            'template': None,
            'text': None,
        }]
        assert user_vault.get_user('unit_test_user') == UserStateMachine(
            user_id='unit_test_user',
            state=source_swiper_state,
            partner_id='some_test_partner_id',
            roomed_partner_ids=['roomed_partner1'],
            rejected_partner_ids=['rejected_partner1', 'rejected_partner2'],
            seen_partner_ids=['seen_partner1', 'seen_partner2', 'seen_partner3'],
            newbie=True,
            activity_timestamp=1619945501,
            activity_timestamp_str='2021-05-02 08:51:41 Z',
        )


@pytest.mark.asyncio
@pytest.mark.parametrize('source_swiper_state, partner_has_name, expected_response_text', [
    ('new', True, None),
    ('wants_chitchat', False, None),
    ('ok_to_chitchat', True, None),

    ('waiting_partner_confirm', False, UTTER_THAT_PERSON_ALREADY_GONE_TEXT),
    ('waiting_partner_confirm', True, UTTER_FIRST_NAME_ALREADY_GONE_TEXT),

    ('asked_to_join', False, None),
    ('asked_to_confirm', True, None),
    ('roomed', False, None),
    ('rejected_join', True, None),
    ('rejected_confirm', False, None),
    ('do_not_disturb', True, None),
])
@pytest.mark.usefixtures('create_user_state_machine_table', 'wrap_actions_datetime_now')
@patch('time.time', Mock(return_value=1619945501))
async def test_action_expire_partner_confirmation(
        tracker: Tracker,
        dispatcher: CollectingDispatcher,
        domain: Dict[Text, Any],
        source_swiper_state: Text,
        partner_has_name: bool,
        expected_response_text: Optional[Text],
) -> None:
    user_vault = UserVault()
    user_vault.save(UserStateMachine(
        user_id='unit_test_user',
        state=source_swiper_state,
        partner_id='some_partner_id',
        roomed_partner_ids=['roomed_partner1'],
        rejected_partner_ids=['rejected_partner1', 'rejected_partner2'],
        seen_partner_ids=['seen_partner1', 'seen_partner2', 'seen_partner3'],
        newbie=True,
    ))
    user_vault.save(UserStateMachine(
        user_id='some_partner_id',
        telegram_from={'first_name': 'unitTest firstName10'} if partner_has_name else {},
    ))

    action = actions.ActionExpirePartnerConfirmation()
    assert action.name() == 'action_expire_partner_confirmation'

    actual_events = await action.run(dispatcher, tracker, domain)

    if expected_response_text:
        # action is expected to have had an effect
        assert actual_events == [
            SlotSet('swiper_action_result', 'success'),
            FollowupAction('action_find_partner'),
            SlotSet('swiper_state', source_swiper_state),
            SlotSet('partner_id', 'some_partner_id'),
        ]
        assert dispatcher.messages == [{
            'attachment': None,
            'buttons': [],
            'custom': {
                'text': expected_response_text,
                'parse_mode': 'html',
                'reply_markup': CANCEL_MARKUP,
            },
            'elements': [],
            'image': None,
            'response': None,
            'template': None,
            'text': None,
        }]

    else:
        # action is NOT expected to have had an effect
        assert actual_events == [
            UserUtteranceReverted(),
            SlotSet('swiper_state', source_swiper_state),
            SlotSet('partner_id', 'some_partner_id'),
        ]
        assert dispatcher.messages == []

    user_vault = UserVault()  # create new instance to avoid hitting cache
    assert user_vault.get_user('unit_test_user') == UserStateMachine(  # the state of current user has not changed
        user_id='unit_test_user',
        state=source_swiper_state,
        partner_id='some_partner_id',
        roomed_partner_ids=['roomed_partner1'],
        rejected_partner_ids=['rejected_partner1', 'rejected_partner2'],
        seen_partner_ids=['seen_partner1', 'seen_partner2', 'seen_partner3'],
        newbie=True,
    )
