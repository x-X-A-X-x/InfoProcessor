import subprocess
from pathlib import Path
#Install ffmpeg and make sure ffmpeg is in your PATH (or use the full path to ffmpeg.exe).
#This uses the LAME encoder (libmp3lame) and keeps only the audio (-vn).

def mp4_to_mp3(src_path, dst_path=None, bitrate="192k", track=0):
    """
    Convert the audio track of an MP4 to MP3 via ffmpeg.

    src_path: path to the .mp4 file
    dst_path: optional output .mp3 path (defaults to same name)
    bitrate:  e.g. "128k", "192k", "320k"
    track:    which audio track to use (0 = first)
    """
    src = Path(src_path)
    dst = Path(dst_path) if dst_path else src.with_suffix(".mp3")

    cmd = [
        "ffmpeg",
        "-y",               # overwrite
        "-i", str(src),     # input
        "-map", f"0:a:{track}",  # pick audio track
        "-vn",              # no video
        "-c:a", "libmp3lame",
        "-b:a", bitrate,
        str(dst)
    ]
    subprocess.run(cmd, check=True)

# Example: single file
mp4_to_mp3("input_video.mp4", bitrate="192k")

# Example: batch all MP4s in a folder
for mp4 in Path(r"D:\Videos").glob("*.mp4"):
    try:
        mp4_to_mp3(mp4, bitrate="192k")
        print(f"OK: {mp4.name}")
    except subprocess.CalledProcessError:
        print(f"FAILED: {mp4.name}")
