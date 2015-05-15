from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.core.mail.backends.base import BaseEmailBackend
from django.core.mail.message import sanitize_address

import requests


class MailgunAPIError(Exception):
    pass


class MailgunBackend(BaseEmailBackend):
    """A Django Email backend that uses mailgun.
    """

    def __init__(self, fail_silently=False, *args, **kwargs):
        access_key, server_name = (kwargs.pop('access_key', None),
                                   kwargs.pop('domain_name', None))

        super(MailgunBackend, self).__init__(fail_silently=fail_silently, *args, **kwargs)

        try:
            self._access_key = access_key or getattr(settings, 'MAILGUN_API_KEY')
            self._domain_name = server_name or getattr(settings, 'MAILGUN_DOMAIN_NAME')
        except AttributeError:
            if self.fail_silently:
                self._access_key, self._domain_name = None, None
            else:
                raise

        self._api_url = "https://api.mailgun.net/v3/{0}/".format(self._domain_name)

    def open(self):
        """Stub for open connection, all sends are done over HTTP POSTs
        """
        pass

    def close(self):
        """Close any open HTTP connections to the API server.
        """
        pass

    def _send(self, email_message):
        """A helper method that does the actual sending."""
        if not email_message.recipients():
            return False

        clean_all = lambda address: [sanitize_address(a, email_message.encoding) for a in address]
        text = email_message.content_subtype == 'plain' and email_message.body or None
        html = email_message.content_subtype == 'html' and email_message.body or None

        if isinstance(email_message, EmailMultiAlternatives):
            for body, mime in email_message.alternatives:
                if mime == 'text/html':
                    html = body

        try:
            r = requests.post(
                self._api_url + "messages",
                auth=("api", self._access_key),
                data={
                    'from': clean_all([email_message.from_email]),
                    'to': clean_all(email_message.to),
                    'cc': clean_all(email_message.cc),
                    'bcc': clean_all(email_message.bcc),
                    'subject': email_message.subject,
                    'text': text,
                    'html': html,
                },
                files=[
                    ('attachment', (filename, content))
                    for filename, content, mimetype in [
                        attachment for attachment in email_message.attachments
                        if isinstance(attachment, tuple)
                        ]
                    ]
            )
        except Exception:
            if not self.fail_silently:
                raise
            return False

        if r.status_code != 200:
            if not self.fail_silently:
                raise MailgunAPIError(r)
            return False

        return True

    def send_messages(self, email_messages):
        """Sends one or more EmailMessage objects and returns the number of
        email messages sent.
        """
        if not email_messages:
            return

        num_sent = 0
        for message in email_messages:
            if self._send(message):
                num_sent += 1

        return num_sent
