import os
import json

class Config():
    
    KEY_ITERATION_COUNT = 'ITERATION_COUNT'
    KEY_USE_EMME = 'USE_EMME'
    KEY_LOG_LEVEL = 'LOG_LEVEL'
    def __init__(self):
        self.__config = None

    @staticmethod
    def read_from_file(path="dev-config.json"):
        print 'reading configuration from file "{}"'.format(path)
        instance = Config()

        with open(path, 'r') as f:
            instance.__config = json.load(f)

        print 'read {} config variables'.format(len(instance.__config))
        return instance

    def get_value(self, key):
        from_env = os.environ.get(key, None)
        if from_env:
            return from_env
        else:
            return self.__config[key]
