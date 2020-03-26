import botocore.auth
import platform
import datetime
import json
import logging
import os
import random
import sys
from threading import Timer
from .AWS import IotBotoCredentialProvider, default_iot_metadata_path

try:
    from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer
except ImportError:
    from http.server import BaseHTTPRequestHandler, HTTPServer


log = logging.getLogger()
log.setLevel(logging.INFO)

# hosts = ["169.254.169.254", "169.254.170.2"]
# loopback is preferred, this will require that
# the following be set:
# /sbin/iptables -t nat -A OUTPUT -p tcp -d 169.254.169.254 --dport 80 -j DNAT --to-destination 127.0.0.1:51680
# /sbin/iptables -t nat -A OUTPUT -p tcp -d 169.254.170.2   --dport 80 -j DNAT --to-destination 127.0.0.1:51680

HOST = "127.0.0.1"
PORT = 51680
HOST = "0.0.0.0"
ROLE_PATH = "/latest/meta-data/iam/security-credentials"
IDENTITY_PATH = "/latest/dynamic/instance-identity/document"
INSTANCE_ID_PATH = "/latest/meta-data/instance-id"
SIGNATURE_PATH = "/latest/dynamic/instance-identity/signature"
PLACEMENT_AVAILABILITY_ZONE_PATH = "/latest/meta-data/placement/availability-zone"
PING_PATH = "/ping"
PING_RESPONSE = "pong"
INSTANCE_DOCUMENT_OVERRIDE_FILE = os.path.join(default_iot_metadata_path, "instance_document_overrides.json")


def json_serial(obj):
    """
    JSON serializer for objects not serializable by default json code
    e.g. datetime.datetime objects
    """

    if isinstance(obj, (datetime.datetime, datetime.date)):
        return obj.isoformat()
    raise TypeError("Type %s not serializable" % type(obj))


class FakeMetadataCredentialProvider(IotBotoCredentialProvider):
    @property
    def role_name(self):
        return self.metadata['role_alias_name']

    @property
    def metadata_credentials(self):
        return {
            'AccessKeyId': self.credentials['accessKeyId'],
            'SecretAccessKey': self.credentials['secretAccessKey'],
            'Token': self.credentials['sessionToken'],
            'Expiration': self.credentials['expiration'],
            'Code': 'Success',
            'Type': 'AWS-HMAC',
            'LastUpdated': self.credentials['expiration']
        }

    @property
    def account(self):
        return self.metadata["account_id"]

    @property
    def region(self):
        return self.metadata["region"]

    def update_timer(self, refresh_time_seconds=300):
        self._update_timer = Timer(refresh_time_seconds, self.get_credentials)
        self._update_timer.daemon = True
        logging.info("will refresh creds in %s", refresh_time_seconds)
        self._update_timer.start()

    def cancel_timer(self):
        if hasattr(self, "_update_timer"):
            self._update_timer.cancel()

    def get_refresh_seconds(self):
        if not hasattr(self, "_credential_expiration"):
            expire_time = datetime.datetime.strptime(self.credentials['expiration'],
                                                     botocore.auth.ISO8601)
            self._credential_expiration = expire_time

        now = datetime.datetime.utcnow()
        expiration = (self._credential_expiration - now).seconds
        logging.debug("credentials expire in %s seconds", expiration)
        refresh_jitter = int(0.1 * expiration)
        if refresh_jitter < 30:
            refresh_jitter = 30
        refresh_time = 0.7 * expiration + random.randrange(0, refresh_jitter)
        return refresh_time

    def get_credentials(self):
        result = super(FakeMetadataCredentialProvider, self).get_credentials()
        self.update_timer(self.get_refresh_seconds())
        return result


