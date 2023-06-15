from django.conf import settings
import boto3
from boto3.s3.transfer import TransferConfig
from mypy_boto3_s3.client import S3Client
from typing import IO, Union, Any, List
from botocore.response import StreamingBody
from botocore.exceptions import ClientError

import threading

from ..file import File
from ..storageInterface import IStorageInterface


CONTENT_TYPE_METADATA_KEY = "content_type"

class S3FileUploadProgressCallback(object):
    def __int__(self, callback:object=None):
        self.lock = threading.Lock()
        self.current_progress = 0
        self.callback = callback

    def __call__(self, bytes_amount):
        with self.lock:
            self.current_progress += bytes_amount
            if not (self.callback is None):
                self.callback(self.current_progress)


class S3File(File):

    def __init__(self, file:bytes, content_type:str):
        super().__init__(file=file, content_type=content_type)


class S3(IStorageInterface):

    def __init__(self) -> None:
        self.location = settings.AWS["S3"]["URL"]
        self.access_key = settings.AWS["ACCESS_KEY_ID"]
        self.access_secret = settings.AWS["ACCESS_KEY_SECRET"]
        self.region = settings.AWS["REGION"]
        self.s3: S3Client = boto3.client(
            service_name='s3', aws_access_key_id=self.access_key,
            aws_secret_access_key=self.access_secret,
            endpoint_url=self.location,
            region_name=self.region
        )

    def does_bucket_exist(self, name: str) -> bool:
        try:
            response = self.s3.head_bucket(Bucket=name)
            if not (response is None):
                return True
        except:
            return False
        return False

    def does_file_exist(self, basedir: str, path: str, *args, **kwargs) -> bool:
        if self.does_bucket_exist(basedir):
            try:
                self.s3.get_object(Bucket=basedir, Key=path)
                return True
            except:
                print(f"File {path} does not exist in bucket")
        return False

    def create_bucket(self, name: str) -> bool:
        if not (self.does_bucket_exist(name)):
            self.s3.create_bucket(Bucket=name)
            return True
        else:
            print(f"Bucket {name} already exists")
        return False

    def delete_bucket(self, name: str) -> bool:
        if self.does_bucket_exist(name):
            response = self.s3.delete_bucket(Bucket=name)
            return True
        return False

    def upload_file(self, basedir: str, data:Union[IO[Any], StreamingBody, str], path: str, content_type:str,
                    use_concurrency:bool=False, callback:S3FileUploadProgressCallback=None,
                    create_basedir_if_not_exist=False, *args, **kwargs) -> bool:

        if not self.does_bucket_exist(basedir):
            if create_basedir_if_not_exist:
                self.create_bucket(basedir)
            else:
                print(f'Bucket does not exist')
                return False
        if not self.does_file_exist(basedir=basedir, path=path):
            try:
                metadata = {"Metadata": {CONTENT_TYPE_METADATA_KEY: content_type}}
                if not use_concurrency:
                    if type(data) == str:
                        self.s3.upload_file(Filename=data, Bucket=basedir, Key=path, ExtraArgs=metadata)
                    else:
                        self.s3.upload_fileobj(Fileobj=data, Bucket=basedir, Key=path, ExtraArgs=metadata)
                else:
                    config = TransferConfig(
                        multipart_threshold=1024 * 25, max_concurrency=10, multipart_chunksize=1024*25, use_threads=True
                    )
                    if type(data) == str:
                        self.s3.upload_file(Filename=data, Bucket=basedir, Key=path, Config=config, Callback=callback,
                                               ExtraArgs=metadata)
                    else:
                        self.s3.upload_fileobj(Fileobj=data, Bucket=basedir, Key=path, Config=config,
                                            Callback=callback,
                                            ExtraArgs=metadata)
                return True
            except ClientError as e:
                print(f"Error uploading file")
                print(e)
        else:
            print(f"Bucket {basedir} does not exist or the file {path} already exists")

        return False

    def get_file(self, basedir: str, path: str, *args, **kwargs) -> S3File:
        if self.does_bucket_exist(basedir):
            try:
                data = self.s3.get_object(Bucket=basedir, Key=path)
                if not (data is None) and ('Body' in data.keys()):
                    content = data['Body'].read()
                    content_type = data["ContentType"]
                    if "Metadata" in data.keys() and CONTENT_TYPE_METADATA_KEY in data["Metadata"].keys():
                        content_type = data["Metadata"][CONTENT_TYPE_METADATA_KEY]
                    return S3File(file=content, content_type=content_type)
            except ClientError as e:
                print(f"Error fetching file")
                print(e)
        else:
            print(f"Bucket {basedir} does not exist")
        return None

    def delete_file(self, basedir: str, path: str, *args, **kwargs) -> bool:
        if self.does_bucket_exist(basedir):
            if self.does_file_exist(basedir=basedir, path=path):
                try:
                    self.s3.delete_object(Bucket=basedir, Key=path)
                    return True
                except ClientError as e:
                    print(f"Error deleting file")
                    print(e)
            else:
                try :
                    response = self.s3.list_objects_v2(Bucket=basedir, Prefix=path)
                    if not (response is None) and ('Contents' in response.keys()):
                        for object in response['Contents']:
                            self.s3.delete_object(Bucket=basedir, Key=object['Key'])
                    return True
                except ClientError as e:
                    print(f"Error fetching path with prefix")
                    print(e)
        else:
            print(f"Bucket {basedir} does not exist")
        return False

    def get_all_filepaths(self, basedir:str, path:str, *args, **kwargs)->List[str]:
        result = []
        if self.does_bucket_exist(basedir):
            try:
                response = self.s3.list_objects_v2(Bucket=basedir, Prefix=path)
                if not (response is None) and ('Contents' in response.keys()):
                    for object in response['Contents']:
                        result.append(object['Key'])
            except ClientError as e:
                print(f"Error fetching path with prefix")
                print(e)
        else:
            print(f"Bucket {basedir} does not exist")
        return result

    def copy_file(self, source_basedir: str, source_path: str, destination_basedir, destination_path: str,
                  overwrite: bool = True, *args, **kwargs) -> bool:
        if self.does_bucket_exist(source_basedir) and self.does_bucket_exist(destination_basedir) \
                and self.does_file_exist(basedir=source_basedir, path=source_path):

            if not overwrite and self.does_file_exist(basedir=destination_basedir, path=destination_path):
                print(f"Cannot copy to destination path as a destination file {destination_path} already exists")
                return False
            try:
                self.s3.copy(CopySource={'Bucket': source_basedir, 'Key': source_path},
                             Bucket=destination_basedir, Key=destination_path)
                return True
            except ClientError as e:
                print(f"Error deleting file")
                print(e)
        else:
            print(
                f"Bucket {source_basedir} or {destination_basedir} does not exist or the file {source_path} does not exist")
        return False

    def move_file(self, source_basedir: str, source_path: str, destination_basedir, destination_path: str,
                  overwrite: bool = True, *args, **kwargs) -> bool:
        if self.copy_file(source_basedir=source_basedir, source_path=source_path,
                          destination_basedir=destination_basedir, destination_path=destination_path,
                          overwrite=overwrite):
            return self.delete_file(basedir=source_basedir, path=source_path)
        return False
