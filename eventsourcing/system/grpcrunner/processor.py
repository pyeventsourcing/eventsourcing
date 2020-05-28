import json
import logging
import sys
from logging import DEBUG

from eventsourcing.system.grpcrunner.processor_server import ProcessorServer

if __name__ == "__main__":
    logging.basicConfig(level=DEBUG)
    application_topic = sys.argv[1]
    infrastructure_topic = sys.argv[2]
    setup_table = (json.loads(sys.argv[3]),)
    address = sys.argv[4]
    upstreams = json.loads(sys.argv[5])
    downstreams = json.loads(sys.argv[6])
    push_prompt_interval = json.loads(sys.argv[7])

    processor = ProcessorServer(
        application_topic,
        infrastructure_topic,
        setup_table,
        address,
        upstreams,
        downstreams,
        push_prompt_interval,
    )
