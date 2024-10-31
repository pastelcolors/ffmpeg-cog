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
        """Setup FFmpeg and optionally load R2 credentials from env"""
        load_dotenv()
        self.r2 = None
        self.bucket_name = None

    def initialize_r2(
        self, account_id: str, access_key: str, secret_key: str, bucket_name: str
    ):
        """Initialize R2 client with provided credentials"""
        self.r2 = boto3.client(
            "s3",
            endpoint_url=f"https://{account_id}.r2.cloudflarestorage.com",
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            config=Config(signature_version="s3v4"),
            region_name="auto",
        )
        self.bucket_name = bucket_name

    def upload_to_r2(self, file_path: str, object_name: str = None) -> str:
        """Upload file to R2 and return the URL"""
        if not self.r2 or not self.bucket_name:
            raise Exception(
                "R2 client not initialized. Provide R2 credentials to upload."
            )

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
        upload_to_r2: bool = Input(
            description="Whether to upload the output to R2", default=True
        ),
        r2_account_id: str = Input(
            description="Cloudflare R2 Account ID (optional if set in .env)",
            default=None,
        ),
        r2_access_key: str = Input(
            description="Cloudflare R2 Access Key ID (optional if set in .env)",
            default=None,
        ),
        r2_secret_key: str = Input(
            description="Cloudflare R2 Secret Access Key (optional if set in .env)",
            default=None,
        ),
        r2_bucket_name: str = Input(
            description="Cloudflare R2 Bucket Name (optional if set in .env)",
            default=None,
        ),
    ) -> str:
        """Convert video/audio to desired audio format and optionally upload to R2"""

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

            if upload_to_r2:
                # Use provided credentials or fall back to env variables
                account_id = r2_account_id or os.getenv("R2_ACCOUNT_ID")
                access_key = r2_access_key or os.getenv("R2_ACCESS_KEY_ID")
                secret_key = r2_secret_key or os.getenv("R2_SECRET_ACCESS_KEY")
                bucket_name = r2_bucket_name or os.getenv("R2_BUCKET_NAME")

                # Check if we have all required credentials
                if not all([account_id, access_key, secret_key, bucket_name]):
                    raise Exception(
                        "Missing R2 credentials. Provide them as parameters or in .env file"
                    )

                # Initialize R2 client with credentials
                self.initialize_r2(account_id, access_key, secret_key, bucket_name)

                # Upload to R2 and return the URL
                url = self.upload_to_r2(output_path, f"audio_files/{output_filename}")
                os.remove(output_path)
                return url
            else:
                # If not uploading to R2, return the local file path
                return str(output_path)

        except subprocess.CalledProcessError as e:
            if os.path.exists(output_path):
                os.remove(output_path)
            raise Exception(f"FFmpeg processing failed: {e.stderr.decode()}")
        except Exception as e:
            if os.path.exists(output_path):
                os.remove(output_path)
            raise e
