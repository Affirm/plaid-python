import abc
import json
import os
from plaid.client import Client


ERROR_PASSWORDS = [
    'account_locked',
    'account_not_supported',
    'account_not_setup',
    'not_responding'
]


class MockResponse(object):
    def __init__(self, _json, status_code=200):
        self._json = _json
        self.status_code = status_code

    def json(self):
        return self._json


class SandboxClient(Client):
    __metaclass__ = abc.ABCMeta

    # noinspection PyUnusedLocal,PyMissingConstructor
    def __init__(self, client_id, secret, access_token=None, http_request=None):
        self._raw_institutions = self._load_fixture('institutions.json')
        self._institutions = {i['type']: i for i in self._raw_institutions}
        self._account = None

    @abc.abstractmethod
    def post_initial_webhook(self, url, data):
        raise NotImplementedError

    @abc.abstractmethod
    def post_historical_webhook(self, url, data):
        raise NotImplementedError

    def _post_webhooks(self):
        url = self._account.get('webhook')
        if url is not None:
            init_data = self._load_fixture('webhook/initial.json')
            hist_data = self._load_fixture('webhook/historical.json')
            self.post_initial_webhook(url, init_data)
            self.post_historical_webhook(url, hist_data)

    def _load_fixture(self, filename):
        dir_name = os.path.dirname(__file__)
        with open(os.path.join(dir_name, 'fixtures', filename)) as f:
            data = json.loads(f.read())

        if 'access_token' in data:
            data['access_token'] = self.get_access_token()
        if 'accounts' in data:
            account_type = self._account['account_type']
            for a in data['accounts']:
                a['_id'] = account_type + a['_id']

        return data

    def _load_connect_success(self, keep_transactions=False):
        account_type = self._account['account_type']
        filename = {
            'wells': 'connect/no_transactions.json',
        }.get(account_type, 'connect/success.json')

        data = self._load_fixture(filename)
        if not keep_transactions and self._account.get('login_only'):
            del data['transactions']
        return data

    def set_access_token(self, access_token):
        self._account = json.loads(self.access_token[5:])

    def get_access_token(self):
        return 'test_%s' % json.dumps(self._account, sort_keys=True)

    def institutions(self):
        return MockResponse(self._raw_institutions)

    def connect(self, account_type, username, password,
                options=None, pin=None, update=False):
        self._account = {
            'username': username,
            'account_type': account_type,
            'login_only': options.get('login_only'),
            'webhook': options.get('webhook') if options.get('login_only') else None
        }
        options = options or {}
        institution = self._institutions[account_type]

        if username not in ('plaid_test', 'plaid_selections'):
            assert False

        if password == 'plaid_good':
            if institution['mfa']:
                status_code = 201
                if self._account['username'] == 'plaid_selections' and 'selections' in institution['mfa']:
                    data = self._load_fixture('connect/selections.json')
                elif 'questions(3)' in institution['mfa']:
                    data = self._load_fixture('connect/questions.json')
                elif 'code' in institution['mfa']:
                    if options.get('list'):
                        data = self._load_fixture('connect/code_list.json')
                    else:
                        data = self._load_fixture('connect/code_email.json')
                else:
                    assert False, 'Bad Plaid sandbox^2 fixtures'
            else:
                status_code = 200
                data = self._load_connect_success()
                self._post_webhooks()
        elif password in ERROR_PASSWORDS:
            status_code = 402
            data = self._load_fixture("connect/{}.json".format(password))
        else:
            status_code = 402
            data = self._load_fixture("connect/invalid_password.json")

        return MockResponse(data, status_code)

    def connect_step(self, account_type, mfa, options=None, update=False):
        assert self._account['account_type'] == account_type

        institution = self._institutions[account_type]
        if mfa is not None:
            success = False
            if self._account['username'] == 'plaid_selections' and 'selections' in institution['mfa']:
                if set(json.loads(mfa)) == {'tomato', 'ketchup'}:
                    success = True
            elif 'questions(3)' in institution['mfa']:
                if mfa == 'tomato':
                    success = True
            elif 'code' in institution['mfa'] and mfa == '1234':
                if mfa == '1234':
                    success = True

            if success:
                status_code = 200
                data = self._load_connect_success()
            else:
                status_code = 402
                data = self._load_fixture('connect/invalid_mfa.json')
        else:
            if 'mask' in options['send_method']:
                send_method = {
                    'xxx-xxx-5309': 'phone',
                    't..t@plaid.com': 'email'
                }[options['send_method']['mask']]
            else:
                send_method = options['send_method']['type']

            status_code = 201
            data = self._load_fixture("connect/code_{}.json".format(send_method))

        return MockResponse(data, status_code)

    def upgrade(self, upgrade_to, options=None, update=False):
        options = options or {}
        institution = self._institutions[self._account['account_type']]

        if institution['mfa']:
            status_code = 201
            if 'code' in institution['mfa']:
                if options.get('list'):
                    data = self._load_fixture('connect/code_list.json')
                else:
                    data = self._load_fixture('connect/code_email.json')
            elif 'questions(3)' in institution['mfa']:
                data = self._load_fixture('connect/questions.json')
            elif self._account['username'] == 'plaid_selections' and 'selections' in institution['mfa']:
                data = self._load_fixture('connect/selections.json')
            else:
                assert False, 'Bad Plaid sandbox^2 fixtures'
        else:
            status_code = 200
            data = self._load_fixture('upgrade/success.json')

        return MockResponse(data, status_code)

    def upgrade_step(self, upgrade_to, mfa, options=None, update=False):
        assert upgrade_to == 'auth'

        institution = self._institutions[self._account['account_type']]
        if mfa is not None:
            success = False
            if 'code' in institution['mfa']:
                if mfa == '1234':
                    success = True
            elif 'questions(3)' in institution['mfa']:
                if mfa == 'tomato':
                    success = True
            elif 'selections' in institution['mfa']:
                if set(json.loads(mfa)) == {'tomato', 'ketchup'}:
                    success = True

            if success:
                status_code = 200
                data = self._load_fixture('upgrade/success.json')
            else:
                status_code = 402
                data = self._load_fixture('connect/invalid_mfa.json')
        else:
            if 'mask' in options['send_method']:
                send_method = {
                    'xxx-xxx-5309': 'phone',
                    't..t@plaid.com': 'email'
                }[options['send_method']['mask']]
            else:
                send_method = options['send_method']['type']

            status_code = 201
            data = self._load_fixture("connect/code_{}.json".format(send_method))

        return MockResponse(data, status_code)

    def transactions(self, options=None):
        data = self._load_connect_success(keep_transactions=True)
        return MockResponse(data)

    def delete_connect(self):
        return MockResponse({})
