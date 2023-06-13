from django.shortcuts import render
from django.http import HttpResponse, HttpRequest, HttpResponseServerError
from rest_framework.views import APIView
from django.conf import settings
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.core.files.base import ContentFile

import uuid, json


from .backends.s3.s3 import S3
from .backends.storageInterface import IStorageInterface
from .backends.file import File
# Create your views here.


class StorageView(APIView):

    def __get_storage(self) -> IStorageInterface:
        return S3()

    def post(self, request:HttpRequest, *args, **kwargs):
        upload_file_name = ''
        if not (request.FILES is None):
            file:InMemoryUploadedFile = request.FILES.get('file', None)
            if not (file is None):
                bucket = settings.AWS["S3"]["BUCKETS"]["RAW VIDEO"]["NAME"]
                filename:str = file.name

                if not (filename is None) and len(filename) > 0:
                    extension = filename.split(".")[-1]
                    filename = str(uuid.uuid4()) + "." + extension
                storage = self.__get_storage()
                response = storage.upload_file(
                    basedir=bucket, data=file.file, path=filename,
                    create_basedir_if_not_exist=True, content_type=file.content_type,
                    use_concurrency=False
                )
                if not response:
                    return HttpResponseServerError('Unable to upload the file')
                else:
                    upload_file_name = filename
        return HttpResponse(f"Uploaded file {upload_file_name}")

    def get(self, request:HttpRequest, *args, **kwargs):
        file = request.GET.get('file', '')
        if (not (file is None)) and len(file) > 0:
            bucket = settings.AWS["S3"]["BUCKETS"]["RAW VIDEO"]["NAME"]
            storage = self.__get_storage()
            file:File = storage.get_file(basedir=bucket, path=file)
            if not (file is None):
                return HttpResponse(ContentFile(file.file), content_type=file.content_type)
        else:
            dir = request.GET.get('directory', '')
            if not (dir is None) and len(dir) > 0:
                bucket = settings.AWS["S3"]["BUCKETS"]["RAW VIDEO"]["NAME"]
                storage = self.__get_storage()
                return HttpResponse(json.dumps({"data": storage.get_all_filepaths(basedir=bucket, path=dir)}), content_type='application/json')
        return HttpResponseServerError('Could not fetch a file. A file does not exist or has been removed')

    def delete(self, request:HttpRequest, *args, **kwargs):
        file = request.GET.get('file', '')
        storage = self.__get_storage()
        bucket = settings.AWS["S3"]["BUCKETS"]["RAW VIDEO"]["NAME"]
        if (not (file is None)) and len(file) > 0:
            success:bool = storage.delete_file(basedir=bucket, path=file)
            if success:
                return HttpResponse(f"Successfully deleted file {file}")

        return HttpResponseServerError('Could not fetch a file. A file does not exist or has been removed')