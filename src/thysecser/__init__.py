import datetime
import logging
import os
import requests

__version__ = '2022.2'

log = logging.getLogger(__name__)


class SecretServerClient:
    def __init__(self, username: str = None, password: str = None, hostname: str = None):
        self.username = username
        if self.username is None:
            self.username = os.getenv('SECRET_SERVER_USERNAME')
        self.password = password
        if self.password is None:
            self.password = os.getenv('SECRET_SERVER_PASSWORD')
        self.hostname = hostname
        if self.hostname is None:
            self.hostname = os.getenv('SECRET_SERVER_HOSTNAME')
        self.token = None
        self.token_expiration = None
        self.s = requests.Session()

    def delete_secret(self, secret_id: int):
        url = f'https://{self.hostname}/SecretServer/api/v1/secrets/{secret_id}'
        if self.token_expired():
            self.refresh_token()
        self.s.delete(url)

    def get_secrets(self, params: dict = None):
        url = f'https://{self.hostname}/SecretServer/api/v1/secrets'
        _params = params or {}
        while True:
            if self.token_expired():
                self.refresh_token()
            r = self.s.get(url, params=_params)
            log.debug(f'Sent request to {r.url}')
            r.raise_for_status()
            payload = r.json()
            log.debug(f'Response: {payload}')
            yield from payload.get('records')
            if payload.get('hasNext'):
                _params.update({
                    'skip': payload.get('nextSkip'),
                })
            else:
                break

    def post_secrets(self, folder_id: int, secret_name: str, secret_username: str, secret_password: str):
        url = f'https://{self.hostname}/SecretServer/api/v1/secrets'
        if self.token_expired():
            self.refresh_token()
        payload = {
            'folderId': folder_id,
            'items': [
                {
                    'fieldId': os.getenv('SECRET_SERVER_PASSWORD_FIELD_ID'),
                    'itemValue': secret_password,
                },
                {
                    'fieldId': os.getenv('SECRET_SERVER_USERNAME_FIELD_ID'),
                    'itemValue': secret_username,
                },
            ],
            'name': secret_name,
            'secretTemplateId': os.getenv('SECRET_SERVER_TEMPLATE_ID'),
            'siteId': os.getenv('SECRET_SERVER_SITE_ID'),
        }
        r = self.s.post(url, json=payload)
        r.raise_for_status()

    def refresh_token(self):
        url = f'https://{self.hostname}/SecretServer/oauth2/token'
        data = {
            'grant_type': 'password',
            'password': self.password,
            'username': self.username,
        }
        r = self.s.post(url, data=data)
        payload = r.json()
        self.token = payload.get('access_token')
        self.token_expiration = datetime.datetime.now() + datetime.timedelta(seconds=payload.get('expires_in'))
        self.s.headers.update({
            'Authorization': f'Bearer {self.token}'
        })

    def token_expired(self):
        return self.token_expiration is None or self.token_expiration < datetime.datetime.now()
