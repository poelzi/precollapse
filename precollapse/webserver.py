import asyncio
from rainfall.web import Application, HTTPHandler, WSHandler

class HelloHandler(HTTPHandler):
    @asyncio.coroutine
    def handle(self, request):
        return 'Hello!'


webapp = Application(
    {
        r'^/$': HelloHandler,
    },
)

