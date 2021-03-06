class CollapseException(Exception):
    pass

class DatabaseError(CollapseException):
    pass

class ArgumentError(CollapseException):
    pass

class DependencyMissing(CollapseException):
    pass

class CommandMissing(DependencyMissing):
    pass

class ModuleMissing(DependencyMissing):
    pass

class CollectionException(CollapseException):
    pass

class EntryError(CollapseException):
    pass

class ValueError(EntryError):
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

class DownloadManagerException(CollapseException):
    pass
