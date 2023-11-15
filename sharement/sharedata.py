import asyncio

# there is only one queue
task_queue = asyncio.PriorityQueue()
NORMAL_PICTURE_PRIORITY = 10
