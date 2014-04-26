from precollapse import base
from precollapse.exceptions import CommandMissing
from precollapse.utils import which



class GitPlugin(base.Plugin):
    name = "git"

    def check(self):
        if not which("git"):
            raise CommandMissing("git missing")
        return True

    def print_name(self):
        print("git plugin")
