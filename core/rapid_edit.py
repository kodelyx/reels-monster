import subprocess
import json
import sys
import argparse
import platform
import functools
from pathlib import Path

BATCH_SIZE = 40


def load_intervals(config_path):
    """Load intervals from a JSON config file."""
    with open(config_path, "r") as f:
        data = json.load(f)

    if isinstance(data, list):
        intervals = [(s, e) for s, e in data]
    else:
        intervals = [(s, e) for s, e in data["intervals"]]

    if not intervals:
        print("❌ No intervals found in config.")
        sys.exit(1)

    return intervals


@functools.lru_cache(maxsize=1)
def check_nvenc_support():
    """Verify if NVIDIA NVENC is supported by FFmpeg on this machine."""
    try:
        cmd = ["ffmpeg", "-y", "-f", "lavfi", "-i", "nullsrc=s=64x64:d=0.1", "-c:v", "h264_nvenc", "-f", "null", "-"]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        return True
    except Exception:
        return False


def process_batch(batch_idx, batch_intervals, input_file, total_batches, temp_dir):
    """Process a single batch of intervals using FFmpeg with GPU acceleration."""
    T_start = batch_intervals[0][0]
    T_end = batch_intervals[-1][1]
    T_seek_start = max(0.0, T_start - 5.0)

    filter_parts = []
    concat_inputs = []
    for local_idx, (start, end) in enumerate(batch_intervals):
        rel_start = start - T_seek_start
        rel_end = end - T_seek_start
        filter_parts.append(
            f"[0:v]trim=start={rel_start:.2f}:end={rel_end:.2f},setpts=PTS-STARTPTS[v{local_idx}];"
            f"[0:a]atrim=start={rel_start:.2f}:end={rel_end:.2f},asetpts=PTS-STARTPTS[a{local_idx}]"
        )
        concat_inputs.append(f"[v{local_idx}][a{local_idx}]")

    filter_complex = (
        ";".join(filter_parts)
        + ";"
        + "".join(concat_inputs)
        + f"concat=n={len(batch_intervals)}:v=1:a=1[cv][outa];[cv]fps=30[outv]"
    )

    temp_ts_file = temp_dir / f"part_{batch_idx:04d}.ts"

    # Encoder options, fastest first. GPU/hardware encoders can silently fail
    # (headless VM, busy GPU, sandbox) — always keep software libx264 as a
    # last-resort fallback so a stage never dies with a cryptic exit 187.
    sys_type = platform.system().lower()
    encoders = []
    if sys_type == "darwin":
        encoders.append((["-hwaccel", "videotoolbox"], ["-c:v", "h264_videotoolbox", "-b:v", "10M"]))
    elif check_nvenc_support():
        encoders.append((["-hwaccel", "cuda"], ["-c:v", "h264_nvenc", "-b:v", "10M"]))
    encoders.append(([], ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20"]))

    print(f"🚀 Batch {batch_idx + 1}/{total_batches} ({T_start:.2f}s → {T_end:.2f}s)...")
    last_err = None
    for enc_idx, (hwaccel_args, encoder_args) in enumerate(encoders):
        cmd = [
            "ffmpeg", "-y"
        ] + hwaccel_args + [
            "-ss", f"{T_seek_start:.2f}",
            "-accurate_seek",
            "-i", str(input_file),
            "-t", f"{T_end - T_seek_start:.2f}",
            "-filter_complex", filter_complex,
            "-map", "[outv]", "-map", "[outa]"
        ] + encoder_args + [
            "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k",
            str(temp_ts_file)
        ]
        try:
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            # Hardware encoders can exit 0 yet write an empty file — treat that as failure.
            if temp_ts_file.exists() and temp_ts_file.stat().st_size > 0:
                print(f"✅ Batch {batch_idx + 1}/{total_batches} done")
                return temp_ts_file
            last_err = RuntimeError(f"{encoder_args[1]} produced empty output")
        except subprocess.CalledProcessError as e:
            last_err = e
        if enc_idx + 1 < len(encoders):
            print(f"⚠️ {encoder_args[1]} failed, falling back to {encoders[enc_idx + 1][1][1]}...")

    print(f"❌ Batch {batch_idx + 1} failed on all encoders.")
    raise last_err


def main():
    parser = argparse.ArgumentParser(description="RapidEdit — cut video using keep intervals")
    parser.add_argument("-path", required=True, help="Input video file")
    parser.add_argument("-out", required=True, help="Output video file")
    parser.add_argument("-config", required=True, help="JSON file with intervals")
    args = parser.parse_args()

    input_file = Path(args.path)
    output_file = Path(args.out)

    if not input_file.exists():
        print(f"❌ Input file not found: {input_file}")
        sys.exit(1)

    intervals = load_intervals(args.config)

    # Batch intervals
    batches = [intervals[i:i + BATCH_SIZE] for i in range(0, len(intervals), BATCH_SIZE)]

    temp_dir = Path("temp_parts")
    temp_dir.mkdir(exist_ok=True)

    ts_files = []
    print(f"Processing {len(intervals)} intervals in {len(batches)} batches...")

    for idx, batch in enumerate(batches):
        try:
            ts_file = process_batch(idx, batch, input_file, len(batches), temp_dir)
            ts_files.append(ts_file)
        except Exception as e:
            print("Processing stopped.")
            raise e

    # Concatenate
    concat_list_file = Path("concat_list.txt")
    with open(concat_list_file, "w") as f:
        for ts_file in ts_files:
            if ts_file:
                f.write(f"file '{ts_file.resolve()}'\n")

    concat_cmd = [
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(concat_list_file),
        "-c", "copy",
        str(output_file)
    ]

    print("🔗 Concatenating...")
    subprocess.run(concat_cmd, check=True)

    # Cleanup
    print("🧹 Cleaning up...")
    if concat_list_file.exists():
        concat_list_file.unlink()
    for ts_file in ts_files:
        if ts_file and ts_file.exists():
            ts_file.unlink()
    if temp_dir.exists():
        temp_dir.rmdir()

    print(f"✨ Done! Output: {output_file}")


if __name__ == "__main__":
    main()
