import tornado.web
import asyncio
import json

from metashape.algm import ModelBuilder3D
from sharement.sharedata import task_queue_dict, NORMAL_PRIORITY


class BaseHandler(tornado.web.RequestHandler):

    def response(self, code, message):
        self.set_status(code)
        self.write(message)


class StatusHandler(BaseHandler):
    def get(self):
        self.response(200, {"available": ModelBuilder3D.available})


class InQueueHandler(BaseHandler):

    async def post(self):
        post_data = self.request.body
        if post_data:
            post_data = self.request.body.decode('utf-8')
            post_data = json.loads(post_data)

        # information 包含：bucket、用户 id、患者 id 和病例 id
        information = post_data.get("information")
        if "normal" not in task_queue_dict:
            task_queue_dict["normal"] = asyncio.PriorityQueue()
        await task_queue_dict["normal"].put((NORMAL_PRIORITY, information))

        self.response(200, "you are in the queue.")
