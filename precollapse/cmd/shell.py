"""
Commands for shell like behaviour
"""


import logging
from ..base import Lister, Command, ShowOne
from .. import exceptions as exc
from .. import utils
import os

from IPython import embed

class Ls(Lister):
    "A simple command that prints a message."
    name = "ls"

    log = logging.getLogger(__name__)
    root_keys = ['typ', 'size', 'owner', 'changed', 'name']
    root_details = ['uuid']
    entry_keys = ['typ', 'size', 'owner', 'changed', 'name']

    PARAMETERS = [
        ('path', {"nargs":'?'}),
        ('--details', '-d', {'action': 'store_true', 'help':'show more details'})
    ]

    def take_action(self, parsed_args):
        #embed()
        npath =  utils.abspath(self.app.pwd, parsed_args.path or "")
        parent, child = os.path.split(npath)
        if parent == "/":
            return self.root(child, details=parsed_args.details)
        else:
            return self.entry(npath, details=parsed_args.details)

    def entry(self, path, details=False):
        from ..db.model import Collection, Entry
        from ..db import create_session
        session = create_session()
        res = Collection.lookup(session, path)
        #embed()

        vars_ = []
        keys = Entry.EXPORT[0]
        for entry in res.children:
            c = entry.dump(details=details)
            keys = c[0]
            vars_.append(c[1])
        return (keys, vars_)

    def root(self, query=None, details=False):
        from ..db.model import Collection
        from ..db import create_session
        session = create_session()
        if query:
            q = session.query(Collection).filter(Collection.name.startswith(query))
        else:
            q = session.query(Collection).all()
        vars_ = []
        keys = Collection.EXPORT[0]
        for col in q:
            c = col.dump(details=details)
            keys = c[0]
            vars_.append(c[1])
        return (keys, vars_)

class Cd(Command):
    "changes into directory"
    name = "cd"

    log = logging.getLogger(__name__)
    keys = ['typ', 'size', 'owner', 'changed', 'name']

    PARAMETERS = (
        ('path', {"nargs":1}),
    )

    def take_action(self, parsed_args):
        from ..db.model import Collection
        from ..db import create_session
        session = create_session()
        if parsed_args.path[0] == "/":
            self.app.set_pwd("/")
            return
        npath =  utils.abspath(self.app.pwd, parsed_args.path[0])
        if npath == "/":
            self.app.set_pwd("/")
            return

        res = Collection.lookup(session, npath)
        if not res:
            raise exc.EntryNotFound("could not find file")
        self.app.set_pwd(npath)

class Info(ShowOne):
    "shows informations about a Entry"
    name = "show"

    log = logging.getLogger(__name__)

    PARAMETERS = [
        ('path', {"nargs":'+'}),
        ('--all',  {"action":'store_true'})
    ]

    def take_action(self, parsed_args):
        from ..db.model import Collection
        from ..db import create_session
        session = create_session()
        res = Collection.lookup(session, parsed_args.path[0])
        if not res:
            return None
        return res.dump(details=True, all_=parsed_args.all)



__all__ = [Ls, Cd, Info]
