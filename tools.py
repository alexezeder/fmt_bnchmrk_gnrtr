from datetime import datetime


class StepPrinter:
    def __init__(self, message: str, is_fail_allowed: bool = False):
        self.message: str = message
        self.fail_allowed: bool = is_fail_allowed

    def __enter__(self):
        print(self.message + '...', end='', flush=True)
        self.start_time = datetime.now()

    def __exit__(self, exception_type, exception_value, traceback):
        time_delta = datetime.now() - self.start_time
        if exception_type is None:
            print(' done in {:.2f}s.'.format(time_delta.total_seconds()))
        else:
            if self.fail_allowed:
                print(' failed in {:.2f}s, but who cares! With message: {}.'.format(time_delta.total_seconds(),
                                                                                    exception_value))
            else:
                print(' failed! With message: {}\nExiting...'.format(exception_value))
                raise
        return True
