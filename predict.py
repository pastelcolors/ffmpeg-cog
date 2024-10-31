from cog import BasePredictor, Input, Path
import subprocess
import os
import boto3
from botocore.config import Config
from dotenv import load_dotenv
from datetime import datetime
import json


class Predictor(BasePredictor):
    def setup(self):
        """Setup FFmpeg and R2 client"""
        load_dotenv()

        # Initialize R2 client
        self.r2 = boto3.client(
            "s3",
            endpoint_url=f"https://{os.getenv('R2_ACCOUNT_ID')}.r2.cloudflarestorage.com",
            aws_access_key_id=os.getenv("R2_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("R2_SECRET_ACCESS_KEY"),
            config=Config(signature_version="s3v4"),
            region_name="auto",
        )
        self.bucket_name = os.getenv("R2_BUCKET_NAME")

    def upload_to_r2(self, file_path: str, object_name: str = None) -> str:
        """Upload file to R2 and return the URL"""
        if object_name is None:
            object_name = os.path.basename(file_path)

        try:
            self.r2.upload_file(file_path, self.bucket_name, object_name)
            return f"https://{self.bucket_name}.r2.cloudflarestorage.com/{object_name}"
        except Exception as e:
            raise Exception(f"Failed to upload to R2: {str(e)}")

    def predict(
        self,
        input_file: Path = Input(description="Input video or audio file"),
        format: str = Input(
            description="Output audio format",
            choices=["mp3", "aac", "wav", "ogg"],
            default="mp3",
        ),
        bitrate: str = Input(
            description="Audio bitrate (e.g. 192k, 256k, 320k)", default="192k"
        ),
    ) -> str:
        """Convert video/audio to desired audio format and upload to R2"""

        # Generate unique output filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_filename = f"audio_{timestamp}.{format}"
        output_path = f"/tmp/{output_filename}"

        # Get input file information using ffprobe
        probe_cmd = [
            "ffprobe",
            "-v",
            "quiet",
            "-print_format",
            "json",
            "-show_streams",
            str(input_file),
        ]

        try:
            probe_output = subprocess.run(
                probe_cmd, check=True, capture_output=True, text=True
            )
            file_info = json.loads(probe_output.stdout)

            # Check if input has audio stream
            has_audio = any(
                stream["codec_type"] == "audio"
                for stream in file_info.get("streams", [])
            )

            if not has_audio:
                raise Exception("Input file contains no audio stream")

            # Try fast extraction first (copy codec)
            cmd = [
                "ffmpeg",
                "-i",
                str(input_file),
                "-vn",  # Remove video stream
                "-acodec",
                "copy",
                "-y",
                output_path,
            ]

            try:
                subprocess.run(cmd, check=True, capture_output=True)
            except subprocess.CalledProcessError:
                # Fallback to re-encoding if copy fails
                cmd = [
                    "ffmpeg",
                    "-i",
                    str(input_file),
                    "-vn",
                    "-ab",
                    bitrate,
                    "-y",
                    output_path,
                ]
                subprocess.run(cmd, check=True, capture_output=True)

            # Upload to R2 and return the URL
            url = self.upload_to_r2(output_path, f"audio_files/{output_filename}")

            # Cleanup temporary file
            os.remove(output_path)

            return url

        except subprocess.CalledProcessError as e:
            if os.path.exists(output_path):
                os.remove(output_path)
            raise Exception(f"FFmpeg processing failed: {e.stderr.decode()}")
        except Exception as e:
            if os.path.exists(output_path):
                os.remove(output_path)
            raise e
