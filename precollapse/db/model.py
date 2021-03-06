from sqlalchemy import Column, Integer, String, Text, BLOB, Enum, ForeignKey,\
                       DateTime, Interval, Boolean, asc, desc, UniqueConstraint, event, and_
from sqlalchemy.sql.expression import ColumnElement
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, backref, object_session, exc as sqlexc
from sqlalchemy import or_
import uuid
import json
import os
import datetime
import math

from sqlalchemy import create_engine
from IPython import embed

from . import Base, create_session
from ..utils import AlchemyEncoder, pathsplit, pathjoin, fib, SEnum
from .. import exceptions as exc


PLUGIN_NAME_LENGTH=30

class EntryType(SEnum):
    root = 'ROOT'
    directory = 'DIRECTORY'
    single = 'SINGLE'
    collection = 'COLLECTION'
    collection_member = 'COLLECTION_MEMBER'
    collection_directory = 'COLLECTION_DIR'
    collection_single = 'COLLECTION_SINGLE'


class MetaType(SEnum):
    string = 'STRING'
    json = 'JSON'
    integer = 'INTEGER'
    blob = 'BLOB'
    number = 'NUMBER'
    none = 'NONE'

class EntryState(SEnum):
    started = "STARTED"
    download = "DOWNLOAD"
    empty = 'EMPTY'
    failure = "FAILED"
    success = "SUCCESS"


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
    for d in dd:
        del rv[d]
    return rv



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
    description = Column(String(80), index=True)
    long_description = Column(Text)
    owner = Column(String(200), default=os.getlogin())
    owner_gpgid = Column(String(30))
    upstream_url = Column(Text(), doc="upstream url")
    uuid = Column(String(36), index=True, unique=True, default=suuid)
    created = Column(DateTime, default=datetime.datetime.now)
    updated = Column(DateTime, default=None)
    enabled = Column(Boolean, default=True)
    check_interval = Column(Interval(), default=datetime.timedelta(days=1))
    download_manager = Column(String(30))
    download_path = Column(String(255))

    #uname = Column(Collection.name.concat("-").concat(Collection.uuid).label("uname"))

    entries = relationship("Entry", backref="collection")

    __tablename__ = 'collection'

    EXPORT = (
        ("size", "owner", "changed", "name"),
        ("id", "upstream_url", "uuid", "created", "updated",
         "enabled", "check_interval", "owner_gpgid", "download_manager"),
        ("description", "long_description")
    )

    @property
    def basename(self):
        return self.name.replace("/", "_").replace("\\", "_")

    @staticmethod
    def create(session, *args, **kwargs):
        nc = Collection(*args, **kwargs)
        session.add(nc)
        root = Entry(name="/", type=EntryType.root, parent_id=None, collection=nc)
        session.add(root)
        return nc

    def mkdir(self, name):
        session = object_session(self)
        if self.type != EntryType.directory:
            raise exc.EntryTypeError("can't create directory under non directory")
        if self.has_child(name):
            raise exc.EntryExistsError("file: %s already exists" %name)
        root = Entry(name=name, type=EntryType.directory, parent_id=self.id, collection=self.collection.id)
        session.add(root)



    @staticmethod
    def lookup(session, path):
        sp = pathsplit(path)
        if len(sp) < 2:
            raise exc.ArgumentError("path needs to be aboslute")
        # find collection
        colname = sp[1]
        col = Collection.lookup_collection(session, colname)
        entries = col.lookup_path(session, sp[2:])
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
        return object_session(self).query(Entry).filter(Entry.collection == self, Entry.type.is_(EntryType.root), Entry.parent_id.is_(None)).one()

    @property
    def size(self):
        """
        Size of all entries that belong to the collection
        """
        return len(self.entries)

    @property
    def changed(self):
        return self.updated or self.created

    def export(self, formatter=None):
        if not formatter:
            from .formatter import yaml
            formatter = yaml.Formatter()
        return formatter.export(self)

