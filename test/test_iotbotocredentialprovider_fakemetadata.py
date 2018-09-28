import datetime
import pytest
import mock
from copy import deepcopy
import os
import json
import shutil
import tempfile
import time
import botocore.auth
import iotbotocredentialprovider.AWS
import iotbotocredentialprovider.FakeMetadata


metadata = {
    'account_id': '0123456789',
    'certificate_id': 'mycertificateid',
    'credential_endpoint': 'https://xyzzy.credentials.iot.us-east-1.amazonaws.com',
    'device_name': 'test1',
    'region': 'us-test-1',
    'role_alias_name': 'TestRole'
}

fake_credentials = {
    'accessKeyId': 'MyAccessKey',
    'expiration': '2018-03-12T03:52:05Z',
    'secretAccessKey': 'MySecretAccessKey',
    'sessionToken': 'MySessionToken',
}


class TestFakeMetadata(object):
    def setup(self):
        self.registration_dir = tempfile.mkdtemp()
        self.metadata_file = os.path.join(self.registration_dir, "metadata.json")

        with open(self.metadata_file, "w") as f:
            json.dump(metadata, f)

        self.cp = iotbotocredentialprovider.FakeMetadata.FakeMetadataCredentialProvider(self.registration_dir)
        assert self.cp.path == self.registration_dir

    def teardown(self):
        shutil.rmtree(self.registration_dir)


    def test_metadata_credentials(self):
        expire_time = datetime.datetime.utcnow() + datetime.timedelta(hours=1)
        self.cp._credentials = fake_credentials
        self.cp._credential_expiration = expire_time

        metadata_creds = self.cp.metadata_credentials

        del metadata_creds["LastUpdated"]
        assert metadata_creds == {
            'AccessKeyId': fake_credentials['accessKeyId'],
            'SecretAccessKey': fake_credentials['secretAccessKey'],
            'Token': fake_credentials['sessionToken'],
            'Expiration': fake_credentials['expiration'],
            'Code': 'Success',
            'Type': 'AWS-HMAC',
        }

    def test_role_name(self):
        assert self.cp.role_name == metadata['role_alias_name']

    @mock.patch.object(iotbotocredentialprovider.FakeMetadata.FakeMetadataCredentialProvider, "get_credentials")
    def test_update_timer(self, mock_get_credentials):
        self.cp.update_timer(refresh_time_seconds=1)
        time.sleep(2)
        assert mock_get_credentials.called is True

    def test_cancel_timer_no_timer(self):
        assert not hasattr(self.cp, "_update_timer")
        self.cp.cancel_timer()
        assert not hasattr(self.cp, "_update_timer")

    @mock.patch.object(iotbotocredentialprovider.FakeMetadata.FakeMetadataCredentialProvider, "get_credentials")
    def test_cancel_timer(self, mock_get_credentials):
        self.cp.update_timer(refresh_time_seconds=2)
        time.sleep(1)
        self.cp.cancel_timer()
        time.sleep(2)
        assert mock_get_credentials.called is False

    @mock.patch.object(iotbotocredentialprovider.FakeMetadata.FakeMetadataCredentialProvider, "get_credentials")
    def test_get_refresh_seconds(self, mock_get_credentials):
        mock_get_credentials.return_value = deepcopy(fake_credentials)
        expire_time = datetime.datetime.utcnow() + datetime.timedelta(hours=1)
        mock_get_credentials.return_value['expiration'] = expire_time.strftime(botocore.auth.ISO8601)

        refresh = self.cp.get_refresh_seconds()
        assert refresh > 0.7*3600
        assert refresh < 3600
