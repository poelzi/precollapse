class CollapseException(Exception):
    pass

class DatabaseError(CollapseException):
    pass

class ArgumentError(CollapseException):
    pass

class CommandMissing(CollapseException):
    pass

class CollectionException(CollapseException):
    pass

class EntryError(CollapseException):
    pass

class EntryExistsError(EntryError):
    pass

class EntryTypeError(EntryError):
    pass

class EntryNotFound(EntryError):
    pass

class ParentNotFound(EntryNotFound):
    pass

class CollectionNotFound(EntryNotFound):
    pass



class CollectionMultipleChoices(CollapseException):
    pass
