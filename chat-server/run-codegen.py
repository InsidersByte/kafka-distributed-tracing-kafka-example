from grpc_tools import protoc

protoc.main((
    '',
    '-I../protos',
    '--python_out=./chat_server',
    '--grpc_python_out=./chat_server',
    '../protos/chat.proto',
))
