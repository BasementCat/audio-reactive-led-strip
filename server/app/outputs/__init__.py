from app import Task


class Output(Task):
    def __init__(self, global_config, output_config, *args, **kwargs):
        super().__init__(output_config['NAME'], global_config, *args, **kwargs)
        self.output_config = output_config
