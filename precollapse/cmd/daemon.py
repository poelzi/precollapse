import logging
import os.path

from ..base import Lister, ShowOne, Command
from .. import exceptions as exc

class Daemon(Command):
    "creates a directory"
    name = "daemon"

    log = logging.getLogger(__name__)

    PARAMETERS = [
        #('path', {"nargs":"?"}),
        ]

    def take_action(self, parsed_args):
        self.app.manager.start_daemon()
        return