class Entry(Base, ModelMixin):
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False, index=True, doc="name of directroy")
    type = Column(EntryType.sql_type(), nullable=False, index=True, default=EntryType.single)
    plugin = Column(String(PLUGIN_NAME_LENGTH), doc="plugin handling the entry")
    uuid = Column(String(36), index=True, unique=True, default=suuid)
    url = Column(Text)
    arguments = Column(Text)
    state = Column(EntryState.sql_type())
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
        # FIXME
        #UniqueConstraint(collection_id, type==EntryType.root , name='uix_entry_unique_name'),
    )

    EXPORT = (
        ("plugin", "type", "last_success", "state", "size", "name"),
        ("id", "last_failure", "uuid", "url", "arguments",
         "created", "enabled", "size_should"),
        ("updated", "last_success", "last_failure",
         "next_check", "error_msg", "success_msg")
        )

    def __init__(self, *args, **kwargs):
        if not 'collection_id' in kwargs:
            if 'collection' in kwargs:
                kwargs['collection_id'] = kwargs['collection'].id
            elif 'parent' in kwargs:
                kwargs['collection_id'] = kwargs['parent'].collection_id

        if 'parent' in kwargs:
            kwargs['parent_id'] = kwargs['parent'].id
            del kwargs['parent']

        return super(Entry, self).__init__(*args, **kwargs)

    @classmethod
    def jobs_filter(cls, session, now, with_empty=False, exclude=()):
        q = session.query(cls)\
                    .filter(or_(cls.next_check==None,
                                cls.next_check<now)) \
                    .filter(or_(cls.type.is_(EntryType.single),
                                cls.type.is_(EntryType.collection_single),
                                cls.type.is_(EntryType.collection)))
        if exclude:
            q = q.filter(cls.id.notin_(exclude))
        if not with_empty:
            q = q.filter(cls.state!=EntryState.empty)
        return q.order_by(desc(cls.priority))

    @property
    def size(self):
        # maybe do update here ?
        return self.size_is

    def set_error(self, msg, unhandled=False):
        session = create_session()
        self.error_msg = msg
        if unhandled:
            self.state = EntryState.empty
            self.next_check = None
            self.failure_count = 0
        else:
            now = datetime.datetime.now()
            self.state = EntryState.failure
            self.last_failure = now
            self.failure_count += 1
            self.next_check = (now +
                            datetime.timedelta(
                                minutes=fib(min(self.failure_count, 10))))
        session.add(self)
        session.commit()

    def set_success(self, msg=None):
        session = create_session()
        self.last_failure = None
        now = datetime.datetime.now()
        self.last_success = now
        self.success_msg = msg
        self.failure_count = 0
        self.next_check = (now +
                           self.get_first_set("check_interval"))
        self.state = EntryState.success
        session.add(self)
        session.commit()

    def restart(self):
        session = create_session()
        self.last_error = None
        now = datetime.datetime.now()
        self.next_check = (now)
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
                return rv

            if not cur.parent_id:
                # check collection
                cur = session.query(Collection).filter(Collection.id==cur.collection_id).one()
                return getattr(cur, key, None)

            cur = session.query(Entry).filter(Entry.id==cur.parent_id).one()

    @property
    def full_path(self):
        #session = object_session(self)
        session = create_session()
        parts = [self.name]
        cur = self
        while cur.parent_id != None:
            cur = session.query(Entry).filter(Entry.id==cur.parent_id).one()
            if cur.name != "/":
                parts.insert(0, cur.name)
            else:
                parts.insert(0, "")
        return pathjoin(parts)

    @property
    def system_path(self):
        #session = object_session(self)
        session = create_session()
        parts = [self.name]
        cur = self
        #embed()
        while cur.parent_id != None:
            cur = session.query(Entry).filter(Entry.id==cur.parent_id).one()
            if cur.name != "/":
                parts.insert(0, cur.name)
        return os.path.join(*parts)


    def __repr__(self):
        return "<Entry('%s' id='%s'>" %(self.name, self.id)

    def has_child(self, name):
        session = object_session(self)
        return session.query(Entry).filter(Entry.parent_id==self.id, Entry.name==name).count() > 0

    def get_child(self, name):
        session = object_session(self)
        return session.query(Entry).filter(Entry.parent_id==self.id, Entry.name==name).one()

    def get_or_create_child(self, name, args):
        session = object_session(self)
        try:
            rv = session.query(Entry).filter(Entry.parent_id==self.id, Entry.name==name).one()
            return rv, False
        except sqlexc.NoResultFound:
            rv = Entry(**args)
            session.add(rv)
            session.flush()
            return rv, True



    def descent(self, name):
        """
        Same as returning get_child(name) but may just change some internal
        structure of this Entry and return itself.
        Used for path transversal
        """
        return self.get_child(name)

    def dump(self, filter_=None, details=False, all_=False, dict_=False):
        rv = ModelMixin.dump(self, filter_=filter_, all_=all_, details=details, dict_=dict_)
        #add_if(rv, 'last_success', self.last_success, filter_)
        #add_if(rv, 'last_failure', self.last_failure, filter_)
        #add_if(rv, 'failure_count', self.failure_count, filter_)
        #embed()
        if len(self.meta) and (filter_ == None or 'meta' in filter_):
            rv['meta'] = meta = {}
            for m in self.meta:
                name = m.name
                if m.plugin:
                    name = "%s::%s" %(m.plugin, m.name)
                rv['meta'][name] = m.value
        return rv

    @staticmethod
    def validate_name(target, value, oldvalue, initiator):
        #print(target)
        #embed()
        if value.find("/") != -1:
            initiator.root_name = True
            if hasattr(target, "is_root") and not target.is_root:
                raise exc.ValueError("can't name contain /")
        else:
            initiator.root_name = False

    @staticmethod
    def validate_type(target, value, oldvalue, initiator):
        #print(target)
        #embed()
        initiator.is_root = value == EntryType.root
        if hasattr(target, "root_name") and target.root_name:
            raise exc.ValueError("name can't contain /")

    def set_meta(self, name, value, plugin=None):
        session = object_session(self)
        try:
            meta = session.query(Meta).filter(Meta.entry_id.is_(self.id),
                                              Meta.name.is_(name),
                                              Meta.plugin.is_(plugin)).one()
        except sqlexc.NoResultFound:
            meta = Meta(entry_id=self.id, name=name, plugin=plugin)
            session.add(meta)
            session.flush()
        meta.value = value
        session.flush()

    def get_meta(self, name, plugin=None, default=None):
        session = object_session(self)
        try:
            return session.query(Meta).filter(Meta.entry_id.is_(self.id),
                                              Meta.name.is_(name),
                                              Meta.plugin.is_(plugin)).one().value
        except sqlexc.NoResultFound:
            return default


