import os

def which(program):
    def is_exe(fpath):
        return os.path.isfile(fpath) and os.access(fpath, os.X_OK)

    if is_exe(program):
        return program

    for path in os.environ["PATH"].split(os.pathsep):
        path = path.strip('"')
        exe_file = os.path.join(path, program)
        if is_exe(exe_file):
            return exe_file

    return None

from sqlalchemy.ext.declarative import DeclarativeMeta
import json

class AlchemyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj.__class__, DeclarativeMeta):
            # an SQLAlchemy class
            fields = {}
            for field in [x for x in dir(obj) if not x.startswith('_') and x != 'metadata']:
                print(field)
                #data = obj.__getattribute__(field)
                data = 1
                try:
                    json.dumps(data) # this will fail on non-encodable values, like other classes
                    fields[field] = data
                except TypeError:
                    fields[field] = None
                    # a json-encodable dict
            return fields
        return json.JSONEncoder.default(self, obj)

def pathsplit(pathstr, maxsplit=None):
    """split relative path into list"""
    path = [pathstr]
    while True:
        oldpath = path[:]
        path[:1] = list(os.path.split(path[0]))
        if path[0] == '':
            path = path[1:]
        elif path[1] == '':
            path = path[:1] + path[2:]
        if path == oldpath:
            return path
        if maxsplit is not None and len(path) > maxsplit:
            return path

def pathjoin(parts):
    # the root element has a special / name
    p = parts[0:1] + list(map(lambda x: x.replace("/", "\\/"), parts[1:]))
    return "/".join(p)

def abspath(*args):
    path = os.path.join(*args)
    # we want trailing /
    suffix = (path[-1] == "/" and path != "/") and "/" or ""
    return os.path.abspath(path) + suffix

def get_prompt(path):
    return '(precollapse) %s: ' %path
