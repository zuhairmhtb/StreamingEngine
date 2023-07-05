# Streaming Engine

A Django application that receives the path of a video in S3, transcodes the video to HLS with DRM encryption and finally uploads the encrypted HLS files to a S3 Bucket.
It also has a simple view to stream HLS videos.


**Note: Sample Requests are included in the postman collection.**

The following requests included in the postman collection are used:

1. **Upload Video:** Provide a video file and the application uploads the video to S3 bucket. The name of the bucket is added in the .env file of docker. 

2. **Transcode Playlist:** This api receives a 'segment_name' which is the path to the raw input video in the S3 Bucket. It also receives an 'encryption_url' that contains the URL from which the decryption key should be fetched when streaming video. It finally returns a JSON object that contains ID of the transcoded video. This video is transcoded and uploaded to S3.

3. **Get All files:** Retrieves all files in a S3 Bucket's path

4. **Delete All files:** Deletes all files from a relative path of a S3 Bucket. It also deletes files in the sub-directories.

5. **Stream Video**: The url http://localhost:8000/streaming/<video id> streams the video (if it exists) related to the corresponding ID provided in the URL path.