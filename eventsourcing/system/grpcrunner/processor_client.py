from datetime import datetime

import grpc
from eventsourcing.utils.transcoding import ObjectJSONDecoder, ObjectJSONEncoder
from grpc._channel import _InactiveRpcError

from eventsourcing.system.grpcrunner.processor_pb2 import (
    CallRequest,
    Empty,
    FollowRequest,
    LeadRequest,
    NotificationsReply,
    NotificationsRequest,
    PromptRequest,
)
from eventsourcing.system.grpcrunner.processor_pb2_grpc import ProcessorStub


class ProcessorClient(object):
    def __init__(self):
        self.channel = None
        self.json_encoder = ObjectJSONEncoder()
        self.json_decoder = ObjectJSONDecoder()

    def connect(self, address, timeout=5):
        """
        Connect to client to server at given address.

        Calls ping() until it gets a response, or timeout is reached.
        """
        self.close()
        self.channel = grpc.insecure_channel(address)
        self.stub = ProcessorStub(self.channel)

        timer_started = datetime.now()
        while True:
            # Ping until get a response.
            try:
                self.ping()
            except _InactiveRpcError:
                if timeout is not None:
                    timer_duration = (datetime.now() - timer_started).total_seconds()
                    if timer_duration > 15:
                        raise Exception("Timed out trying to connect to %s" % address)
                else:
                    continue
            else:
                break

    # def __enter__(self):
    #     return self
    #
    # def __exit__(self, exc_type, exc_val, exc_tb):
    #     self.close()
    #
    def close(self):
        """
        Closes the client's GPRC channel.
        """
        if self.channel is not None:
            self.channel.close()

    def ping(self):
        """
        Sends a Ping request to the server.
        """
        request = Empty()
        response = self.stub.Ping(request, timeout=5)

    # def follow(self, upstream_name, upstream_address):
    #     request = FollowRequest(
    #         upstream_name=upstream_name, upstream_address=upstream_address
    #     )
    #     response = self.stub.Follow(request, timeout=5,)

    def prompt(self, upstream_name):
        """
        Prompts downstream server with upstream name, so that downstream
        process and promptly pull new notifications from upstream process.
        """
        request = PromptRequest(upstream_name=upstream_name)
        response = self.stub.Prompt(request, timeout=5)

    def get_notifications(self, section_id):
        """
        Gets a section of event notifications from server.
        """
        request = NotificationsRequest(section_id=section_id)
        notifications_reply = self.stub.GetNotifications(request, timeout=5)
        assert isinstance(notifications_reply, NotificationsReply)
        return notifications_reply.section

    def lead(self, application_name, address):
        """
        Requests a process to connect and then send prompts to given address.
        """
        request = LeadRequest(
            downstream_name=application_name, downstream_address=address
        )
        response = self.stub.Lead(request, timeout=5)

    def call_application(self, method_name, *args, **kwargs):
        """
        Calls named method on server's application with given args.
        """
        request = CallRequest(
            method_name=method_name,
            args=self.json_encoder.encode(args),
            kwargs=self.json_encoder.encode(kwargs),
        )
        response = self.stub.CallApplicationMethod(request, timeout=5)
        return self.json_decoder.decode(response.data)
