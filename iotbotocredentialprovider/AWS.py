import boto3
import datetime
import requests
import json
import os
import logging
import botocore.auth
from botocore.credentials import CredentialProvider, RefreshableCredentials


log = logging.getLogger()
log.setLevel(logging.INFO)

default_iot_metadata_path = os.environ.get("FAKE_METADATA_PATH", "/AWSIoT")


class IotBotoCredentialProviderError(Exception):
    pass


class IotBotoCredentialProvider(CredentialProvider):
    def __init__(self, iot_metadata_path=default_iot_metadata_path):
        self.path = iot_metadata_path
        self._metadata_file = os.path.join(self.path, "metadata.json")

    @property
    def metadata(self):
        if not hasattr(self, "_metadata") or \
                os.stat(self._metadata_file) != self._metadata_mtime:

            self._populate_metadata()
        return self._metadata

    def _populate_metadata(self):
        with open(self._metadata_file) as f:
            self._metadata = json.load(f)
            self._metadata_mtime = os.stat(self._metadata_file).st_mtime

    @property
    def credentials(self):
        now = datetime.datetime.utcnow()

        if hasattr(self, "_credentials") and \
            hasattr(self, "_credential_expiration") and \
                self._credential_expiration > now:

            return self._credentials

        return self.get_credentials()

    def get_credentials(self):
        url = "%s/role-aliases/%s/credentials" % (self.metadata['credential_endpoint'],
                                                  self.metadata['role_alias_name'])

        headers = {"x-amzn-iot-thingname": self.metadata['device_name']}

        certificate_file = os.path.join(self.path, "%s.pem" % self.metadata['certificate_id'])
        private_key_file = os.path.join(self.path, "%s.privatekey" % self.metadata['certificate_id'])

        o = requests.get(url, cert=(certificate_file, private_key_file), headers=headers)
        response = json.loads(o.text)

        if o.status_code == 200:
            self._credentials = response["credentials"]
            self._credential_expiration = datetime.datetime.strptime(self._credentials['expiration'],
                                                                     botocore.auth.ISO8601)
            return self._credentials

        raise IotBotoCredentialProviderError(response)

    @property
    def boto3_credentials(self):
        return {
            'access_key': self.credentials['accessKeyId'],
            'secret_key': self.credentials['secretAccessKey'],
            'token': self.credentials['sessionToken'],
            'expiry_time': self.credentials['expiration']
        }

    def _refresh_credentials(self):
        if hasattr(self, "_credentials"):
            del self._credentials
        return self.credentials

    def _fetch_metadata(self):
        self._refresh_credentials()
        return self.boto3_credentials

    def load(self):
        fetcher = self._fetch_metadata

        metadata = fetcher()
        if not metadata:
            return None

        log.debug("Obtained for account %s will expire at %s",
                  self.metadata['account_id'], self.credentials['expiration'])

        return RefreshableCredentials.create_from_metadata(
            metadata,
            method=self.METHOD,
            refresh_using=fetcher,
        )

    def get_botocore_session(self, insert_before='iam-role'):
        session = botocore.session.Session()
        session.get_component('credential_provider').insert_before(insert_before, self)
        return session

    def get_boto3_session(self, region_name, insert_before='iam-role'):
        botocore_session = self.get_botocore_session(insert_before=insert_before)
        boto3_session = boto3.session.Session(
            botocore_session=botocore_session,
            region_name=region_name
        )
        return boto3_session


def configure_session(session, iot_metadata_path=default_iot_metadata_path, insert_before='iam-role'):
    """Configure a Botocore session to obtain credentials from AWS IoT.

    :param session: Existing botocore Session
    :type session: :class:`botocore.session.Session`
]   :param str iot_metadata_path: where to look for AWS IoT registration files (metadata.json,
            and certificates)
    :returns: Botocore session with auto-updating AWS IoT federated credentials
    :rtype: :class:`botocore.session.Session`

    .. code-block:: python

        import botocore
        import botocore.session
        import boto3

        region_name = 'us-east-1'
        account_id = '123456789'

        botocore_session = iotbotocredentialprovider.AWS.configure_session(
            session=botocore.session.Session(),
            account_id=account_id)

        # If application uses the default session
        boto3.setup_default_session(
            botocore_session=botocore_session,
            region_name=region_name
        )
        # If application needs individual sessions
        boto3_session = boto3.session.Session(
            botocore_session=botocore_session,
            region_name=region_name
        )


    """
    # we choose to configure our credentials before IAM
    session.get_component('credential_provider').insert_before(
        insert_before, IotBotoCredentialProvider(iot_metadata_path=iot_metadata_path))
    return session


def get_botocore_session(iot_metadata_path=default_iot_metadata_path, insert_before='iam-role'):
    """
    :param str iot_metadata_path=default_iot_metadata_path: The path to the IoT registration directory
        which includes metadata.json, the certificate, and its private key
    :param str insert_before: where in the list to insert the material set

    Obtain a botocore session using a iotbotocredentialprovider credential provider to renew credentials.

    """
    cp = IotBotoCredentialProvider(iot_metadata_path)
    return cp.get_botocore_session(insert_before)


def get_boto3_session(region_name, iot_metadata_path=default_iot_metadata_path, insert_before='iam-role'):
    """
    :param str iot_metadata_path=default_iot_metadata_path: The path to the IoT registration directory
        which includes metadata.json, the certificate, and its private key
    :param str region_name: aws region name, e.g. us-east-1, us-west-2, etc
    :param str insert_before: where in the list to insert the material set

    Obtain a boto3 session using a iotbotocredentialprovider credential provider to renew credentials.
    """
    cp = IotBotoCredentialProvider(iot_metadata_path=iot_metadata_path)
    return cp.get_boto3_session(region_name, insert_before)
