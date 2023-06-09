from django.conf import settings
import boto3
from boto3.s3.transfer import TransferConfig
from mypy_boto3_s3.client import S3Client
from typing import IO, Union, Any
from botocore.response import StreamingBody
from botocore.exceptions import ClientError

import threading


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


class S3:

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

    def does_file_exist(self, bucket: str, path: str) -> bool:
        if self.does_bucket_exist(bucket):
            try:
                self.s3.get_object(Bucket=bucket, Key=path)
                return True
            except:
                print(f"File {path} does not exist in bucket")
        return False

    def create_bucket(self, name: str) -> bool:
        if not (self.does_bucket_exist(name)):
            self.s3.create_bucket(name)
            return True
        else:
            print(f"Bucket {name} already exists")
        return False

    def delete_bucket(self, name: str) -> bool:
        if self.does_bucket_exist(name):
            response = self.s3.delete_bucket(name)
            return True
        return False

    def upload_file(self, bucket: str, file: Union[IO[Any], StreamingBody], path: str, use_concurrency:bool=False, callback:S3FileUploadProgressCallback=None) -> bool:
        if self.does_bucket_exist(bucket) and not self.does_file_exist(bucket=bucket, path=path):
            try:
                if not use_concurrency:
                    self.s3.upload_fileobj(Fileobj=file, Bucket=bucket, Key=path)
                else:
                    config = TransferConfig(
                        multipart_threshold=1024 * 25, max_concurrency=10, multipart_chunksize=1024*25, use_threads=True
                    )
                    self.s3.upload_fileobj(Fileobj=file, Bucket=bucket, Key=path, Config=config, Callback=callback)
                return True
            except ClientError as e:
                print(f"Error uploading file")
                print(e)
        else:
            print(f"Bucket {bucket} does not exist or the file {path} already exists")

        return False

    def get_file(self, bucket: str, path: str) -> bytes:
        if self.does_bucket_exist(bucket):
            try:
                data = self.s3.get_object(Bucket=bucket, Key=path)
                if not (data is None) and ('Body' in data.keys()):
                    return data['Body'].read()
            except ClientError as e:
                print(f"Error fetching file")
                print(e)
        else:
            print(f"Bucket {bucket} does not exist")
        return None

    def delete_file(self, bucket: str, path: str) -> bool:
        if self.does_bucket_exist(bucket) and self.does_file_exist(bucket=bucket, path=path):
            try:
                self.s3.delete_object(Bucket=bucket, Key=path)
                return True
            except ClientError as e:
                print(f"Error deleting file")
                print(e)
        else:
            print(f"Bucket {bucket} does not exist or the file {path} does not exist in the bucket")
        return False

    def copy_file(self, source_bucket: str, source_path: str, destination_bucket, destination_path: str,
                  overwrite: bool = True) -> bool:
        if self.does_bucket_exist(source_bucket) and self.does_bucket_exist(destination_bucket) \
                and self.does_file_exist(bucket=source_bucket, path=source_path):

            if not overwrite and self.does_file_exist(bucket=destination_bucket, path=destination_path):
                print(f"Cannot copy to destination path as a destination file {destination_path} already exists")
                return False
            try:
                self.s3.copy(CopySource={'Bucket': source_bucket, 'Key': source_path},
                             Bucket=destination_bucket, Key=destination_path)
                return True
            except ClientError as e:
                print(f"Error deleting file")
                print(e)
        else:
            print(
                f"Bucket {source_bucket} or {destination_bucket} does not exist or the file {source_path} does not exist")
        return False

    def move_file(self, source_bucket: str, source_path: str, destination_bucket, destination_path: str,
                  overwrite: bool = True) -> bool:
        if self.copy_file(source_bucket=source_bucket, source_path=source_path,
                          destination_bucket=destination_bucket, destination_path=destination_path,
                          overwrite=overwrite):
            return self.delete_file(bucket=source_bucket, path=source_path)
        return False
