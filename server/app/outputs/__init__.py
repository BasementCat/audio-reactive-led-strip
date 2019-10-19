from app.lib.threads import Thread


class OutputThread(Thread):
    def __init__(self, global_config, output_config, *args, **kwargs):
        super().__init__(output_config['NAME'], global_config, *args, **kwargs)
        self.output_config = output_config
        self.is_output = True
