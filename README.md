# Video/Audio to Audio Converter

A Cog-based service that converts video/audio files to various audio formats with optional Cloudflare R2 storage integration.

## Features

- Convert video files to audio formats (mp3, aac, wav, ogg)
- Extract audio from video files
- Configurable audio bitrate
- Optional upload to Cloudflare R2 storage
- Fast extraction using codec copy when possible
- Fallback to re-encoding when needed

## Prerequisites

- [Cog](https://github.com/replicate/cog)
- FFmpeg
- Python 3.11
- Cloudflare R2 account (optional)

## Configuration

### Environment Variables

When using R2 storage, set these in your `.env` file:

- `R2_ACCOUNT_ID`: Your Cloudflare account ID
- `R2_ACCESS_KEY_ID`: R2 access key
- `R2_SECRET_ACCESS_KEY`: R2 secret key
- `R2_BUCKET_NAME`: R2 bucket name

### Supported Formats

- MP3 (default)
- AAC
- WAV
- OGG

### Bitrate Options

Default: 192k
Common values:

- 128k (lower quality)
- 192k (balanced)
- 256k (high quality)
- 320k (highest quality)

## How It Works

1. The service first checks if the input file contains an audio stream
2. Attempts fast extraction by copying the audio codec directly
3. If fast extraction fails, falls back to re-encoding with specified format/bitrate
4. Optionally uploads the result to R2 storage
5. Returns either a R2 URL or local file path

## Error Handling

The service handles various error cases:

- Missing audio streams
- FFmpeg processing failures
- R2 upload issues
- Missing credentials
- Invalid input files
