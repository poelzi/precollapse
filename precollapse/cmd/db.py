import logging

from ..base import Command


class SyncDB(Command):
    "A simple command that prints a message."
    name = "db-sync"

    log = logging.getLogger(__name__)

    def take_action(self, parsed_args):
        self.log.info('sync db')
        from ..db import Base, model, create_session, Engine

        session = create_session()
        Base.metadata.create_all(Engine)

