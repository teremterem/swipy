from dataclasses import dataclass
from typing import Text, Optional

from transitions import Machine


class UserState:
    NEW = 'new'
    WAITING_PARTNER_ANSWER = 'waiting_partner_answer'
    OK_FOR_CHITCHAT = 'ok_for_chitchat'
    ASKED_TO_JOIN = 'asked_to_join'
    DO_NOT_DISTURB = 'do_not_disturb'

    all = [
        NEW,
        WAITING_PARTNER_ANSWER,
        OK_FOR_CHITCHAT,
        ASKED_TO_JOIN,
        DO_NOT_DISTURB,
    ]


@dataclass
class UserModel:
    user_id: Text
    state: Text = None  # the state machine will set it to UserState.NEW if not provided explicitly
    related_user_id: Optional[Text] = None
    newbie: bool = True


class UserStateMachine(UserModel):
    def __init__(self, *args, state=None, **kwargs):
        super().__init__(*args, **kwargs)

        self.machine = Machine(model=self, states=UserState.all, initial=UserState.NEW)
        if state is not None:
            self.machine.set_state(state)

        # noinspection PyTypeChecker
        self.machine.add_transition(
            trigger='ask_partner',
            source='*',
            dest=UserState.WAITING_PARTNER_ANSWER,
            before=self.before_ask_partner,
        )
        # noinspection PyTypeChecker
        self.machine.add_transition(
            trigger='fail_to_find_partner',
            source='*',
            dest=UserState.OK_FOR_CHITCHAT,
            before=self.before_fail_to_find_partner,
        )
        # noinspection PyTypeChecker
        self.machine.add_transition(
            trigger='become_asked_to_join',
            source=UserState.OK_FOR_CHITCHAT,
            dest=UserState.ASKED_TO_JOIN,
            before=self.before_become_asked_to_join,
        )

    def before_ask_partner(self, partner: 'UserStateMachine'):
        # noinspection PyUnresolvedReferences
        partner.become_asked_to_join(self.user_id)

        self.related_user_id = partner.user_id

    def before_fail_to_find_partner(self):
        self.related_user_id = None

    def before_become_asked_to_join(self, asker_id: Text):
        self.related_user_id = asker_id
