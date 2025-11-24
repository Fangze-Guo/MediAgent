class AbcStep:
    def __init__(self, *args, **kwargs):
        pass
    
    def to_kwargs(self):
        raise NotImplementedError

    def run(self, step_dir, result_dir, **kwargs):
        raise NotImplementedError

    def save(self, step_dir, **kwargs):
        raise NotImplementedError

    @classmethod
    def load(cls, step_dir):
        raise NotImplementedError