event.listen(Entry.name, 'set', Entry.validate_name)
event.listen(Entry.type, 'set', Entry.validate_type)

class Meta(Base):
    id = Column(Integer, primary_key=True)
    entry_id = Column(Integer, ForeignKey('entry.id'))
    plugin = Column(String(PLUGIN_NAME_LENGTH), index=True, doc="plugin handling matadata")
    type = Column(MetaType.sql_type(), index=True)
    name = Column(String(255), index=True, doc="name of value key")
    _value = Column(BLOB())

    __tablename__ = 'meta'

    __table_args__ = (
        UniqueConstraint(entry_id, name, plugin, name='uix_meta_unique_name'),
    )

    def _get_value(self):
        if self.type == MetaType.integer:
            return int(self._value)
        elif self.type == MetaType.string:
            return str(self._value, "utf-8")
        elif self.type == MetaType.json:
            return json.loads(str(self._value, "utf-8"))
        elif self.type == MetaType.number:
            return float(str(self._value, "utf-8"))
        elif self.type == MetaType.blob:
            return self._value
        elif self.type in (MetaType.none, None):
            return None
        else:
            raise exc.DatabaseError("can't decode meta type: %s" %self.type)

    def _set_value(self, value):
        if isinstance(value, str):
            self._value = bytes(value, "utf-8")
            self.type = MetaType.string
        elif isinstance(value, int):
            self._value = bytes(str(value), "utf-8")
            self.type = MetaType.integer
        elif isinstance(value, float):
            self._value = bytes(str(value), "utf-8")
            self.type = MetaType.number
        elif isinstance(value, dict):
            self._value = bytes(json.dumps(value), "utf-8")
            self.type = MetaType.json
        elif value is None:
            self._value = bytes()
            self.type = MetaType.none
        else:
            self._value = bytes(value)
            self.type = MetaType.blob

    def _del_value(self):
        self._value = ""
        self.type = MetaType.none

    value = property(_get_value, _set_value, _del_value)

    def __repr__(self):
        return "<Meta entry='%s' name='%s' type='%s' plugin='%s'>" %(self.entry_id, self.name, self.type, self.plugin)
