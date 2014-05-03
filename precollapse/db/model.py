from sqlalchemy import Column, Integer, String, Text, BLOB, Enum, ForeignKey,\
                       DateTime, Interval, Boolean, asc, desc, UniqueConstraint
from sqlalchemy.types import TypeDecorator
from sqlalchemy.sql.expression import ColumnElement
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, backref, object_session
from sqlalchemy import or_
import uuid
import json
import os
import datetime
import enum
import math

from sqlalchemy import create_engine

from . import Base, create_session
from ..utils import AlchemyEncoder, pathsplit, pathjoin, fib
from .. import exceptions as exc


PLUGIN_NAME_LENGTH=30

TYPE_DIRECTORY = 'DIRECTORY'
TYPE_COLLECTION = 'COLLECTION'
TYPE_COLLECTION_MEMBER = 'COLLECTION_MEMBER'
TYPE_SINGLE = 'SINGLE'
ENTRY_TYPES = [TYPE_DIRECTORY, TYPE_COLLECTION, TYPE_COLLECTION_MEMBER, TYPE_SINGLE]

META_STRING = 'STRING'
META_JSON = 'JSON'
META_INTEGER = 'INTEGER'
META_BLOB = 'BLOB'
META_NONE = 'NONE'
META_TYPES = [META_STRING, META_JSON, META_INTEGER, META_BLOB, META_NONE]




class AEnum(TypeDecorator):
    """Safely coerce Python bytestrings to Unicode
    before passing off to the database."""

    impl = Enum

    def process_bind_param(self, value, dialect):
        if isinstance(value, enum.Enum):
            value = value.value
        return value



class EntryState(enum.Enum):
    download = "DOWNLOAD"
    done = "DONE"

    def __str__(self):
        return self.value

    def __eq__(self, other):
        if isinstance(other, enum.Enum):
            return self.value == other.value
        return self.value == other


def suuid():
    return str(uuid.uuid4())

def add_if(d, k, v, fi_=None):
    if fi_ is not None and k not in fi_:
        return
    if v:
        if isinstance(d, dict):
            d[k] = v
        else:
            d[0].append(k)
            d[1].append(v)

def filter_dump(rv, filter_):
    if filter_ is None:
        return
    dd = list(filter(lambda k: k not in filter_, rv.keys()))
    print("--------------------------")
    print(dd)
    for d in dd:
        del rv[d]
    return rv


def enum2alch(en):
    # creates a list of enum strings
    return map(lambda x: str(x), list(en))

class ModelMixin(object):
    def dump(self, filter_=None, details=False, all_=False, dict_=False):
        if not hasattr(self, "EXPORT"):
            return {}
        keys = self.EXPORT[0]
        if (details or all_) and len(self.EXPORT) > 1:
            keys += self.EXPORT[1]
        if all_ and len(self.EXPORT) > 2:
            keys += self.EXPORT[2]

        rv = []
        rk = []
        for key in keys:
            if filter_ is not None and key not in filter_:
                continue
            rk.append(key)
            rv.append(self.__getattribute__(key))
        if dict_:
            return dict(zip(rk, rv))
        return (rk, rv)