class FakeMetadataRequestHandler(BaseHTTPRequestHandler):
    """
    This implements the request handling that we'll
    need, it responds very simply:

    if user requests ROLE_PATH, respond with the role name we serve
    if user requests ROLE_PATH + role name, respond with credentials
        obtained by self.get_credentials(RoleArn)
    otherwise, return a 404

    This class shouldn't directly be used, instead use a child
    which implements get_credentials

    """
    # we want to use the same provider across all class instances
    # to allow for caching
    credential_provider = FakeMetadataCredentialProvider()

    def get_credentials(self, RoleArn=None):
        return FakeMetadataRequestHandler.credential_provider.metadata_credentials

    def get_role(self):
        return FakeMetadataRequestHandler.credential_provider.role_name

    def get_placement_availability_zone(self):
        result = "fake"
        try:
            override = json.load(open(INSTANCE_DOCUMENT_OVERRIDE_FILE))
            result = override.get("availabilityZone", result)
        except (ValueError, IOError):
            pass

        return result

    def get_identity_doc(self):
        result = {
            "accountId": FakeMetadataRequestHandler.credential_provider.account,
            "region": FakeMetadataRequestHandler.credential_provider.region,
            "architecture": platform.machine(),
            "availabilityZone": "fake",
            "imageId": "fake",
            "instanceId": FakeMetadataRequestHandler.credential_provider.metadata['device_name'],
            "instanceType": "f1.fake",
            "privateIp": "fake",
        }

        try:
            override = json.load(open(INSTANCE_DOCUMENT_OVERRIDE_FILE))
            result.update(override)
        except (ValueError, IOError):
            pass

        return result

    def do_PUT(self):
        return

    def do_GET(self):
        our_role = self.get_role()
        our_path = ROLE_PATH + "/" + self.get_role()
        return_code = 200
        response_prefix = ""
        if sys.version_info.major == 3:
            response_prefix = "HTTP/1.0 200 OK\n"

        start_doc = "%sServer: %s\nDate: %s\nContent-Type: text/plain\n\n" % \
           (response_prefix, self.version_string(), self.date_time_string())
        result = ""

        stripped_path = self.path.rstrip("/")
        if stripped_path == PING_PATH:
            result = PING_RESPONSE
        elif stripped_path == ROLE_PATH:
            # client is requesting we return the role name
            result = our_role
        elif stripped_path == PLACEMENT_AVAILABILITY_ZONE_PATH:
            result = self.get_placement_availability_zone()
        elif stripped_path == IDENTITY_PATH:
            result = json.dumps(self.get_identity_doc(), default=json_serial, indent=4)
        elif stripped_path == INSTANCE_ID_PATH:
            result = self.get_identity_doc().get("instanceId")
        elif stripped_path == SIGNATURE_PATH:
            result = "bad"
        elif stripped_path != our_path:
            # client asked for a role we don't serve
            return_code = 404
            if sys.version_info.major == 3:
                response_prefix = "HTTP/1.0 404 Not Found\n"

            start_doc = "%sContent-Type: text/html\n" % response_prefix
            result = """
<?xml version="1.0" encoding="iso-8859-1"?>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN"
         "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en" lang="en">
 <head>
  <title>404 - Not Found</title>
 </head>
 <body>
  <h1>404 - Not Found</h1>
 </body>
</html>
"""
        else:
            # client asked for credentials
            credentials = self.get_credentials()
            result = json.dumps(credentials, default=json_serial, indent=4)
        self.send_response(return_code)
        self.wfile.write(bytes(start_doc.encode("utf-8") + result.encode("utf-8")))


class FakeMetadataServer(object):
    """
    This creates a server which acts like METADATA
    You will need to have certain traffic directed to it, e.g.

    /sbin/sysctl -w net.ipv4.conf.all.route_localnet=1
    /sbin/iptables -t nat -A PREROUTING -p tcp -d 169.254.169.254 --dport 80 -j DNAT --to-destination 127.0.0.1:51679

    TBD: may not need to redirect the container address, this may
    be best left to ECSAgent, the container address is:

    /sbin/iptables -t nat -A PREROUTING -p tcp -d 169.254.170.2   --dport 80 -j DNAT --to-destination 127.0.0.1:51679

    """

    def __init__(self, request_handler, host=None, port=None):
        self.request_handler = request_handler
        if host is None:
            self.host = HOST
        else:
            self.host = host

        self.port = port
        if self.port is None:
            self.port = PORT

        print(" server for %s:%s" % (self.host, self.port))
        self.server = HTTPServer((self.host, self.port), self.request_handler)

    def stop(self):
        self.request_handler.credential_provider.cancel_timer()
        self.server.shutdown()
        self.server.server_close()

    def run(self):
        print("run server on %s:%s" % (self.host, self.port))
        self.server.serve_forever()
        self.request_handler.credential_provider.cancel_timer()
        self.server.shutdown()
        self.server.server_close()
