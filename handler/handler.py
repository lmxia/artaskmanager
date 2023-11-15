import tornado.web
import asyncio
import json

from sharement.sharedata import task_queue_dict, NORMAL_PRIORITY


class BaseHandler(tornado.web.RequestHandler):

    def response(self, code, message):
        self.set_status(code)
        self.write(message)


class InQueueHandler(BaseHandler):

    async def post(self):
        post_data = self.request.body
        if post_data:
            post_data = self.request.body.decode('utf-8')
            post_data = json.loads(post_data)

        video_path = post_data.get("s3_path")
        if "normal" not in task_queue_dict:
            task_queue_dict["normal"] = asyncio.PriorityQueue()
        await task_queue_dict["normal"].put((NORMAL_PRIORITY, video_path))

        self.response(200, "you are in the queue.")
