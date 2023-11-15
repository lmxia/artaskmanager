import asyncio
import tornado.web
from tornado.ioloop import IOLoop
from handler import handler
from metashape.algm import ModelBuilder3D


class MainHandler(tornado.web.RequestHandler):
    def get(self):
        self.write("Hello, world")


def make_app():
    settings = {
        "secret_key": "42wqTE23123wffLU94342wgldgFs",
    }

    return tornado.web.Application(
        [
            (r"/", MainHandler),
            (r"/enqueue/(?P<id>[0-9]+)", handler.InQueueHandler),
        ],
        **settings
    )


async def main():
    app = make_app()
    app.listen(8888)
    IOLoop.current().spawn_callback(ModelBuilder3D.builder)
    shutdown_event = asyncio.Event()
    await shutdown_event.wait()


# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    asyncio.run(main())
