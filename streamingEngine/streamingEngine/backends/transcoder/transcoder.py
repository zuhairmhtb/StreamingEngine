import os.path
from typing import List
from typing import Union, Generator

import ffmpeg, sys, datetime
import ffmpeg_streaming
from ffmpeg_streaming._input import Input
from ffmpeg_streaming import Formats, Format, Bitrate, Representation, Size


def monitor(ffmpeg, duration, time_, time_left, process):
    """
    Handling proccess.

    Examples:
    1. Logging or printing ffmpeg command
    logging.info(ffmpeg) or print(ffmpeg)

    2. Handling Process object
    if "something happened":
        process.terminate()

    3. Email someone to inform about the time of finishing process
    if time_left > 3600 and not already_send:  # if it takes more than one hour and you have not emailed them already
        ready_time = time_left + time.time()
        Email.send(
            email='someone@somedomain.com',
            subject='Your video will be ready by %s' % datetime.timedelta(seconds=ready_time),
            message='Your video takes more than %s hour(s) ...' % round(time_left / 3600)
        )
       already_send = True

    4. Create a socket connection and show a progress bar(or other parameters) to your users
    Socket.broadcast(
        address=127.0.0.1
        port=5050
        data={
            percentage = per,
            time_left = datetime.timedelta(seconds=int(time_left))
        }
    )

    :param ffmpeg: ffmpeg command line
    :param duration: duration of the video
    :param time_: current time of transcoded video
    :param time_left: seconds left to finish the video process
    :param process: subprocess object
    :return: None
    """
    per = round(time_ / duration * 100)
    sys.stdout.write(
        "\rTranscoding...(%s%%) %s left [%s%s]" %
        (per, datetime.timedelta(seconds=int(time_left)), '#' * per, '-' * (100 - per))
    )
    sys.stdout.flush()
class TranscoderConfiguration(object):
    def __init__(self, audio_bitrate:int, video_bitrate:int, width:int, height:int=-1):
        self.audio_bitrate = audio_bitrate
        self.video_bitrate = video_bitrate
        self.width = width
        self.height = height

class Transcoder(object):
    def __init__(self, output_video_codec: str = 'h264', output_audio_codec='aac'):
        self.output_video_codec = output_video_codec
        self.output_audio_codec = output_audio_codec


    def __get_video_height(self, input_filepath:str, current_width:int)->int:
        probe = ffmpeg.probe(input_filepath)
        video_info = next(stream for stream in probe['streams'] if stream['codec_type'] == 'video')

        # Extract width and height
        width = int(video_info['width'])
        height = int(video_info['height'])

        return int( height * current_width / width )




    def transcode(self, input_filepath:str, base_output_dir:str, manifest_filename:str,
                  configurations:List[TranscoderConfiguration], output_formats:List[str]=['hls'],
                  encryption_key_directory:str=None, encryption_key_url:str=None, *args, **kwargs) -> Union[str, None]:
        if not (input_filepath is None) and len(input_filepath) > 0 \
                and not (base_output_dir is None) and len(base_output_dir) > 0 \
                and not (manifest_filename is None) and len(manifest_filename) > 0 \
                and len(configurations) > 0 and len(output_formats) > 0:
            if not os.path.exists(input_filepath):
                return None
            video = ffmpeg_streaming.input(input_filepath)
            for format in output_formats:
                output_format = None
                if format == 'hls':
                    output_format = video.hls(Formats.h264(audio=self.output_audio_codec, video=self.output_video_codec))

                if not output_format is None:
                    output_format.representations(
                        *[
                            Representation(
                                size=Size(width=config.width, height=config.height if config.height > 0 else self.__get_video_height(input_filepath=input_filepath, current_width=config.width)),
                                bitrate=Bitrate(audio=config.audio_bitrate, video=config.video_bitrate)
                            ) for config in configurations]
                    )
                    if not os.path.exists(base_output_dir):
                        os.makedirs(base_output_dir)
                    output_filepath = os.path.join(base_output_dir, manifest_filename)

                    if not (encryption_key_directory is None) and not (encryption_key_url is None):
                        output_format.encryption(encryption_key_directory, encryption_key_url)
                    output_format.output(output_filepath, monitor=monitor)
                    return output_filepath

        return None

if __name__ == "__main__":
    configs = [
        TranscoderConfiguration(audio_bitrate=250000, video_bitrate=250000, width=320),
        TranscoderConfiguration(audio_bitrate=500000, video_bitrate=500000, width=640),
        TranscoderConfiguration(audio_bitrate=1000000, video_bitrate=1000000, width=854),
        TranscoderConfiguration(audio_bitrate=2000000, video_bitrate=2000000, width=1280),
    ]

    transcoder = Transcoder()
    basedir = "C:\\Users\\DELL\\Desktop\\zuhair_tests\\drip\\sample\\"
    res = transcoder.transcode(
        input_filepath="C:\\Users\\DELL\\Desktop\\zuhair_tests\\drip\\streaming-engine\\streamingEngine\\downloads\\3894fe7f-152d-4be2-a9d3-065dc0fe57a8\\sample.mp4",
        base_output_dir=os.path.join(basedir, "video"),
        manifest_filename="master.m3u8",
        configurations=configs,
        encryption_key_directory=os.path.join(basedir, "key"),
        encryption_key_url="http://127.0.0.1:8000/streaming/key"
    )
    print(res)