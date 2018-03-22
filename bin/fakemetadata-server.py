#!/usr/bin/env python3
from iotbotocredentialprovider.FakeMetadata import FakeMetadataServer, FakeMetadataRequestHandler

if __name__ == "__main__":
    f = FakeMetadataServer(FakeMetadataRequestHandler)
    f.run()
