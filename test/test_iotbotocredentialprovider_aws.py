import pytest
import datetime
import tempfile
import time
from copy import deepcopy
import json
import mock
import os
import botocore
import botocore.session
import shutil
import boto3
import requests
import iotbotocredentialprovider.AWS
from botocore.credentials import CredentialProvider, RefreshableCredentials
import requests.packages.urllib3.util.connection as urllib3_cn


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


class TestIotBotoCredentialProvider(object):
    def setup(self):
        self.registration_dir = tempfile.mkdtemp()
        self.metadata_file = os.path.join(self.registration_dir, "metadata.json")

        with open(self.metadata_file, "w") as f:
            json.dump(metadata, f)

        self.cp = iotbotocredentialprovider.AWS.IotBotoCredentialProvider(self.registration_dir)
        assert self.cp.path == self.registration_dir

    def teardown(self):
        shutil.rmtree(self.registration_dir)

    def test_iot_metadata_path(self):
        cp = iotbotocredentialprovider.AWS.IotBotoCredentialProvider()
        assert cp.path == iotbotocredentialprovider.AWS.default_iot_metadata_path

    def test_alternate_iot_metadata_path(self):
        iot_metadata_path = "/foo"
        cp = iotbotocredentialprovider.AWS.IotBotoCredentialProvider(iot_metadata_path)
        assert cp.path == iot_metadata_path

    def test_metadata(self):
        assert not hasattr(self.cp, "_metadata")
        md = self.cp.metadata
        assert hasattr(self.cp, "_metadata")
        assert self.cp._metadata == md
        assert md == metadata

    def test_credentials_cached(self):
        expire_time = datetime.datetime.utcnow() + datetime.timedelta(hours=1)
        self.cp._credentials = fake_credentials
        self.cp._credential_expiration = expire_time
        assert self.cp.credentials == fake_credentials

    @mock.patch.object(iotbotocredentialprovider.AWS.IotBotoCredentialProvider, "get_credentials")
    def test_credentials_expired(self, mock_get_credentials):
        expire_time = datetime.datetime.utcnow() - datetime.timedelta(hours=1)
        self.cp._credentials = fake_credentials
        self.cp._credential_expiration = expire_time

        mock_get_credentials.return_value = {}
        assert self.cp.credentials == {}
        assert mock_get_credentials.called is True

    @mock.patch.object(iotbotocredentialprovider.AWS.IotBotoCredentialProvider, "get_credentials")
    def test_refresh_credentials(self, mock_get_credentials):
        self.cp._credentials = "test"
        mock_get_credentials.return_value = fake_credentials
        self.cp._refresh_credentials()
        assert mock_get_credentials.called is True
        assert not hasattr(self.cp, "_credentials")

    @mock.patch.object(iotbotocredentialprovider.AWS.IotBotoCredentialProvider, "get_credentials")
    def test_fetch_metadata(self, mock_get_credentials):
        mock_get_credentials.return_value = fake_credentials
        boto3_creds = self.cp._fetch_metadata()
        assert mock_get_credentials.called is True
        assert boto3_creds == {
            'access_key': fake_credentials['accessKeyId'],
            'secret_key': fake_credentials['secretAccessKey'],
            'token': fake_credentials['sessionToken'],
            'expiry_time': fake_credentials['expiration']
        }

    @mock.patch.object(iotbotocredentialprovider.AWS.IotBotoCredentialProvider, "get_credentials")
    def test_load(self, mock_get_credentials):
        mock_get_credentials.return_value = fake_credentials
        res = self.cp.load()
        assert mock_get_credentials.called is True
        assert isinstance(res, RefreshableCredentials)

    @mock.patch.object(iotbotocredentialprovider.AWS.IotBotoCredentialProvider, "_fetch_metadata")
    def test_load_no_creds(self, mock_fetch_metadata):
        mock_fetch_metadata.return_value = {}
        res = self.cp.load()
        assert mock_fetch_metadata.called is True
        assert res is None

    def test_boto3_credentials(self):
        expire_time = datetime.datetime.utcnow() + datetime.timedelta(hours=1)
        self.cp._credentials = fake_credentials
        self.cp._credential_expiration = expire_time

        boto3_creds = self.cp.boto3_credentials
        assert boto3_creds == {
            'access_key': fake_credentials['accessKeyId'],
            'secret_key': fake_credentials['secretAccessKey'],
            'token': fake_credentials['sessionToken'],
            'expiry_time': fake_credentials['expiration']
        }

    def test_get_botocore_session(self):
        bc = self.cp.get_botocore_session()
        assert isinstance(bc, botocore.session.Session)

    def test_get_boto3_session(self):
        bs = self.cp.get_boto3_session("us-east-1")
        assert isinstance(bs, boto3.session.Session)

    @mock.patch("requests.get")
    def test_get_credentials_200(self, mock_requests_get):
        response = mock.Mock()
        response.status_code = 200
        response_data = {'credentials': fake_credentials}
        response.text = json.dumps(response_data)
        mock_requests_get.return_value = response

        res = self.cp.get_credentials()
        assert res == fake_credentials

    @mock.patch("requests.get")
    def test_get_credentials_403(self, mock_requests_get):
        response = mock.Mock()
        response.status_code = 403
        response_data = '{"message":"Access Denied"}'
        response.text = json.dumps(response_data)
        mock_requests_get.return_value = response

        with pytest.raises(iotbotocredentialprovider.AWS.IotBotoCredentialProviderError):
            self.cp.get_credentials()


class TestGetSessions(object):
    def setup(self):
        self.registration_dir = tempfile.mkdtemp()
        self.metadata_file = os.path.join(self.registration_dir, "metadata.json")

        with open(self.metadata_file, "w") as f:
            json.dump(metadata, f)

    def teardown(self):
        shutil.rmtree(self.registration_dir)

    def test_get_botocore_session(self):
        bc = iotbotocredentialprovider.AWS.get_botocore_session(iot_metadata_path=self.registration_dir)
        assert isinstance(bc, botocore.session.Session)

    def test_get_boto3_session(self):
        bs = iotbotocredentialprovider.AWS.get_boto3_session("us-east-1",
                                                             iot_metadata_path=self.registration_dir)
        assert isinstance(bs, boto3.session.Session)

    def test_configure_session(self):
        my_session = botocore.session.Session()
        original_component_list = my_session.get_component('credential_provider').providers
        for x in original_component_list:
            assert not isinstance(x, iotbotocredentialprovider.AWS.IotBotoCredentialProvider)

        botocore_session = iotbotocredentialprovider.AWS.configure_session(iot_metadata_path=self.registration_dir,
                                                                           session=my_session)

        new_component_list = set(botocore_session.get_component('credential_provider').providers)

        saw_cred_provider = False
        for x in new_component_list:
            if isinstance(x, iotbotocredentialprovider.AWS.IotBotoCredentialProvider):
                saw_cred_provider = True
        assert saw_cred_provider is True
