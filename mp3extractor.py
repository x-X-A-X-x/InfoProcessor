import argparse
import os
import shutil
import subprocess
import sys

def main():
    p = argparse.ArgumentParser(description="Extract MP3 audio from an MP4 file.")
    p.add_argument("input", help="Path to input .mp4 file")
    p.add_argument("-o", "--output", help="Path to output .mp3 (optional)")
    p.add_argument("-b", "--bitrate", default="192k", help="Audio bitrate (e.g., 128k, 192k, 256k)")
    args = p.parse_args()

    # 1) Check ffmpeg availability
    if shutil.which("ffmpeg") is None:
        print("Error: ffmpeg not found. Install ffmpeg and ensure it's in your PATH.", file=sys.stderr)
        sys.exit(1)

    # 2) Validate input
    in_path = os.path.abspath(args.input)
    if not os.path.isfile(in_path):
        print(f"Error: input file not found: {in_path}", file=sys.stderr)
        sys.exit(1)

    # 3) Derive output name if not provided
    if args.output:
        out_path = os.path.abspath(args.output)
    else:
        base, _ = os.path.splitext(in_path)
        out_path = base + ".mp3"

    # 4) Build ffmpeg command
    # -vn = no video, -acodec libmp3lame = encode as MP3, -b:a = bitrate
    cmd = [
        "ffmpeg",
        "-y",                # overwrite output if exists
        "-i", in_path,       # input
        "-vn",               # drop video
        "-acodec", "libmp3lame",
        "-b:a", args.bitrate,
        out_path
    ]

    # 5) Run and stream progress
    print("Running:", " ".join(cmd))
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        for line in proc.stdout:
            # ffmpeg prints progress to stderr (merged into stdout here)
            if "time=" in line or "Duration:" in line:
                print(line.strip())
    except KeyboardInterrupt:
        proc.kill()
        sys.exit(130)

    rc = proc.wait()
    if rc != 0:
        print(f"ffmpeg failed with exit code {rc}", file=sys.stderr)
        sys.exit(rc)

    print(f"Done! MP3 saved to: {out_path}")

if __name__ == "__main__":
    main()