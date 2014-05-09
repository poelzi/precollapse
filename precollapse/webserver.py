import asyncio
from vase import Vase
from vase.webserver import WebServer

#from rainfall.web import Application, HTTPHandler, WSHandler

#class HelloHandler(HTTPHandler):
    #@asyncio.coroutine
    #def handle(self, request):
        #return 'Hello!'


#webapp = Application(
    #{
        #r'^/$': HelloHandler,
    #},
#)



class Webserver(Vase):
    def __init__(self):
        super(Webserver, self).__init__("PreCollapseWeb")

    def run(self, *, host='0.0.0.0', port=3000, loop=None, run_forever=True):
        if loop is None:
            loop = asyncio.get_event_loop()
        asyncio.async(loop.create_server(lambda: WebServer(loop=loop, app=self),
                    host, port))
        if run_forever:
            loop.run_forever()


webapp = Webserver()


@webapp.route(path="/")
def hello(request):
    return "Hello Vase!"

