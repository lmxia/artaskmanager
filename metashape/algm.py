import asyncio
import errno
import logging
import os
import shutil
import tempfile

import Metashape
from obs import ObsClient
from tornado import httpclient

from sharement.sharedata import task_queue_dict


class ModelBuilder3D:
    obsClient = ObsClient(
        access_key_id='NCZPQASHJNW2URNGB9SI',
        secret_access_key='lXLZ9J1yUJYMrUBYZX2oAmzc3uvbSEIOSckpEsvN',
        server='obs.cn-east-3.myhuaweicloud.com'
    )

    available = True

    http_client = httpclient.AsyncHTTPClient()
    bucket_url_map = {
        "smilelink": "http://test.teethlink.cn/api/facescan",
        "smilelink-prod": "https://teethlink.cn/api/facescan"
    }

    def __init__(self):
        pass

    @classmethod
    def get_input_prefix(cls, user_id, case_id, typ):
        return f"doctor/{user_id}/facescan/{case_id}/face-photos/{typ}/"

    @classmethod
    def get_output_prefix(cls, patient_id, case_id, typ):
        return f"patient/{patient_id}/facescan/{case_id}_{typ}_"

    @classmethod
    def get_output_filepath(cls, user_id, case_id, typ, filename):
        return f"doctor/{user_id}/facescan/{case_id}/models/facescan/{typ}/{filename}"

    @classmethod
    def make_request(cls, bucket, case_id, route):
        return httpclient.HTTPRequest(
            url=f"{cls.bucket_url_map.get(bucket)}/{case_id}/{route}",
            method="PATCH",
            connect_timeout=10,
            allow_nonstandard_methods=True
        )

    @classmethod
    async def builder(cls):
        while True:
            # 接收新病例
            logging.info("prepare to get a new ill case")
            if "normal" not in task_queue_dict:
                task_queue_dict["normal"] = asyncio.Queue()
            _, information = await task_queue_dict["normal"].get()
            logging.info(f"now get a new ill case: {information}")

            bucket = information.get("bucket")
            user_id = information.get("user_id")
            patient_id = information.get("patient_id")
            case_id = information.get("case_id")
            typ = information.get("type")

            # 设置服务器和病例的状态
            cls.available = False
            try:
                resp = await cls.http_client.fetch(cls.make_request(bucket, case_id, "executing"))
            except Exception as e:
                logging.error(f"error fetching: {e}")
            else:
                logging.info(f"resp: {resp.body}")

            try:
                tmp_dir = tempfile.mkdtemp()  # create dir
                logging.info("now we work in a temp dir " + tmp_dir)

                # 读取图片
                resp = cls.obsClient.listObjects(bucket, cls.get_input_prefix(user_id, case_id, typ))
                if resp.status > 300:
                    raise Exception(f"read file form {user_id}/{case_id}/{typ} failed with {resp}")
                # 判断图片张数是否符合要求
                if len(resp.body.contents) == 0:
                    raise Exception(f"numbers of {user_id}/{case_id}/{typ}'s images are empty")
                for index, content in enumerate(resp.body.contents):
                    if content.key.endswith(".jpg"):
                        res = cls.obsClient.getObject(bucket, content.key,
                                                      downloadPath=f"{tmp_dir}/{index}.jpg")
                        if res.status > 300:
                            logging.error(f"get object failed: {res}")

                # 指定图片路径
                path = tmp_dir + "/"

                # 创建Metashape文档对象
                doc = Metashape.Document()

                # 添加图片到文档
                chunk = doc.addChunk()
                chunk.addPhotos([path + f for f in os.listdir(path) if f.endswith(".jpg")])

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
                    chunk.exportModel(path + 'model/model.obj')

                # shutil.make_archive(path + "model", "zip", path + '/model/')
                # resp = cls.obsClient.putFile(bucket, cls.get_output_prefix(patient_id, case_id, typ) + "model.zip",
                #                              path + 'model.zip')
                # if resp.status >= 300:
                #     raise Exception(f"upload zip file failed with resp: {resp}")

                resp = cls.obsClient.putFile(bucket, cls.get_output_filepath(user_id, case_id, typ, "model.obj"),
                                             path + 'model/model.obj')
                logging.info(f"upload obj file resp: {resp}")
                if resp.status >= 300:
                    raise Exception(f"upload obj file failed with resp: {resp}")
                resp = cls.obsClient.putFile(bucket, cls.get_output_filepath(user_id, case_id, typ, "model.jpg"),
                                             path + 'model/model.jpg')
                logging.info(f"upload jpg file resp: {resp}")
                if resp.status >= 300:
                    raise Exception(f"upload jpg file failed with resp: {resp}")
                resp = cls.obsClient.putFile(bucket, cls.get_output_filepath(user_id, case_id, typ, "model.mtl"),
                                             path + 'model/model.mtl')
                logging.info(f"upload mtl file resp: {resp}")
                if resp.status >= 300:
                    raise Exception(f"upload mtl file failed with resp: {resp}")
                logging.info("Finished!")

                # 设置病例的状态
                try:
                    resp = await cls.http_client.fetch(cls.make_request(bucket, case_id, "finished"))
                except Exception as e:
                    logging.error(f"error fetching: {e}")
                else:
                    logging.info(f"resp: {resp.body}")
            except Exception as e:
                logging.info(e)
                # 设置病例的状态
                try:
                    resp = await cls.http_client.fetch(cls.make_request(bucket, case_id, "failed"))
                except Exception as e:
                    logging.error(f"error fetching: {e}")
                else:
                    logging.info(f"resp: {resp.body}")
            finally:
                cls.available = True
                try:
                    shutil.rmtree(tmp_dir)  # delete directory
                except OSError as exc:
                    if exc.errno != errno.ENOENT:  # ENOENT - no such file or directory
                        raise
