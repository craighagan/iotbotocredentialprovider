#!/usr/bin/env python3
import argparse
from iotbotocredentialprovider.FakeMetadata import FakeMetadataServer, FakeMetadataRequestHandler, PORT

# this will require that
# the following be set:
# /sbin/iptables -t nat -A OUTPUT -p tcp -d 169.254.169.254 --dport 80 -j DNAT --to-destination 127.0.0.1:51680
# /sbin/iptables -t nat -A OUTPUT -p tcp -d 169.254.170.2   --dport 80 -j DNAT --to-destination 127.0.0.1:51680

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, dest="port",
                        help="port to listen on defaults to %s" % PORT, required=False, default=PORT)
    parser.add_argument("--host", dest="host", default="0.0.0.0",
                        help="host to bind to defaults to 0.0.0.0")
    args = parser.parse_args()

    print("got args host=%s port=%s" % (args.host, args.port))
    f = FakeMetadataServer(FakeMetadataRequestHandler, host=args.host, port=args.port)
    f.run()
