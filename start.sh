#!/bin/bash
docker run --name "live_server" -d --restart="on-failure" -p 127.0.0.1:8912:8000 --net="host" rrls 
#docker run --name "live_server" -d --restart="on-failure" -p 127.0.0.1:8912:8000 rrls 
