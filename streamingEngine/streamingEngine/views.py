from typing import List
import os, uuid, mimetypes, shutil
from django.http import HttpResponse, HttpRequest, HttpResponseServerError, HttpResponseForbidden, JsonResponse
from rest_framework.views import APIView
from django.views.generic import TemplateView
from django.conf import settings
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.core.files.base import ContentFile
from django.shortcuts import render

from .backends.storageInterface import IStorageInterface
from .backends.file import File
from .backends.s3.s3 import S3
from django.views.decorators.cache import cache_control
from django.utils.decorators import method_decorator

from .task import transcode_video


VIDEO_FOLDER_NAME = "videos"
KEYS_FILE_NAME = "keys"
def get_storage_path(content:str)->str:
    storage_path = f"{settings.AWS_STREAM_UPLOAD_DIR}/{content}"
    return storage_path

def get_video_storage_path(content:str)->str:
    return get_storage_path(content) + "/" + VIDEO_FOLDER_NAME

def get_key_storage_path(content:str)->str:
    return get_storage_path(content) + "/" + KEYS_FILE_NAME

class StreamingView(TemplateView):

    template_name = "index.html"

    @method_decorator(cache_control(max_age=0, no_cache=True, no_store=True))
    def get(self, request:HttpRequest, file:str, *args, **kwargs):
        if (not (file is None)) and len(file) > 0:
            storage_path = get_video_storage_path(file)
            return render(request, self.template_name, {"url": f"/playlist/{storage_path}/", "id": file})


class VttView(APIView):
    def get(self, request: HttpRequest, id:str, *args, **kwargs):
        vtt_content = '''WEBVTT

1
00:00:00.000 --> 00:00:03.500
Chapter 1

2
00:00:03.500 --> 00:00:03.000
Chapter 2

3
00:06:10.000 --> 00:09:25.000
Chapter 3
 '''
        return HttpResponse(vtt_content, content_type="text/vtt")



class SampleView(APIView):
    def post(self, request:HttpRequest, *args, **kwargs):
        print("Received post request with data")
        print(request.POST.dict())
        return HttpResponse("ok")

class KeysView(APIView):

    def __get_storage(self) -> IStorageInterface:
        return S3()
    @method_decorator(cache_control(max_age=0, no_cache=True, no_store=True))
    def get(self, request: HttpRequest, id:str, *args, **kwargs):
        is_authorized = True
        if not is_authorized:
            return HttpResponseForbidden("You are not allowed to access this video")
        if not (id is None) and len(id) > 0:
            keys_path = get_key_storage_path(id)
            bucket = settings.AWS["S3"]["BUCKETS"]["RAW VIDEO"]["NAME"]
            storage = self.__get_storage()
            file: File = storage.get_file(basedir=bucket, path=f"{keys_path}")
            if not (file is None):
                return HttpResponse(ContentFile(file.file), content_type=file.content_type)

        return HttpResponseServerError("Could not find keys")



class VideoUploader(APIView):

    def __save_file(self, file:InMemoryUploadedFile, temp_dir:str)->str:
        if not os.path.exists(temp_dir):
            os.makedirs(temp_dir)

        filename: str = file.name
        file_extension = filename.split(".")[-1]

        if not file_extension.lower() in ['mp4', 'mkv']:
            return None

        temp_filepath = os.path.join(temp_dir, filename)
        try:
            with open(temp_filepath, 'wb') as f:
                f.write(file.read())
            return temp_filepath
        except Exception as e:
            print("Error saving file to temp directory")
        return None

    def get(self, request:HttpRequest, *args, **kwargs):
        path = request.GET.get("path", "")
        if not (path is None) and len(path) > 0:
            bucket = settings.AWS["S3"]["BUCKETS"]["RAW VIDEO"]["NAME"]
            storage:IStorageInterface = S3()
            result = storage.get_all_filepaths(basedir=bucket, path=path)
            return HttpResponse(str(result))
        return HttpResponse("No files found")

    def delete(self, request:HttpRequest, *args, **kwargs):
        path = request.GET.get("path", "")
        if not (path is None) and len(path) > 0:
            bucket = settings.AWS["S3"]["BUCKETS"]["RAW VIDEO"]["NAME"]
            storage: IStorageInterface = S3()
            result = storage.delete_file(basedir=bucket, path=path)
            return HttpResponse(str(result))
        return HttpResponse("No files found")
    def post(self,  request:HttpRequest, *args, **kwargs):
        if not (request.FILES is None):
            file: InMemoryUploadedFile = request.FILES.get('file', None)

            bucket = settings.AWS["S3"]["BUCKETS"]["RAW VIDEO"]["NAME"]

            # Save video to temp directory
            temp_unique_dir = str(uuid.uuid4())
            temp_dir = os.path.join(settings.AWS_TEMP_DOWNLOAD_DIR, temp_unique_dir)
            saved_filepath = self.__save_file(file=file, temp_dir=temp_dir)
            mimetype = mimetypes.guess_type(saved_filepath)[0]
            if (mimetype is None) or (len(mimetype) == 0):
                mimetype = "text/html"

            s3_path = get_storage_path(f"raw/{temp_unique_dir}/{file.name}")

            uploaded = S3().upload_file(
                basedir=bucket,
                data=saved_filepath,
                path=s3_path,
                content_type=mimetype,
                create_basedir_if_not_exist=True
            )

            if uploaded:
                os.remove(saved_filepath)
                return HttpResponse(f"Uploaded file to {s3_path}")
            return HttpResponseServerError(f"Error uploading file {file.name} to {s3_path}")

        return HttpResponseServerError("Error uploading file")

