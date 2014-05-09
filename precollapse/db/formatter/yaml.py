from . import yamlmap

class Formatter:
    def __init__(self):
        pass

    def export(self, collection):
        return yamlmap.generate(collection.dump(all_=True, dict_=True))
