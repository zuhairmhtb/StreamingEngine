from typing import List
import ffmpeg, io, os
from typing import Union, Generator


class TranscoderOutput(object):
    def __init__(self, bitrate: str, resolution: str, output: Union[bytes, None], filename: str):
        self.bitrate = bitrate
        self.resolution = resolution
        self.output = output
        self.filename = filename


class TranscoderConfiguration:
    def __init__(self, bitrate:str, resolution:str, manifest_relative_filepath:str='', input_framerate:int=30):
        self.bitrate = bitrate
        self.resolution = resolution
        self.manifest_filepath:str=manifest_relative_filepath
        self.input_framerate:int=input_framerate

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
                        stream: bytes, format: str, input_framerate: int,  hls_output_dir:str, loglevel: str = 'quiet',
                        ) -> Generator[TranscoderOutput, None, None]:
        """
        If you try to read bytes from mp4 and it throws error 'Error retrieving a packet from demuxer: Invalid data found when processing input'
        then try to create a valid mp4 file using the following command:

        ffmpeg -i <input file>.mp4 -movflags faststart -acodec copy -vcodec copy <output file>.mp4

        Then try reading the new file. This happens because metadata in mp4 can be not only at the beginning of the
        file, but also at the end. And accordingly ffpmeg cannot get them.
        Link: https://github.com/fluent-ffmpeg/node-fluent-ffmpeg/issues/932

        Current problems:
        1. Even if ffmpeg returns the manifest file (of the hls video) as bytes, it saves the .ts files on the machine.

        The plan was to create each ts file and return them so that it can be saved to s3 directly without saving it
        locally first. This will save memory of lambda and reduce the processing time.
        Looked on internet but could not find any package that does it.

        :param stream:
        :param format:
        :param input_framerate:
        :param loglevel:
        :return:
        """
        if not (stream is None) and not (format is None) and (len(format) > 0) and not (input_framerate is None):
            hls_output_path = f"{hls_output_dir}/{self.hls_segment_filename}"
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
                    hls_segment_filename=hls_output_path
                )
                output: Union[bytes, None]
                output, err = ffmpeg.run(output_stream, input=stream, capture_stdout=True, capture_stderr=True)

                yield TranscoderOutput(
                    bitrate=resolution['bitrate'],
                    resolution=resolution['resolution'],
                    output=output,
                    filename=f"{resolution['output_file_suffix']}"
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


    def create_master_playlist(self, configurations:List[TranscoderConfiguration])->str:
        master_playlist = '#EXTM3U\n'

        for config in configurations:
            # Add variant playlist entry to the master playlist
            master_playlist += f'#EXT-X-STREAM-INF:BANDWIDTH={config.bitrate},RESOLUTION={config.resolution}\n'
            master_playlist += f'{config.manifest_filepath}\n'

        return master_playlist

    def transcode(self,
                  input_filepath:str,
                  input_framerate:int,
                  base_output_dir:str,
                  manifest_filename:str,
                  configuration:TranscoderConfiguration,
                  output_format:str='hls',
                  hls_file_pattern:str='output_%v_%03d.ts',
                  overwrite_output=True

                  ) ->Union[str, None]:
        if not (input_filepath is None) and not (input_framerate is None) \
                and not (base_output_dir is None) and not (manifest_filename is None) \
                and (not configuration is None):
            file_extension = input_filepath.split(".")[-1]
            if len(file_extension) == 0:
                return None
            input_video = ffmpeg.input(input_filepath)
            if not os.path.exists(base_output_dir):
                os.makedirs(base_output_dir)

            hls_segment_filepath = os.path.join(base_output_dir, hls_file_pattern)
            manifest_filepath = os.path.join(base_output_dir, manifest_filename)

            output_stream = ffmpeg.output(
                input_video,
                manifest_filepath,
                format=output_format,
                vcodec=self.output_video_codec,
                acodec=self.output_audio_codec,
                vf=f'scale={configuration.resolution}',
                video_bitrate=configuration.bitrate,
                hls_time=self.hls_time,
                hls_list_size=self.hls_list_size,
                hls_segment_filename=hls_segment_filepath
            )

            output, error = ffmpeg.run(output_stream, capture_stderr=True, capture_stdout=True)
            return manifest_filepath
        return None

    def transcode_adaptive_bitrate(self, input_filepath:str, manifest_filename:str, configurations:List[TranscoderConfiguration], output_folder:str)->str:
        added_transcodings: List[TranscoderConfiguration] = []
        for configuration in configurations:
            output_dir = os.path.join(output_folder, configuration.bitrate)
            configuration.manifest_filepath = f"{configuration.bitrate}/{manifest_filename}"
            try:
                manifest_absolute_path = self.transcode(
                    input_filepath=input_filepath,
                    input_framerate=configuration.input_framerate,
                    base_output_dir=output_dir,
                    manifest_filename=manifest_filename,
                    configuration=configuration,
                    output_format='hls',
                    hls_file_pattern= os.path.join(output_dir, "output_%v_%03d.ts")
                )
                if not (manifest_absolute_path is None) and len(manifest_absolute_path) > 0:
                    added_transcodings.append(configuration)
            except Exception as e:
                print(e)

        master_playlist_content = self.create_master_playlist(added_transcodings)

        if not (master_playlist_content is None) and len(master_playlist_content) > 0:
            master_playlist_filepath = os.path.join(output_folder, 'master.m3u8')
            with open(master_playlist_filepath, 'w') as f:
                f.write(master_playlist_content)
            return master_playlist_filepath
        else:
            print("No content in master playlist")
        return None


if __name__ == "__main__":
    base_filedir = 'E:\\Accessories\\WebDevelopment\\Python\\StreamingEngine\\sample-video-transcoding'
    input_filepath = os.path.join(base_filedir, 'video.mp4')
    output_folder = os.path.join(base_filedir, 'output')
    # input_filepath = "http://127.0.0.1:8000/storage/video/?file=b457e616-09dc-4cda-9ff9-5cf182bcda0a.mp4"


    # Transcode from bytes
    # with open(input_filepath, 'rb') as f:
    #     content = f.read()
    #
    # output_dir = os.path.join(base_filedir, 'output')
    # transcoder = HLSTranscoder()
    # for output in transcoder.transcode_from_bytes(
    #         stream=content, format='mp4', input_framerate=30, loglevel='verbose', hls_output_dir=output_dir
    # ):
    #     print(type(output.output))
    #     print(output.bitrate)
    #     print(output.resolution)
    #     print(output.filename)
    #     output_filepath = os.path.join(output_dir, f"sample_{output.filename}")
    #     with open(output_filepath, 'wb') as f:
    #         f.write(output.output)

    # Transcode from file to byte
    # transcoder = HLSTranscoder()
    # for output in transcoder.transcode_from_file(input_filepath, output_dir=os.path.join(base_filedir, 'output'), output_fileprefix='sample_',
    #                                              format='mp4', input_framerate=30, loglevel='verbose'):
    #     print(type(output.output))
    #     print(output.bitrate)
    #     print(output.resolution)
    #     print(output.filename)

    # Transcode from file to file
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
        TranscoderConfiguration(
            bitrate='1200k',
            resolution='854:-1',
            input_framerate=30
        ),
        TranscoderConfiguration(
            bitrate='2000k',
            resolution='1280:-1',
            input_framerate=30
        ),
    ]
    transcoder = HLSTranscoder()
    master_manifest_path = transcoder.transcode_adaptive_bitrate(input_filepath=input_filepath, manifest_filename='output.m3u8',
                                          configurations=configurations, output_folder=output_folder)
    print(master_manifest_path)


