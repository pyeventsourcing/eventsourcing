#!/usr/bin/env bash
wget https://download.axoniq.io/axonserver/AxonServer.zip
unzip AxonServer.zip
mv AxonServer-* axonserver
chmod +x axonserver/axonserver.jar
