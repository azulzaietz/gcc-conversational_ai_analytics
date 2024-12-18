# Audio Formatter

This project provides a tool for formatting any raw audio files format supported by [FFmpeg](https://www.ffmpeg.org/ffmpeg.html) (e.g., WAV) to FLAC format, extracting metadata, and uploading them to Google Cloud Storage.

## Functionality

1. **Download:** Downloads the raw audio file from a Google Cloud Storage (GCS) bucket.
2. **Format:** Converts the raw audio to FLAC format using FFmpeg, ensuring the desired number of channels.
3. **Metadata Extraction:** Extracts audio stream metadata (codec, sample rate, etc.) using FFprobe.
4. **File Metadata Extraction:** Extracts metadata from the filename, such as case manager email and creation date.
5. **Metadata Creation:** Creates a JSON file containing all extracted metadata.
6. **Upload:** Uploads the formatted audio and metadata JSON to specified GCS buckets.
7. **Error Handling:** Logs FFmpeg errors to Google Cloud Logging.
8. **Temporary File Cleanup:** Deletes temporary files created during the process.

## Usage

1. **Prerequisites:**
    - Google Cloud project with necessary permissions
    - Ingested filenames should follow this structure `[10-digit phone number] [case manager email] [timestamp].[file extension]` Any other additional metadata in the filename should be separated by a space and not any other special characters. Example: `9999999999 test@domain.com 2024-09-19T15:52:58Z.wav` 
2. **Configuration:**
    - Set the corresponding environment variables for the Cloud Function. For more information about the variables [click this documentation](../README.md)
3. **Execution:**
    - Cloud Function is triggered through an EventArc when a `google.cloud.storage.object.v1.finalized` event occurs.

## Dependencies
```
functions-framework==3.*
google-auth==2.17.0
google-cloud-storage==2.8.0
google-cloud-logging==3.11.0
```

## Output

1. **FLAC encoded file**: A file renamed with an UUID stored in GCS as a blob like: `creation-date/filename.flac`
2. **FLAC encoded file metadata**: A json file named as the encoded file containing metadata, stored as: `creation-date/filename.json`. Contains:

| Field | Description | Type | Example |
|---|---|---|---|
| `stream` | Contains audio stream metadata | `object` |  |
| `stream.codec_name` | Encoding used for the audio | `string` | `"flac"` |
| `stream.sample_rate` | Audio sample rate in Hz | `string` | `"48000"` |
| `stream.channels` | Number of audio channels | `string` | `"2"` |
| `stream.channel_layout` | Channel layout of the audio | `string` | `"stereo"` |
| `stream.start_time` | Start time of the audio stream | `string` | `"0.000000"` |
| `stream.duration` | Duration of the audio stream in seconds | `string` | `"270.133333"` |
| `stream.bits_per_raw_sample` | Bits per raw audio sample | `string` | `"0"` |
| `encoder` | Encoder used to create the audio file | `string` | `"Lavf59.27.100"` |
| `case_manager_email` | Email address extracted from the filename | `string` | `"test@insmed.com"` |
| `create_date` | Date extracted from the filename | `string` | `"2024-09-19"` |
| `patient_id` | Patient phone number extracted from filename and hashed | `string` ||

## Error handling
Error could occur when changing the format of the audio file. As it is done by command the script checks for the existence of the output file, if it exists then continues, otherwise it logs an error. Where the entry contains:
- **ffmpeg_error**: Which is the error message produced by ffmpeg or any exception that might have catched. 
- **raw_file_gcs_path**: Which is a string with the original filename (raw) that produced the error during the conversion
