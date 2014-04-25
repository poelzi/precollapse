from precollapse.base import Plugin
from precollapse.exceptions import CommandMissing
from precollapse.utils import which



class GitPlugin(Plugin):
    def check(self):
        print(which("git"))
        if not which("git"):
            raise CommandMissing("git missing")
        return True

    def print_name(self):
        print("git plugin")
