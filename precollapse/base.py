from yapsy.IPlugin import IPlugin
from cliff.command import Command as cCommand
from cliff.show import ShowOne as cShowOne
from cliff.lister import Lister as cLister


class Plugin(IPlugin):
    commands = []
    backends = []

    def check(self):
        return None

    def register_commands(self, manager):
        for cmd in self.commands:
            manager.register_command(cmd)

    def register_backends(self, manager):
        for back in self.backends:
            manager.register_backend(back)

class CmdMixin(object):
    def get_parser(self, prog_name):
        try:
            args = self.__getattribute__("PARAMETERS")
        except AttributeError:
            args = []
        # search for the real implementation class
        # and get the parser
        bclass = self.__class__.__bases__[0]
        rclass = bclass.__bases__[-1]
        parser = rclass.get_parser(self, prog_name)
        for arg in args:
            kw = arg[-1]
            ar = arg[:-1]
            if not isinstance(kw, dict):
                ar = ar + (kw,)
                kw = {}
            parser.add_argument(*ar, **kw)
        return parser


class Command(CmdMixin, cCommand):
    pass

class ShowOne(CmdMixin, cShowOne):
    pass

class Lister(CmdMixin, cLister):
    pass
