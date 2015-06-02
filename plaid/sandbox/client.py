import json
import os
from plaid.client import Client


class MockResponse(object):
    def __init__(self, _json, status_code=200):
        self._json = _json
        self.status_code = status_code

    def json(self):
        return self._json


class SandboxClient(Client):
    # noinspection PyUnusedLocal,PyMissingConstructor
    def __init__(self, client_id, secret, access_token=None, http_request=None):
        self._raw_institutions = self._load_fixture('institutions.json')
        self._institutions = {i['type']: i for i in self._raw_institutions}
        self.access_token = access_token

    @staticmethod
    def _load_fixture(filename):
        dir_name = os.path.dirname(__file__)
        with open(os.path.join(dir_name, 'fixtures', filename)) as f:
            return json.loads(f.read())

    def institutions(self):
        return MockResponse(self._raw_institutions)

    def connect(self, account_type, username, password,
                options=None, pin=None):
        data = None
        institution = self._institutions[account_type]
        if username not in ('plaid_test', 'plaid_selections'):
            assert False
        if password != 'plaid_good':
            data = self._load_fixture('connect/invalid_password.json')
            status_code = 402
        elif institution['mfa']:
            status_code = 201
            if username == 'plaid_selections' and 'selections' in institution['mfa']:
                data = self._load_fixture('connect/selections.json')
            elif 'questions(3)' in institution['mfa']:
                data = self._load_fixture('connect/questions.json')
            elif 'code' in institution['mfa']:
                if options.get('list'):
                    data = self._load_fixture('connect/code_list.json')
                else:
                    data = self._load_fixture('connect/code_email.json')
        else:
            data = self._load_connect_success(account_type)
            status_code = 200

        if 'access_token' in data:
            self.access_token = "test_{}".format(account_type)
            data['access_token'] = self.access_token
        return MockResponse(data, status_code)

    def upgrade(self, upgrade_to):
        data = self._load_fixture('upgrade/success.json')
        data['access_token'] = self.access_token
        return MockResponse(data)

    def transactions(self, options=None):
        data = self._load_connect_success()
        data['access_token'] = self.access_token
        return MockResponse(data)

    def _load_connect_success(self, account_type=None):
        if not account_type:
            account_type = self.access_token.strip('test_')
        filename = {
            'wells': 'connect/no_transactions.json',
        }.get(account_type, 'connect/success.json')
        return self._load_fixture(filename)

    def connect_step(self, account_type, mfa, options=None):
        institution = self._institutions[account_type]
        data = None
        status_code = 200
        if not mfa:
            send_method = options['send_method']['type']
            status_code = 201
            data = self._load_fixture("connect/code_{}.json".format(send_method))
        else:
            if 'questions(3)' in institution['mfa']:
                if mfa == 'tomato':
                    data = self._load_connect_success(account_type)
                else:
                    data = self._load_fixture('connect/invalid_mfa.json')
                    status_code = 402
            elif 'code' in institution['mfa']:
                if mfa == '1234':
                    data = self._load_connect_success(account_type)
            else:
                mfa = json.loads(mfa)
                if isinstance(mfa, list):
                    if mfa == ['tomato', 'ketchup']:
                        data = self._load_connect_success(account_type)

        if 'access_token' in data:
            self.access_token = "test_{}".format(account_type)
            data['access_token'] = self.access_token
        return MockResponse(data, status_code)
