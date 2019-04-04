from grpc_tools import protoc

protoc.main((
    '',
    '-I../protos',
    '--python_out=./chat_client',
    '--grpc_python_out=./chat_client',
    '../protos/chat.proto',
))
