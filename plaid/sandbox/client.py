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
    # noinspection PyUnusedLocal,PyMissingConstructor
    def __init__(self, client_id, secret, access_token=None, http_request=None):
        self._raw_institutions = self._load_fixture('institutions.json')
        self._institutions = {i['type']: i for i in self._raw_institutions}
        self.access_token = access_token

    @staticmethod
    def post_initial_webhook(url, data):
        raise NotImplementedError

    @staticmethod
    def post_historical_webhook(url, data):
        raise NotImplementedError

    def get_account(self, access_token=None):
        access_token = access_token or self.access_token
        return json.loads(access_token[5:])

    def gen_access_token(self, account):
        self.access_token = 'test_%s' % json.dumps(account, sort_keys=True)
        return self.access_token

    @staticmethod
    def _load_fixture(filename):
        dir_name = os.path.dirname(__file__)
        with open(os.path.join(dir_name, 'fixtures', filename)) as f:
            return json.loads(f.read())

    @classmethod
    def _post_webhook(cls, account, event_type):
        data = SandboxClient._load_fixture('webhook/%s.json' % event_type)
        data['access_token'] = 'test_%s' % json.dumps(account, sort_keys=True)
        if event_type == 'initial':
            cls.post_initial_webhook(account['webhook'], data)
        elif event_type == 'historical':
            cls.post_historical_webhook(account['webhook'], data)

    def _process_connect_success(self, data, account=None):
        account = account or self.get_account()

        if account.get('login_only'):
            del data['transactions']
        if account.get('webhook') is not None:
            self._post_webhook(account, 'initial')
            self._post_webhook(account, 'historical')

    def _load_connect_success(self, account_type=None):
        if not account_type:
            account_type = self.get_account()['account_type']

        filename = {
            'wells': 'connect/no_transactions.json',
        }.get(account_type, 'connect/success.json')
        return self._load_fixture(filename)

    def institutions(self):
        return MockResponse(self._raw_institutions)

    def connect(self, account_type, username, password,
                options=None, pin=None):
        data = None
        success = False
        institution = self._institutions[account_type]
        if username not in ('plaid_test', 'plaid_selections'):
            assert False

        if password not in ERROR_PASSWORDS + ['plaid_good']:
            password = 'invalid_password'

        if password != 'plaid_good':
            data = self._load_fixture("connect/{}.json".format(password))
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
            success = True

        if 'access_token' in data:
            account = {
                'account_type': account_type,
                'login_only': options.get('login_only'),
                'webhook': options.get('webhook') if options.get('login_only') else None
            }
            self.gen_access_token(account)
            data['access_token'] = self.access_token
            if success:
                self._process_connect_success(data, account=account)
        return MockResponse(data, status_code)

    def upgrade(self, upgrade_to):
        account = self.get_account()
        institution = self._institutions[account['account_type']]

        if 'code' in institution['mfa']:
            data = self._load_fixture('connect/code_email.json')
            status_code = 201
        elif 'questions(3)' in institution['mfa']:
            data = self._load_fixture('connect/questions.json')
            status_code = 201
        elif 'selections' in institution['mfa']:
            data = self._load_fixture('connect/selections.json')
            status_code = 201
        else:
            data = self._load_fixture('upgrade/success.json')
            status_code = 200

        if 'access_token' in data:
            data['access_token'] = self.access_token
        return MockResponse(data, status_code)

    def transactions(self, options=None):
        data = self._load_connect_success()
        data['access_token'] = self.access_token
        return MockResponse(data)

    def connect_step(self, account_type, mfa, options=None):
        institution = self._institutions[account_type]
        data = None
        status_code = 200
        success = False
        if not mfa:
            if 'mask' in options['send_method']:
                send_method = {
                    'xxx-xxx-5309': 'phone',
                    't..t@plaid.com': 'email'
                }[options['send_method']['mask']]
            else:
                send_method = options['send_method']['type']

            status_code = 201
            data = self._load_fixture("connect/code_{}.json".format(send_method))
        else:
            if 'selections' in institution['mfa']:
                try:
                    mfa = json.loads(mfa)
                    if mfa == ['tomato', 'ketchup']:
                        data = self._load_connect_success(account_type)
                        success = True
                except:
                    # maybe the username wasn't plaid_selections? let it slide
                    pass
            if not success:
                if 'questions(3)' in institution['mfa'] and mfa == 'tomato':
                    data = self._load_connect_success(account_type)
                    success = True
                elif 'code' in institution['mfa'] and mfa == '1234':
                    data = self._load_connect_success(account_type)
                    success = True
                else:
                    data = self._load_fixture('connect/invalid_mfa.json')
                    status_code = 402

        if 'access_token' in data:
            data['access_token'] = self.access_token

        if success:
            self._process_connect_success(data)
        return MockResponse(data, status_code)

    def upgrade_step(self, upgrade_to, mfa, options=None):
        assert upgrade_to == 'auth'
        account = self.get_account()
        institution = self._institutions[account['account_type']]

        if 'code' in institution['mfa']:
            if mfa == '1234':
                data = self._load_fixture('upgrade/success.json')
                status_code = 200
            else:
                data = self._load_fixture('connect/invalid_mfa.json')
                status_code = 402
        elif 'questions(3)' in institution['mfa']:
            if mfa == 'tomato':
                data = self._load_fixture('upgrade/success.json')
                status_code = 200
            else:
                data = self._load_fixture('connect/invalid_mfa.json')
                status_code = 402
        elif 'selections' in institution['mfa']:
            mfa = json.loads(mfa)
            if mfa == ['tomato', 'ketchup']:
                data = self._load_fixture('upgrade/success.json')
                status_code = 200
            else:
                data = self._load_fixture('connect/invalid_mfa.json')
                status_code = 402
        else:
            assert False, 'upgrade_step should only be called if upgrade returns an MFA'

        if 'access_token' in data:
            data['access_token'] = self.access_token
        return MockResponse(data, status_code)

    def delete_connect(self):
        return MockResponse({})
