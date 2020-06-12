#!/usr/bin/env bash
mkdir -p dynamodb_local
wget -O dynamodb_local/dynamodb_local_latest.tar.gz https://s3.us-west-2.amazonaws.com/dynamodb-local/dynamodb_local_latest.tar.gz
tar --cd dynamodb_local -xzf dynamodb_local/dynamodb_local_latest.tar.gz
rm dynamodb_local/dynamodb_local_latest.tar.gz