class Collection(Base, ModelMixin):
    id = Column(Integer, primary_key=True)
    name = Column(String(255))
    description = Column(String(80))
    long_description = Column(Text)
    owner = Column(String(200), default=os.getlogin())
    owner_gpgid = Column(String(30))
    upstream_url = Column(Text(), doc="upstream url")
    uuid = Column(String(36), index=True, unique=True, default=suuid)
    created = Column(DateTime, default=datetime.datetime.now)
    updated = Column(DateTime, default=None)
    enabled = Column(Boolean, default=True)
    check_interval = Column(Interval(), default=datetime.timedelta(days=1))

    #uname = Column(Collection.name.concat("-").concat(Collection.uuid).label("uname"))

    entries = relationship("Entry", backref="collection")

    __tablename__ = 'collection'

    EXPORT = (
        ("size", "owner", "changed", "name"),
        ("id", "upstream_url", "uuid", "created", "updated",
         "enabled", "check_interval", "owner_gpgid"),
        ("description", "long_description")
    )


    @staticmethod
    def create(session, *args, **kwargs):
        nc = Collection(*args, **kwargs)
        session.add(nc)
        root = Entry(name="/", type=TYPE_DIRECTORY, parent_id=None, collection=nc)
        session.add(root)
        return nc

    def mkdir(name):
        session = object_session(self)
        if self.type != TYPE_DIRECTORY:
            raise exc.EntryTypeError("can't create directory under non directory")
        if self.has_child(name):
            raise exc.EntryExistsError("file: %s already exists" %name)
        root = Entry(name=name, type=TYPE_DIRECTORY, parent_id=self.id, collection=self.collection.id)
        session.add(root)



    @staticmethod
    def lookup(session, path):
        sp = pathsplit(path)
        print(sp)
        if len(sp) < 2:
            raise exc.ArgumentError("path needs to be aboslute")
        # find collection
        colname = sp[1]
        col = Collection.lookup_collection(session, colname)
        entries = col.lookup_path(session, sp[2:])
        print("---%--"*4)
        print(entries)
        return entries

    @staticmethod
    def lookup_collection(session, colname):
        uname = Collection.name.concat("-").concat(Collection.uuid).label("uname")
        q = session.query(Collection).add_column(uname)
        q = q.filter(or_(uname.startswith("%s-" %colname), uname.startswith(colname)))
        q = q.order_by(asc("uname"))
        res = q.all()
        if len(res) == 0:
            raise exc.CollectionNotFound("could not find collation with name: %s" %colname)
        elif len(res) > 1:
            raise exc.CollectionMultipleChoices("multiple collections match, add uuid: %s[-UUID]" %colname)
        return res[0][0]

    def lookup_path(self, session, chunks):
        root = self.get_root()
        cur = root
        chunks = chunks[:]
        while len(chunks):
            nname = chunks.pop(0)
            cur = cur.descent(nname)
        return cur


    def __repr__(self):
        return "<Collection('%s' owner='%s'>" %(self.name, self.owner)

    def get_root(self):
        """
        Return the Root Directory Entry of the collection
        """
        return object_session(self).query(Entry).filter(Entry.collection == self, Entry.type.is_(TYPE_DIRECTORY), Entry.parent_id.is_(None)).one()

    @property
    def size(self):
        """
        Size of all entries that belong to the collection
        """
        return len(self.entries)

    @property
    def changed(self):
        return self.updated or self.created

