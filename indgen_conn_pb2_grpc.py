# Generated by the gRPC Python protocol compiler plugin. DO NOT EDIT!
import grpc

import indgen_conn_pb2 as indgen__conn__pb2


class GreeterStub(object):
    """The query service definition
    """

    def __init__(self, channel):
        """Constructor.

        Args:
            channel: A grpc.Channel.
        """
        self.SayHello = channel.unary_unary(
                '/indgen_conn.Greeter/SayHello',
                request_serializer=indgen__conn__pb2.HelloRequest.SerializeToString,
                response_deserializer=indgen__conn__pb2.HelloReply.FromString,
                )
        self.SendLemma = channel.unary_unary(
                '/indgen_conn.Greeter/SendLemma',
                request_serializer=indgen__conn__pb2.Lemma.SerializeToString,
                response_deserializer=indgen__conn__pb2.Ack.FromString,
                )


class GreeterServicer(object):
    """The query service definition
    """

    def SayHello(self, request, context):
        """Sends a greeting
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def SendLemma(self, request, context):
        """Sends a lemma to python server
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')


def add_GreeterServicer_to_server(servicer, server):
    rpc_method_handlers = {
            'SayHello': grpc.unary_unary_rpc_method_handler(
                    servicer.SayHello,
                    request_deserializer=indgen__conn__pb2.HelloRequest.FromString,
                    response_serializer=indgen__conn__pb2.HelloReply.SerializeToString,
            ),
            'SendLemma': grpc.unary_unary_rpc_method_handler(
                    servicer.SendLemma,
                    request_deserializer=indgen__conn__pb2.Lemma.FromString,
                    response_serializer=indgen__conn__pb2.Ack.SerializeToString,
            ),
    }
    generic_handler = grpc.method_handlers_generic_handler(
            'indgen_conn.Greeter', rpc_method_handlers)
    server.add_generic_rpc_handlers((generic_handler,))


 # This class is part of an EXPERIMENTAL API.
class Greeter(object):
    """The query service definition
    """

    @staticmethod
    def SayHello(request,
            target,
            options=(),
            channel_credentials=None,
            call_credentials=None,
            compression=None,
            wait_for_ready=None,
            timeout=None,
            metadata=None):
        return grpc.experimental.unary_unary(request, target, '/indgen_conn.Greeter/SayHello',
            indgen__conn__pb2.HelloRequest.SerializeToString,
            indgen__conn__pb2.HelloReply.FromString,
            options, channel_credentials,
            call_credentials, compression, wait_for_ready, timeout, metadata)

    @staticmethod
    def SendLemma(request,
            target,
            options=(),
            channel_credentials=None,
            call_credentials=None,
            compression=None,
            wait_for_ready=None,
            timeout=None,
            metadata=None):
        return grpc.experimental.unary_unary(request, target, '/indgen_conn.Greeter/SendLemma',
            indgen__conn__pb2.Lemma.SerializeToString,
            indgen__conn__pb2.Ack.FromString,
            options, channel_credentials,
            call_credentials, compression, wait_for_ready, timeout, metadata)
