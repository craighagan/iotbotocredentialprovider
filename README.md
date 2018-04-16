# iotbotocredentialprovider
AWS IoT Credential Provider: create boto sessions which obtain and renew credentials from an AWS IoT device certificate

## Dependencies

This depends upon devices which were provisioned via iotdeviceprovisioner
and have a properly configured /AWSIoT directory with a certificate, private key, and metadata.json file created.

## IoT Documentation

https://docs.aws.amazon.com/iot/latest/developerguide/authorizing-direct-aws.html


## Using

```python
import iotbotocredentialprovider.AWS

session = iotbotocredentialprovider.AWS.get_boto3_session(region_name="us-east-2")

s3_client = session.client('s3')
s3_client.list_buckets()
```
## Using the metadata server

### Configure iptables

```
/sbin/iptables -t nat -A OUTPUT -p tcp -d 169.254.169.254 --dport 80 -j DNAT --to-destination 127.0.0.1:51680
/sbin/iptables -t nat -A OUTPUT -p tcp -d 169.254.170.2   --dport 80 -j DNAT --to-destination 127.0.0.1:51680
```

### Start the server

Create a script/service which runs this:
```
python /usr/local/bin/fakemetadata-server.py
```

### Use your aws tools

Example:

```
aws s3 ls s3://
```


