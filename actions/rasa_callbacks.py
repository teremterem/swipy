import logging
import os
from pprint import pformat
from typing import Text, Dict, Any, Optional

import aiohttp

from actions.user_state_machine import UserStateMachine
from actions.utils import SwiperRasaCallbackError

logger = logging.getLogger(__name__)

RASA_PRODUCTION_HOST = os.environ['RASA_PRODUCTION_HOST']
RASA_TOKEN = os.getenv('RASA_TOKEN')

OUTPUT_CHANNEL = 'telegram'  # seems to be more robust than 'latest'

PARTNER_ID_SLOT = 'partner_id'
PARTNER_PHOTO_FILE_ID_SLOT = 'partner_photo_file_id'
PARTNER_FIRST_NAME = 'partner_first_name'
ROOM_URL_SLOT = 'room_url'

EXTERNAL_ASK_TO_JOIN_INTENT = 'EXTERNAL_ask_to_join'
EXTERNAL_ASK_TO_CONFIRM_INTENT = 'EXTERNAL_ask_to_confirm'
EXTERNAL_JOIN_ROOM_INTENT = 'EXTERNAL_join_room'


async def ask_to_join(
        sender_id: Text,
        receiver: UserStateMachine,
        sender_photo_file_id: Optional[Text],
        sender_first_name: Optional[Text],
        suppress_callback_errors: bool = False,
) -> Optional[Dict[Text, Any]]:
    return await _trigger_external_rasa_intent(
        sender_id,
        receiver,
        EXTERNAL_ASK_TO_JOIN_INTENT,
        {
            PARTNER_ID_SLOT: sender_id,
            PARTNER_PHOTO_FILE_ID_SLOT: sender_photo_file_id,
            PARTNER_FIRST_NAME: sender_first_name,
        },
        suppress_callback_errors,
    )


async def ask_to_confirm(
        sender_id: Text,
        receiver: UserStateMachine,
        sender_photo_file_id: Optional[Text],
        sender_first_name: Optional[Text],
        suppress_callback_errors: bool = False,
) -> Optional[Dict[Text, Any]]:
    return await _trigger_external_rasa_intent(
        sender_id,
        receiver,
        EXTERNAL_ASK_TO_CONFIRM_INTENT,
        {
            PARTNER_ID_SLOT: sender_id,
            PARTNER_PHOTO_FILE_ID_SLOT: sender_photo_file_id,
            PARTNER_FIRST_NAME: sender_first_name,
        },
        suppress_callback_errors,
    )


async def join_room(
        sender_id: Text,
        receiver: UserStateMachine,
        room_url: Text,
        suppress_callback_errors: bool = False,
) -> Optional[Dict[Text, Any]]:
    return await _trigger_external_rasa_intent(
        sender_id,
        receiver,
        EXTERNAL_JOIN_ROOM_INTENT,
        {
            PARTNER_ID_SLOT: sender_id,
            ROOM_URL_SLOT: room_url,
        },
        suppress_callback_errors,
    )


async def _trigger_external_rasa_intent(
        sender_id: Text,
        receiver: UserStateMachine,
        intent_name: Text,
        entities: Dict[Text, Text],
        suppress_callback_errors: bool,
) -> Optional[Dict[Text, Any]]:
    # TODO oleksandr: do I need to reuse ClientSession instance ? what should be its lifetime ?
    async with aiohttp.ClientSession() as session:
        params = {
            'output_channel': OUTPUT_CHANNEL,
        }
        if RASA_TOKEN:
            params['token'] = RASA_TOKEN

        async with session.post(
                f"{RASA_PRODUCTION_HOST}/conversations/{receiver.user_id}/trigger_intent",
                params=params,
                json={
                    'name': intent_name,
                    'entities': entities,
                },
        ) as resp:
            resp_json = await resp.json()

    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(
            'TRIGGER_INTENT %r RESULT:\n\nSENDER_ID: %r\n\nRECEIVER_ID: %r\n\nENTITIES:\n%s\n\nRESPONSE:\n%s',
            intent_name,
            sender_id,
            receiver.user_id,
            pformat(entities),
            pformat(resp_json),
        )

    if not resp_json.get('tracker') or resp_json.get('status') == 'failure':
        if 'bot was blocked' in (resp_json.get('message') or '').lower():
            # noinspection PyUnresolvedReferences
            receiver.mark_as_bot_blocked()
            receiver.save()

        try:
            raise SwiperRasaCallbackError(repr(resp_json))
        except SwiperRasaCallbackError:
            logger.exception('failure in ' + repr(intent_name))
            if not suppress_callback_errors:
                raise

    if not suppress_callback_errors:
        return resp_json
    return None