class Entry(Base, ModelMixin):
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False, index=True, doc="name of directroy")
    type = Column(AEnum(*ENTRY_TYPES), index=True)
    plugin = Column(String(PLUGIN_NAME_LENGTH), doc="plugin handling the entry")
    uuid = Column(String(36), index=True, unique=True, default=suuid)
    url = Column(Text)
    arguments = Column(Text)
    state = Column(AEnum(*enum2alch(EntryState)))
    created = Column(DateTime, default=datetime.datetime.now)
    updated = Column(DateTime, default=None, index=True)
    enabled = Column(Boolean, nullable=True, default=None)
    last_success = Column(DateTime, nullable=True, default=None)
    last_failure = Column(DateTime, nullable=True, default=None, index=True)
    error_msg = Column(Text, nullable=True, default=None)
    success_msg = Column(Text, nullable=True, default=None)
    next_check = Column(DateTime, nullable=True, default=None, index=True,
                        doc="used for querying jobs")
    job_started = Column(DateTime, nullable=True, default=None, index=True,
                         doc="last time the job started")
    failure_count = Column(Integer, nullable=False, default=0,
                           doc="failures since last success")
    size_is = Column(Integer, nullable=False, default=0,
                           doc="size last time checked")
    size_should = Column(Integer, nullable=False, default=0,
                         doc="size if known")
    priority = Column(Integer, nullable=False, default=0,
                      doc="priority for job scheduler. higher means more priority")

    collection_id = Column(Integer, ForeignKey('collection.id'), nullable=False, index=True)
    parent_id = Column(Integer, ForeignKey('entry.id'),  index=True)
    check_interval = Column(Interval(), default=None)

    children = relationship("Entry")
    meta = relationship("Meta", backref="entry")

    __tablename__ = 'entry'
    __table_args__ = (
        UniqueConstraint(parent_id, name, name='uix_entry_unique_name'),
    )

    EXPORT = (
        ("plugin", "updated", "state", "size", "name"),
        ("id", "type", "uuid", "url", "arguments", "created", "enabled", "size_should"),
        ("updated", "last_success", "last_failure",
         "next_check", "error_msg", "success_msg")
        )

    @property
    def size(self):
        # maybe do update here ?
        return self.size_is

    def set_error(self, msg):
        session = create_session()
        self.error_msg = msg
        now = datetime.datetime.now()
        self.last_failure = now
        self.failure_count += 1
        self.next_check = (now +
                           datetime.timedelta(
                               minutes=fib(min(self.failure_count, 10))))
        session.add(self)
        session.commit()

    def set_success(self, msg=None):
        session = create_session()
        self.last_error = None
        now = datetime.datetime.now()
        self.last_success = now
        self.success_msg = msg
        self.failure_count = 0
        self.next_check = (now +
                           self.get_first_set("check_interval"))
        self.state = EntryState.done.value
        session.add(self)
        session.commit()



    def is_collection(self):
        return self.type != 'SINGLE'

    def is_single(self):
        return self.type == 'SINGLE'


    def get_first_set(self, key):
        session = create_session()

        cur = self
        while True:
            rv = getattr(cur, key, None)
            if rv:
                print("rv", rv)
                return rv

            if not cur.parent_id:
                # check collection
                cur = session.query(Collection).filter(Collection.id==cur.collection_id).one()
                print("cur", cur)
                return getattr(cur, key, None)

            cur = session.query(Entry).filter(Entry.id==cur.parent_id).one()
            print(cur)

    @property
    def full_path(self):
        #session = object_session(self)
        session = create_session()
        parts = [self.name]
        cur = self
        #embed()
        while cur.parent_id != None:
            cur = session.query(Entry).filter(Entry.id==cur.parent_id).one()
            if cur.name != "/":
                parts.insert(0, cur.name)
            else:
                parts.insert(0, "")
        return pathjoin(parts)


    def __repr__(self):
        return "<Entry('%s' id='%s'>" %(self.name, self.id)

    def has_child(self, name):
        session = object_session(self)
        return session.query(Entry).filter(Entry.parent_id==self.id, Entry.name==name).count() > 0

    def get_child(self, name):
        session = object_session(self)
        return session.query(Entry).filter(Entry.parent_id==self.id, Entry.name==name).one()

    def descent(self, name):
        """
        Same as returning get_child(name) but may just change some internal
        structure of this Entry and return itself.
        Used for path transversal
        """
        return self.get_child(name)

    def dump(self, filter_=None, details=False, all_=False, dict_=False):
        rv = ModelMixin.dump(self, filter_=filter_, all_=all_, details=details, dict_=dict_)
        add_if(rv, 'last_success', self.last_success, filter_)
        add_if(rv, 'last_failure', self.last_failure, filter_)
        add_if(rv, 'failure_count', self.failure_count, filter_)
        #embed()
        if len(self.meta) and (filter_ == None or 'meta' in filter_):
            rv['meta'] = meta = {}
            for m in self.meta:
                name = m.name
                if m.plugin:
                    name = "%s::%s" %(m.plugin, m.name)
                rv['meta'][name] = m.value
        return rv



class Meta(Base):
    id = Column(Integer, primary_key=True)
    entry_id = Column(Integer, ForeignKey('entry.id'))
    plugin = Column(String(PLUGIN_NAME_LENGTH), index=True, doc="plugin handling matadata")
    type = Column(AEnum(*META_TYPES), index=True)
    name = Column(String(255), index=True, doc="name of value key")
    _value = Column(BLOB())

    __tablename__ = 'meta'


    def _get_value(self):
        if self.type == META_INTEGER:
            return int(self._value)
        elif self.type == META_STRING:
            return str(self._value)
        elif self.type == META_JSON:
            return json.loads(self._value)
        elif self.type == META_BLOB:
            return self._value
        elif self.type == META_NONE:
            return None
        else:
            raise exc.DatabaseError("can't decode meta type: %s" %self.type)

    def _set_value(self, value):
        if isinstance(value, str):
            self._value = value
            self.type = META_STRING
        elif isinstance(value, int):
            self._value = value
            self.type = META_INTEGER
        elif isinstance(value, dict):
            self._value = json.dumps(value)
            self.type = META_JSON
        elif isinstance(value, None):
            self._value = ""
            self.type = META_NONE
        else:
            self._value = value
            self.type = META_BLOB

    def _del_value(self):
        self._value = ""
        self.type = META_NONE

    value = property(_get_value, _set_value, _del_value)

    def __repr__(self):
        return "<Meta entry='%s' name='%s' plugin='%s'>" %(self.entry_id.full_path, self.name, self.plugin)
