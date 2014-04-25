import logging

from cliff.command import Command
from ..db import Base, Engine


class SyncDB(Command):
    "A simple command that prints a message."
    name = "db-sync"

    log = logging.getLogger(__name__)

    def take_action(self, parsed_args):
        self.log.info('sync db')
        from ..db import model

        Base.metadata.create_all(Engine)



__all__ = [SyncDB]
