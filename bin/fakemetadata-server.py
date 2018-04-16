#!/usr/bin/env python3
from iotbotocredentialprovider.FakeMetadata import FakeMetadataServer, FakeMetadataRequestHandler

# this will require that
# the following be set:
# /sbin/iptables -t nat -A OUTPUT -p tcp -d 169.254.169.254 --dport 80 -j DNAT --to-destination 127.0.0.1:51680
# /sbin/iptables -t nat -A OUTPUT -p tcp -d 169.254.170.2   --dport 80 -j DNAT --to-destination 127.0.0.1:51680

if __name__ == "__main__":
    f = FakeMetadataServer(FakeMetadataRequestHandler)
    f.run()
