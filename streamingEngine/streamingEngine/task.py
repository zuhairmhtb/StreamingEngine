from .backends.s3.s3 import S3
from .backends.transcoder.transcoder import TranscoderConfiguration, Transcoder

import os, mimetypes, shutil

from celery import shared_task


TRANSCODING_CONFIGURATIONS = [
    TranscoderConfiguration(audio_bitrate=250000, video_bitrate=250000, width=320),
    TranscoderConfiguration(audio_bitrate=500000, video_bitrate=500000, width=640),
    TranscoderConfiguration(audio_bitrate=1000000, video_bitrate=1000000, width=854),
    TranscoderConfiguration(audio_bitrate=2000000, video_bitrate=2000000, width=1280),
]


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
                    output_storage_basedir:str, output_storage_filepath:str):
    transcoded_video_output_dir = os.path.join(transcoding_base_output_dir, video_folder_name)
    encryption_key_path = os.path.join(transcoding_base_output_dir, encryption_key_filename)
    print(f"Transcoding video from {input_filepath} to {transcoded_video_output_dir}")
    transcoder = Transcoder()
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
            print(f"Successfully uploaded video to {output_storage_basedir}/{output_storage_filepath}")
        else:
            print(f"Error uploading video to {output_storage_basedir}/{output_storage_filepath}")
    else:
        print(f"Error transcoding video from to {transcoded_video_output_dir}")