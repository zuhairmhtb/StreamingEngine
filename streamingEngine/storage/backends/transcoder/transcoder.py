from typing import List
import ffmpeg, io, os
from typing import Union, Generator


class TranscoderOutput(object):
    def __init__(self, bitrate: str, resolution: str, output: Union[bytes, None], filename: str):
        self.bitrate = bitrate
        self.resolution = resolution
        self.output = output
        self.filename = filename


class HLSTranscoder(object):
    def __init__(self,
                 output_video_codec: str = 'h264',
                 output_audio_codec='aac',
                 hls_time=10,
                 hls_list_size=0,
                 hls_segment_filename='output_%v_%03d.ts',
                 resolutions=None):
        if resolutions is None:
            resolutions = [
                {'bitrate': '600k', 'resolution': '320:-1', 'output_file_suffix': 'output_600k.m3u8', 'folder': '600k'},
                # {'bitrate': '800k', 'resolution': '640:-1', 'output_file_suffix': 'output_800k.m3u8', 'folder': '800k'},
                # {'bitrate': '1200k', 'resolution': '854:-1', 'output_file_suffix': 'output_1200k.m3u8', 'folder': '1200k'},
                # {'bitrate': '2000k', 'resolution': '1280:-1', 'output_file_suffix': 'output_2000k.m3u8', 'folder': '2000k'},
                # {'bitrate': '4000k', 'resolution': '1920:-1', 'output_file_suffix': 'output_4000k.m3u8', 'folder': '4000k'}
            ]
        self.resolutions: List[dict] = resolutions

        self.output_video_codec = output_video_codec
        self.output_audio_codec = output_audio_codec
        self.hls_time = hls_time  # seconds
        self.hls_list_size = hls_list_size
        self.hls_segment_filename = hls_segment_filename


    def transcode_from_bytes(self,
                        stream: bytes, format: str, input_framerate: int, loglevel: str = 'quiet'
                        ) -> Generator[TranscoderOutput, None, None]:
        if not (stream is None) and not (format is None) and (len(format) > 0) and not (input_framerate is None):
            for resolution in self.resolutions:
                output_stream = ffmpeg.output(
                    ffmpeg.input('pipe:', format=format, r=input_framerate, loglevel=loglevel),
                    'pipe:',
                    format='hls',
                    vcodec=self.output_video_codec,
                    acodec=self.output_audio_codec,
                    vf=f'scale={resolution["resolution"]}',
                    video_bitrate=resolution['bitrate'],
                    hls_time=self.hls_time,
                    hls_list_size=self.hls_list_size,
                    hls_segment_filename=self.hls_segment_filename
                )
                output: Union[bytes, None]
                output, err = ffmpeg.run(output_stream, input=stream, capture_stdout=True, capture_stderr=True)

                yield TranscoderOutput(
                    bitrate=resolution['bitrate'],
                    resolution=resolution['resolution'],
                    output=output,
                    filename=resolution['output_file']
                )

    def transcode_from_file(self,
                        input_filepath: str, format: str, input_framerate: int, output_dir:str, output_fileprefix:str, loglevel: str = 'quiet'
                        ) -> Generator[TranscoderOutput, None, None]:
        if not (input_filepath is None) and not (format is None) and (len(format) > 0) and not (input_framerate is None):
            for resolution in self.resolutions:
                inp = ffmpeg.input(input_filepath)
                output_dir_current_resolution = os.path.join(output_dir, resolution['folder'])
                if not os.path.exists(output_dir_current_resolution):
                    os.makedirs(output_dir_current_resolution)

                output_filepath = os.path.join(output_dir_current_resolution, f"{output_fileprefix}{resolution['output_file_suffix']}")
                hls_segment_filepath = os.path.join(output_dir_current_resolution, f"{output_fileprefix}{self.hls_segment_filename}")

                output_stream = ffmpeg.output(
                    inp,
                    output_filepath,
                    format='hls',
                    vcodec=self.output_video_codec,
                    acodec=self.output_audio_codec,
                    vf=f'scale={resolution["resolution"]}',
                    video_bitrate=resolution['bitrate'],
                    hls_time=self.hls_time,
                    hls_list_size=self.hls_list_size,
                    hls_segment_filename=hls_segment_filepath
                )
                output: Union[bytes, None]
                output, err = ffmpeg.run(output_stream)

                yield TranscoderOutput(
                    bitrate=resolution['bitrate'],
                    resolution=resolution['resolution'],
                    output=output,
                    filename=output_filepath
                )

    def transcode_video(self,
                        stream: bytes, format: str, input_framerate: int, loglevel: str = 'quiet'
                        ) -> Generator[TranscoderOutput, None, None]:
        return self.transcode_from_bytes(stream=stream, format=format, input_framerate=input_framerate, loglevel=loglevel)


if __name__ == "__main__":
    base_filedir = 'E:\\Accessories\\WebDevelopment\\Python\\StreamingEngine\\sample-video-transcoding'
    input_filepath = os.path.join(base_filedir, 'video.mp4')

    with open(input_filepath, 'rb') as f:
        content = f.read()

    transcoder = HLSTranscoder()
    for output in transcoder.transcode_video(stream=input_filepath, format='mp4', input_framerate=30, loglevel='verbose'):
        print(type(output.output))
        print(output.bitrate)
        print(output.resolution)
        print(output.filename)

    # transcoder = HLSTranscoder()
    # for output in transcoder.transcode_from_file(input_filepath, output_dir=os.path.join(base_filedir, 'output'), output_fileprefix='sample_',
    #                                              format='mp4', input_framerate=30, loglevel='verbose'):
    #     print(type(output.output))
    #     print(output.bitrate)
    #     print(output.resolution)
    #     print(output.filename)

