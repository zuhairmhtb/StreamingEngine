import os, uuid, mimetypes, shutil
from django.http import HttpResponse, HttpRequest, HttpResponseServerError
from rest_framework.views import APIView
from django.views.generic import TemplateView
from django.conf import settings
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.core.files.base import ContentFile
from django.shortcuts import render

from storage.backends.storageInterface import IStorageInterface
from storage.backends.file import File
from storage.backends.s3.s3 import S3
from storage.backends.transcoder.transcoder import TranscoderConfiguration, HLSTranscoder
from django.views.decorators.cache import cache_control
from django.utils.decorators import method_decorator

def get_storage_path(content:str)->str:
    storage_path = f"{settings.AWS_STREAM_UPLOAD_DIR}/{content}/hls/"
    return storage_path

class StreamingView(TemplateView):

    template_name = "index.html"

    @method_decorator(cache_control(max_age=0, no_cache=True, no_store=True))
    def get(self, request:HttpRequest, file:str, *args, **kwargs):
        if (not (file is None)) and len(file) > 0:
            storage_path = get_storage_path(file)
            return render(request, self.template_name, {"url": f"/playlist/{storage_path}"})




class PlayList(APIView):

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

    def __upload_all_files_to_storage(self, path:str, storage:IStorageInterface, base_output_dir:str, relative_output_path:str)->bool:
        if not os.path.exists(path):
            return False

        if os.path.isfile(path):
            if path.endswith(".ts"):
                mimetype = "video/mp2t"  # mimetypes package does not recognize hls ts files
            else:
                mimetype = mimetypes.guess_type(path)[0]
                if mimetype is None:
                    mimetype = 'text/html'
            storage.upload_file(
                basedir=base_output_dir,
                data=path,
                path=relative_output_path,
                content_type=mimetype,
                use_concurrency=True,
                create_basedir_if_not_exist=True
            )
            return True
        else:
            success = True
            for file in os.listdir(path):
                filepath = os.path.join(path, file)
                relative_filepath = f"{relative_output_path}/{file}"
                success = success and self.__upload_all_files_to_storage(path=filepath, storage=storage,
                                                   base_output_dir=base_output_dir, relative_output_path=relative_filepath)
            return success

    @method_decorator(cache_control(max_age=0, no_cache=True, no_store=True))
    def get(self, request: HttpRequest, segment_name:str, *args, **kwargs):
        if (not (segment_name is None)) and len(segment_name) > 0:
            bucket = settings.AWS["S3"]["BUCKETS"]["RAW VIDEO"]["NAME"]
            storage = self.__get_storage()
            storage_path = f"{settings.AWS_STREAM_UPLOAD_DIR}/{segment_name}"
            #file: File = storage.get_file(basedir=bucket, path=f"{settings.AWS_STREAM_UPLOAD_DIR}/{segment_name}")
            # master_playlist = request.GET.get('master_playlist', '')
            # if len(master_playlist) > 0:
            #     segment_name = segment_name + '/' + master_playlist
            if not ( "m3u8" in segment_name) and not ('.ts' in segment_name):
                segment_name = segment_name.rstrip("/") + "/" + "master.m3u8"
            file: File = storage.get_file(basedir=bucket, path=f"{segment_name}")
            if not (file is None):
                return HttpResponse(ContentFile(file.file), content_type=file.content_type)
        return HttpResponseServerError('Could not fetch a file. A file does not exist or has been removed')

    def delete(self, request:HttpRequest):
        return HttpResponse("ok")

    def post(self, request:HttpRequest, *args, **kwargs):
        if not (request.FILES is None):
            file:InMemoryUploadedFile = request.FILES.get('file', None)

            storage:IStorageInterface = self.__get_storage()
            bucket = settings.AWS["S3"]["BUCKETS"]["RAW VIDEO"]["NAME"]

            # Save video to temp directory
            temp_unique_dir = str(uuid.uuid4())
            temp_dir = os.path.join(settings.AWS_TEMP_DOWNLOAD_DIR, temp_unique_dir)
            saved_filepath = self.__save_file(file=file, temp_dir=temp_dir)

            if not (saved_filepath is None):
                configurations = [
                    TranscoderConfiguration(
                        bitrate='600k',
                        resolution='320:-1',
                        input_framerate=30
                    ),
                    TranscoderConfiguration(
                        bitrate='800k',
                        resolution='640:-1',
                        input_framerate=30

                    ),
                    # TranscoderConfiguration(
                    #     bitrate='1200k',
                    #     resolution='854:-1',
                    #     input_framerate=30
                    # ),
                    # TranscoderConfiguration(
                    #     bitrate='2000k',
                    #     resolution='1280:-1',
                    #     input_framerate=30
                    # ),
                ]

                # Transcode to HLS
                output_dir = os.path.join(temp_dir, 'hls')
                transcoder = HLSTranscoder()
                master_manifest_filepath = transcoder.transcode_adaptive_bitrate(
                    input_filepath=saved_filepath,
                    manifest_filename='master.m3u8',
                    configurations=configurations,
                    output_folder=output_dir
                )

                if not (master_manifest_filepath is None) and len(master_manifest_filepath) > 0:
                    # Upload content to S3
                    s3_upload_path = f"{settings.AWS_STREAM_UPLOAD_DIR}/{temp_unique_dir}"
                    success = self.__upload_all_files_to_storage(path=temp_dir, storage=storage,
                                                       base_output_dir=bucket, relative_output_path=s3_upload_path)
                    if success:
                        # Delete temp directory
                        # shutil.rmtree(temp_dir, ignore_errors=True)
                        return HttpResponse(f"Uploaded file to {bucket}/{temp_unique_dir}")

        return HttpResponseServerError("Error uploading file")