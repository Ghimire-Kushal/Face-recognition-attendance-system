import os
import threading

from django.apps import AppConfig


class AttendanceConfig(AppConfig):
    name = 'attendance'

    def ready(self):
        # runserver's autoreloader forks a parent process that never serves
        # requests - RUN_MAIN is only set in the actual worker process.
        if 'runserver' in os.sys.argv and os.environ.get('RUN_MAIN') != 'true':
            return
        # tests mock face_engine/matcher directly - a real model download would
        # make CI dependent on internet access and add tens of seconds per run.
        if 'test' in os.sys.argv:
            return
        _warm_up_in_background()


def _warm_up_in_background():
    def _load():
        from . import face_engine, matcher
        try:
            face_engine.get_app()
            matcher.refresh()
        except Exception:
            pass  # first real request will retry and surface the error normally

    threading.Thread(target=_load, daemon=True).start()