class PlayList(APIView):

    MASTER_MANIFEST_FILENAME = "master.m3u8"
    def __get_storage(self) -> IStorageInterface:
        return S3()

    def __save_file(self, file:InMemoryUploadedFile, temp_dir:str)->str:
        if not os.path.exists(temp_dir):
            os.makedirs(temp_dir)

        filename: str = file.name
        file_extension = filename.split(".")[-1]

        if not file_extension.lower() in ['mp4', 'mkv']:
            return None

        temp_filepath = os.path.join(temp_dir, filename)
        try:
            with open(temp_filepath, 'wb') as f:
                f.write(file.read())
            return temp_filepath
        except Exception as e:
            print("Error saving file to temp directory")
        return None

    @method_decorator(cache_control(max_age=0, no_cache=True, no_store=True))
    def get(self, request: HttpRequest, segment_name:str, *args, **kwargs):
        if (not (segment_name is None)) and len(segment_name) > 0:
            bucket = settings.AWS["S3"]["BUCKETS"]["RAW VIDEO"]["NAME"]
            storage = self.__get_storage()
            if not ( "m3u8" in segment_name) and not ('.ts' in segment_name):
                segment_name = segment_name.rstrip("/") + "/" + PlayList.MASTER_MANIFEST_FILENAME
            file: File = storage.get_file(basedir=bucket, path=f"{segment_name}")
            if not (file is None):
                return HttpResponse(ContentFile(file.file), content_type=file.content_type)
        return HttpResponseServerError('Could not fetch a file. A file does not exist or has been removed')

    def delete(self, request:HttpRequest, segment_name:str, *args, **kwargs):
        if (not (segment_name is None)) and len(segment_name) > 0:
            bucket = settings.AWS["S3"]["BUCKETS"]["RAW VIDEO"]["NAME"]
            storage = self.__get_storage()
            storage_path = get_storage_path(segment_name)
            contents:List[str] = storage.get_all_filepaths(basedir=bucket, path=storage_path)

            if not (contents is None) and len(contents) > 0:
                for content in contents:
                    storage.delete_file(basedir=bucket, path=content)

        return HttpResponse("ok")

    def put(self, request:HttpRequest, *args, **kwargs):
        segment_name = request.GET.get("segment_name", "")
        if not (segment_name is None) and len(segment_name) > 0:
            bucket = settings.AWS["S3"]["BUCKETS"]["RAW VIDEO"]["NAME"]
            # Save video to temp directory
            temp_unique_dir = str(uuid.uuid4())
            temp_dir = os.path.join(settings.AWS_TEMP_DOWNLOAD_DIR, temp_unique_dir)
            encryption_key_url:str = request.GET.get("encryption_url", f"/keys/")
            encryption_key_url = encryption_key_url.rstrip("/") + "/" + temp_unique_dir
            transcode_video.delay(
                input_filepath=segment_name,
                transcoding_base_output_dir=temp_dir,
                video_folder_name=VIDEO_FOLDER_NAME,
                manifest_filename=PlayList.MASTER_MANIFEST_FILENAME,
                encryption_key_filename=KEYS_FILE_NAME,
                encryption_key_url=encryption_key_url,
                output_storage_basedir=bucket,
                output_storage_filepath=get_storage_path(temp_unique_dir),
                s3_bucket_name=bucket
            )
            # return HttpResponse(
            #     f"Your video {temp_unique_dir} is being transcoded and uploaded to S3. Please wait a while. The transcoded file will be saved in {temp_unique_dir}")

            return JsonResponse({
                "id": temp_unique_dir
            })



        return HttpResponseServerError("Could not fetch the file")

    def post(self, request:HttpRequest, *args, **kwargs):
        if not (request.FILES is None):
            file: InMemoryUploadedFile = request.FILES.get('file', None)

            storage: IStorageInterface = self.__get_storage()
            bucket = settings.AWS["S3"]["BUCKETS"]["RAW VIDEO"]["NAME"]

            # Save video to temp directory
            temp_unique_dir = str(uuid.uuid4())
            temp_dir = os.path.join(settings.AWS_TEMP_DOWNLOAD_DIR, temp_unique_dir)
            saved_filepath = self.__save_file(file=file, temp_dir=temp_dir)

            transcode_video.delay(
                input_filepath=saved_filepath,
                transcoding_base_output_dir=temp_dir,
                video_folder_name=VIDEO_FOLDER_NAME,
                manifest_filename=PlayList.MASTER_MANIFEST_FILENAME,
                encryption_key_filename=KEYS_FILE_NAME,
                encryption_key_url=f"/keys/{temp_unique_dir}",
                output_storage_basedir=bucket,
                output_storage_filepath=get_storage_path(temp_unique_dir)
            )
            return HttpResponse(f"Your video {temp_unique_dir} is being transcoded and uploaded to S3. Please wait a while")

        return HttpResponseServerError("Error uploading file")