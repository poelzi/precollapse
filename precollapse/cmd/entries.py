"""
Commands for collection management
"""


import logging
import os.path
import asyncio

from ..base import Lister, ShowOne, Command
from .. import exceptions as exc

class EntryMod(object):
    def add_entry(self, path, **kwargs):
        from ..db.model import Collection, Entry, EntryType
        from ..db import create_session

        print(path)
        if os.path.isabs(path):
            pass
        elif self.app.interactive_mode:
            path = os.path.abspath(os.path.join(self.app.pwd, path))
        else:
            raise exc.ArgumentError("path must be absolute")

        parent, fname = os.path.split(path)
        session = create_session()
        rv = Collection.lookup(session,
                               parent)
        if not rv:
            raise exc.ParentNotFound("could not find parent directory: %s" %parent)

        if rv.has_child(fname):
            self.log.error("Entry already exists")
            raise exc.EntryExistsError("Entry already exists")

        nentry = Entry(name=fname, collection=rv.collection,
                       parent_id=rv.id,
                       url=kwargs.get('url', None), enabled=(not kwargs.get('disable', False)),
                       uuid=kwargs.get('uuid', None), plugin=kwargs.get('plugin', None),
                       type=kwargs.get('type', EntryType.single))
        session.add(nentry)
        session.commit()
        #rv = nentry.dump(details=True)
        return nentry


class Entry_Add(ShowOne, EntryMod):
    "A simple command that prints a message."
    name = "entry-add"

    log = logging.getLogger(__name__)

    PARAMETERS = [
        ('name', {"nargs":1}),
        ('url', {"nargs":'?'}),
        ('arguments', {"nargs":'*', "help":"additional download parameters (backend specific)"}),
        ('--disable', {"action": "store_true"}),
        ('--uuid', {"action": "store"}),
        ('--plugin', {"action": "store"}),
        #('--type', {"choices":

    ]

    def take_action(self, parsed_args):

        print(parsed_args)

        entry = self.add_entry(parsed_args.name[0],
                       url=parsed_args.url,
                       arguments=parsed_args.arguments,
                       disable=parsed_args.disable,
                       uuid=parsed_args.uuid,
                       plugin=parsed_args.plugin)
        return entry.dump(details=True)

        #Collection.create(

class Mkdir(Command, EntryMod):
    "creates a directory"
    name = "mkdir"

    log = logging.getLogger(__name__)

    PARAMETERS = [
        ('path', {"nargs":"?"}),
        ]

    def take_action(self, parsed_args):
        from ..db.model import EntryType
        entry = self.add_entry(parsed_args.path,
                               type=EntryType.directory)
        return entry.dump(details=True)

class Clear(Command):
    "Clears all downloaded files from entry"
    name = "clear"

    log = logging.getLogger(__name__)

    PARAMETERS = [
        ('path', {"nargs":'+'}),
        ]

    def take_action(self, parsed_args):
        from ..db.model import Collection
        from ..db import create_session
        session = create_session()
        for path in parsed_args.path:
            res = Collection.lookup(session, path)
            if not res:
                self.log.error("can't find: %s", path)
            else:
                self.log.info("clear %s", path)
                yield from asyncio.wait_for(self.app.manager.get_download_manager(res.collection).clear_entry(res))


__all__ = [Entry_Add, Mkdir, Clear]
