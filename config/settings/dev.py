from .base import *  # noqa: F401,F403

DEBUG = True

# Prints emails to the console instead of sending real ones - lets you
# demo the absent-notification feature without SMTP credentials.
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
