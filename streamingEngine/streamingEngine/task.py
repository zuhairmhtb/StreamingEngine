import uuid
import requests

from .backends.s3.s3 import S3
from .backends.transcoder.transcoder import TranscoderConfiguration, Transcoder
from .settings import AWS_TEMP_DOWNLOAD_DIR, TRANSCODE_COMPLETE_WEBHOOK

import os, mimetypes, shutil

from celery import shared_task


TRANSCODING_CONFIGURATIONS = [
    TranscoderConfiguration(audio_bitrate=250000, video_bitrate=250000, width=320),
    TranscoderConfiguration(audio_bitrate=500000, video_bitrate=500000, width=640),
    TranscoderConfiguration(audio_bitrate=1000000, video_bitrate=1000000, width=854),
    TranscoderConfiguration(audio_bitrate=2000000, video_bitrate=2000000, width=1280),
]


def get_video_from_s3(input_path:str, bucket:str, temp_directory_name="temp")->str:
    if (input_path is None) or (bucket) is None:
        print("Provide a bucket name and input filepath")
        return None

    storage = S3()
    is_file = storage.does_file_exist(basedir=bucket, path=input_path)
    if is_file:
        file = storage.get_file(basedir=bucket, path=input_path)
        if not (file is None) and not (file.file is None):
            file_extension = input_path.split(".")[-1]
            temp_filename = str(uuid.uuid4()) + "." + file_extension

            try:
                if not (temp_directory_name is None) and len(temp_directory_name) > 0:
                    if not os.path.exists(temp_directory_name):
                        os.makedirs(temp_directory_name)

                temp_filename = os.path.join(temp_directory_name, temp_filename)
                with open(temp_filename, 'wb') as f:
                    f.write(file.file)
                return temp_filename
            except Exception as e:
                print(f"Could not save S3 file to temp path")
                print(e)
        else:
            print(f"Could not fetch file from the url {input_path}")

    else:
        print(f"The s3 url {input_path} does not match any file")
    return None

def upload_all_files_to_s3(input_path: str, bucket: str,
                                  relative_output_path: str) -> bool:
    if not os.path.exists(input_path):
        return False

    if os.path.isfile(input_path):
        if input_path.endswith(".ts"):
            mimetype = "video/mp2t"  # mimetypes package does not recognize hls ts files
        else:
            mimetype = mimetypes.guess_type(input_path)[0]
            if mimetype is None:
                mimetype = 'text/html'
        storage = S3()
        storage.upload_file(
            basedir=bucket,
            data=input_path,
            path=relative_output_path,
            content_type=mimetype,
            use_concurrency=True,
            create_basedir_if_not_exist=True
        )
        return True
    else:
        success = True
        for file in os.listdir(input_path):
            filepath = os.path.join(input_path, file)
            relative_filepath = f"{relative_output_path}/{file}"
            success = success and upload_all_files_to_s3(input_path=filepath, bucket=bucket, relative_output_path=relative_filepath)
        return success


@shared_task
def transcode_video(input_filepath:str, transcoding_base_output_dir:str, video_folder_name:str, manifest_filename:str,
                    encryption_key_filename:str, encryption_key_url:str,
                    output_storage_basedir:str, output_storage_filepath:str, s3_bucket_name:str=""):

    errors = []
    transcoded_video_id = input_filepath
    success = False

    try:
        transcoded_video_output_dir = os.path.join(transcoding_base_output_dir, video_folder_name)
        encryption_key_path = os.path.join(transcoding_base_output_dir, encryption_key_filename)
        print(f"Transcoding video from {input_filepath} to {transcoded_video_output_dir}")
        use_s3 = not (s3_bucket_name) is None and len(s3_bucket_name) > 0
        if use_s3:
            downloaded_filepath = get_video_from_s3(input_path=input_filepath, bucket=s3_bucket_name,
                                                    temp_directory_name=AWS_TEMP_DOWNLOAD_DIR)
            if (downloaded_filepath is None) or len(downloaded_filepath) == 0:
                print("Could not fetch file from S3. Aborting task")
                errors.append(f"Could not fetch file from S3 {input_filepath}")
                requests.post(TRANSCODE_COMPLETE_WEBHOOK, data={"errors": errors, "success": success, "id": transcoded_video_id})
                return
            input_filepath = downloaded_filepath
        

        transcoder = Transcoder()
        print(f"Transcoding video {input_filepath} to {transcoded_video_output_dir}")
        res = transcoder.transcode(
            input_filepath=input_filepath,
            base_output_dir=transcoded_video_output_dir,
            manifest_filename=manifest_filename,
            configurations=TRANSCODING_CONFIGURATIONS,
            encryption_key_directory=encryption_key_path,
            encryption_key_url=encryption_key_url
        )

        if not (res is None) and len(res) > 0:
            print(f"Successfully transcoded video and saved to {transcoded_video_output_dir}")
            success = upload_all_files_to_s3(
                input_path=transcoding_base_output_dir,
                bucket=output_storage_basedir,
                relative_output_path=output_storage_filepath
            )
            if success:
                print(f"Deleting data from temp directory {transcoding_base_output_dir}")
                shutil.rmtree(transcoding_base_output_dir, ignore_errors=False)
                if use_s3:
                    os.remove(downloaded_filepath)
                transcoded_video_id = output_storage_filepath.split("/")[-1]
                success = True
                print(f"Successfully uploaded video to {output_storage_basedir}/{output_storage_filepath}")
            else:
                errors.append(f"Error uploading video to {output_storage_basedir}/{output_storage_filepath}")
                print(f"Error uploading video to {output_storage_basedir}/{output_storage_filepath}")
        else:
            errors.append(f"Error transcoding video from to {transcoded_video_output_dir}")
            print(f"Error transcoding video from to {transcoded_video_output_dir}")
    except Exception as e:
        errors.append(str(e))

    try:
        requests.post(TRANSCODE_COMPLETE_WEBHOOK, data={"errors": errors, "success": success, "id": transcoded_video_id})
    except Exception as e:
        print(f"Error sending completion message to {TRANSCODE_COMPLETE_WEBHOOK}")