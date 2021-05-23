from dataclasses import dataclass
from typing import Text, Optional

from transitions import Machine


class UserState:
    NEW = 'new'
    WAITING_PARTNER_ANSWER = 'waiting_partner_answer'
    OK_TO_CHITCHAT = 'ok_to_chitchat'
    ASKED_TO_JOIN = 'asked_to_join'
    DO_NOT_DISTURB = 'do_not_disturb'

    all = [
        NEW,
        WAITING_PARTNER_ANSWER,
        OK_TO_CHITCHAT,
        ASKED_TO_JOIN,
        DO_NOT_DISTURB,
    ]


@dataclass
class UserModel:
    user_id: Text
    state: Text = None  # the state machine will set it to UserState.NEW if not provided explicitly
    partner_id: Optional[Text] = None
    newbie: bool = True


class UserStateMachine(UserModel):
    def __init__(self, *args, state: Text = None, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        self.machine = Machine(model=self, states=UserState.all, initial=UserState.NEW)
        if state is not None:
            self.machine.set_state(state)

        # noinspection PyTypeChecker
        self.machine.add_transition(
            trigger='ask_partner',
            source='*',
            dest=UserState.WAITING_PARTNER_ANSWER,
            before=[self.set_partner_id],
        )
        # noinspection PyTypeChecker
        self.machine.add_transition(
            trigger='become_ok_to_chitchat',
            source='*',
            dest=UserState.OK_TO_CHITCHAT,
            before=[self.drop_partner_id],
        )
        # noinspection PyTypeChecker
        self.machine.add_transition(
            trigger='become_asked_to_join',
            source=UserState.OK_TO_CHITCHAT,
            dest=UserState.ASKED_TO_JOIN,
            before=[self.set_partner_id],
        )
        # noinspection PyTypeChecker
        self.machine.add_transition(
            trigger='accept_invitation',
            source=UserState.ASKED_TO_JOIN,
            dest=UserState.OK_TO_CHITCHAT,
            before=[self.graduate_from_newbie],  # TODO oleksandr: should partner_id be dropped ?
        )
        # noinspection PyTypeChecker
        self.machine.add_transition(
            trigger='reject_invitation',
            source=UserState.ASKED_TO_JOIN,
            dest=UserState.DO_NOT_DISTURB,
            before=[self.drop_partner_id],
        )

    def set_partner_id(self, partner_id: Text) -> None:
        self.partner_id = partner_id

    def drop_partner_id(self) -> None:
        self.partner_id = None

    def graduate_from_newbie(self) -> None:
        self.newbie = False
