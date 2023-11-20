import asyncio
import logging
import Metashape
import errno
import shutil
import tempfile

from sharement.sharedata import task_queue_dict
from obs import ObsClient, Object
import cv2
import os


class ModelBuilder3D:
    bucket = "facescan"
    obsClient = ObsClient(
        access_key_id='NCZPQASHJNW2URNGB9SI',
        secret_access_key='lXLZ9J1yUJYMrUBYZX2oAmzc3uvbSEIOSckpEsvN',
        server='obs.cn-east-3.myhuaweicloud.com'
    )

    def __init__(self):
        pass

    @classmethod
    async def builder(cls):
        while True:
            # 这里会阻塞的。
            logging.info("prepare to get a new video")
            if "normal" not in task_queue_dict:
                task_queue_dict["normal"] = asyncio.PriorityQueue()
            _, video_fullpath_name = await task_queue_dict["normal"].get()
            logging.info("now get a a new video: " + video_fullpath_name)
            (s3_path, filename) = os.path.split(video_fullpath_name)
            object_metadata = cls.obsClient.getObjectMetadata(cls.bucket, video_fullpath_name)
            if object_metadata.status > 300:
                logging.info("no video file found in your request...")
                continue
            video_resp = cls.obsClient.createSignedUrl('GET', cls.bucket, video_fullpath_name, expires=3600)
            cap = cv2.VideoCapture(video_resp.signedUrl)
            num_frame = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            if num_frame < 30:
                continue
            try:
                tmp_dir = tempfile.mkdtemp()  # create dir
                logging.info("now we work in a temp dir " + tmp_dir)
                for count in range(30):  # 计数，从第0帧开始
                    cap.set(cv2.CAP_PROP_POS_FRAMES, int(count * num_frame / 30))
                    success, frame = cap.read()
                    if not success:
                        logging.error("read failed with file")
                        continue
                    cv2.imwrite(tmp_dir + "/" + str(count) + '.png', frame)
                # 指定图片路径
                path = tmp_dir + "/"

                # 创建Metashape文档对象
                doc = Metashape.Document()

                # 添加图片到文档
                chunk = doc.addChunk()
                chunk.addPhotos([path + f for f in os.listdir(path) if f.endswith(".png")])

                # 对齐图片
                chunk.matchPhotos(downscale=2,
                                  generic_preselection=True,
                                  reference_preselection=False)
                chunk.alignCameras()

                # 深度图
                chunk.buildDepthMaps(downscale=2,
                                     filter_mode=Metashape.AggressiveFiltering)
                # 模型创建
                chunk.buildModel(surface_type=Metashape.Arbitrary,
                                 interpolation=Metashape.EnabledInterpolation)

                # 纹理创建
                chunk.buildUV(mapping_mode=Metashape.GenericMapping)
                chunk.buildTexture(blending_mode=Metashape.MosaicBlending,
                                   texture_size=2048)

                # 导出obj模型
                if chunk.model:
                    chunk.exportModel(path + '/model.obj')
                resp = cls.obsClient.putFile(cls.bucket, s3_path + "/model.obj", path + '/model.obj')
                if resp.status >= 300:
                    logging.error("obj file upload failed..")
                resp = cls.obsClient.putFile(cls.bucket, s3_path + "/model.jpg", path + '/model.jpg')
                if resp.status >= 300:
                    logging.error("jpg file upload failed..")
                resp = cls.obsClient.putFile(cls.bucket, s3_path + "/model.mtl", path + '/model.mtl')
                if resp.status >= 300:
                    logging.error("mtl file upload failed..")
                logging.info("Finished!")

            finally:
                try:
                    shutil.rmtree(tmp_dir)  # delete directory
                except OSError as exc:
                    if exc.errno != errno.ENOENT:  # ENOENT - no such file or directory
                        raise
