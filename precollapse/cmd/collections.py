"""
Commands for collection management
"""


import logging

from ..base import Lister, ShowOne, Command
from IPython import embed


class Collection_List(Lister):
    "A simple command that prints a message."
    name = "collection-list"

    log = logging.getLogger(__name__)

    def take_action(self, parsed_args):
        from ..db.model import Collection
        from ..db import Session
        session = Session()
        keys = ['id', 'name', 'uuid', 'owner', 'upstream_url']
        q = session.query(Collection).all()
        if not len(q):
            return (keys,())
        vars_ = []
        for col in q:
            vars_.append(tuple(col.__getattribute__(k) for k in keys))
        return (keys, vars_)




class Collection_Add(ShowOne):
    "A simple command that prints a message."
    name = "collection-add"

    log = logging.getLogger(__name__)

    PARAMETERS = [
        ('name', {"nargs":1}),
        ('--owner', {"help":'owner of collection'}),
        ('--gpgid', {"help":'gpg id for signing'})
    ]

    def take_action(self, parsed_args):
        from ..db.model import Collection
        from ..db import Session
        print(parsed_args)
        #Collection.create(
        session = Session()
        rv = Collection.create(session,
                               name=parsed_args.name[0], owner=parsed_args.owner,
                               owner_gpgid=parsed_args.gpgid)
        session.commit()
        x = rv.dump()
        return x.keys(), x.values()



__all__ = [Collection_List, Collection_Add]
