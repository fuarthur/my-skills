#!/usr/bin/env python3
"""Run local MLX Whisper and preserve transcript formats plus source provenance."""

import argparse
from datetime import datetime, timezone
from importlib.metadata import version
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("media", type=Path, help="Local audio/video file")
    parser.add_argument("--output-dir", type=Path, required=True, help="New directory (never overwrite)")
    parser.add_argument("--model", default="mlx-community/whisper-small-mlx", help="HF model ID or local model directory")
    parser.add_argument("--language", help="Known spoken language code; omit to detect")
    parser.add_argument("--initial-prompt", help="Verified vocabulary or proper names")
    parser.add_argument("--word-timestamps", action="store_true")
    parser.add_argument("--offline", action="store_true", help="Require local/cached weights; no Hub requests")
    parser.add_argument("--start", type=float, default=0, help="Clip start in original recording seconds")
    parser.add_argument("--end", type=float, help="Clip end in original recording seconds")
    args = parser.parse_args()
    media = args.media.expanduser().resolve()
    output = args.output_dir.expanduser().resolve()
    if not media.is_file():
        parser.error(f"Media not found: {media}")
    if output.exists():
        parser.error(f"Output already exists; choose a new directory: {output}")
    if not math.isfinite(args.start) or args.start < 0:
        parser.error("--start must be finite and nonnegative")
    if args.end is not None and (not math.isfinite(args.end) or args.end <= args.start):
        parser.error("--end must be finite and greater than --start")
    for tool in ("ffmpeg", "ffprobe"):
        if not shutil.which(tool):
            parser.error(f"Missing {tool}; install ffmpeg first")
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", str(media)],
        capture_output=True, text=True, check=True,
    )
    info = json.loads(probe.stdout)
    if not any(s.get("codec_type") == "audio" for s in info.get("streams", [])):
        parser.error("No audio track; inspect visual content/OCR instead")
    duration = float(info.get("format", {}).get("duration", 0)) or None
    if duration is not None and args.start >= duration:
        parser.error("--start is outside the recording")
    if args.offline:
        os.environ["HF_HUB_OFFLINE"] = "1"
    # Set before importing Hugging Face via mlx_whisper; audio is never uploaded.
    os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
    import mlx_whisper
    from mlx_whisper.writers import get_writer

    clip = [args.start] if args.end is None else [args.start, args.end]
    result = mlx_whisper.transcribe(
        str(media), path_or_hf_repo=args.model, task="transcribe",
        language=args.language, initial_prompt=args.initial_prompt,
        word_timestamps=args.word_timestamps, clip_timestamps=clip, verbose=False,
    )
    segments = result.get("segments", [])
    if not result.get("text", "").strip() or not segments:
        raise RuntimeError("No speech recognized; inspect audio/silence/language before using this as context")
    for segment in segments:
        start, end = float(segment["start"]), float(segment["end"])
        if not (math.isfinite(start) and math.isfinite(end) and 0 <= start <= end):
            raise RuntimeError("Invalid segment timestamps; inspect this transcription")
    runtime = Path(os.environ.get("MLX_WHISPER_HOME", "~/.local/share/mlx-whisper")).expanduser()
    commit_file = runtime / "source-commit.txt"
    metadata = {
        "source": str(media), "source_bytes": media.stat().st_size,
        "source_mtime_ns": media.stat().st_mtime_ns, "duration_seconds": duration,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "engine": "mlx-whisper", "engine_version": version("mlx-whisper"),
        "upstream_commit": commit_file.read_text().strip() if commit_file.exists() else None,
        "model": args.model, "task": "transcribe", "requested_language": args.language,
        "detected_language": result.get("language"), "word_timestamps": args.word_timestamps,
        "initial_prompt": args.initial_prompt, "offline": args.offline,
        "requested_range_seconds": [args.start, args.end if args.end is not None else duration],
        "timestamp_origin": "original recording", "segment_count": len(segments),
        "status": "machine transcript; requires spot checking",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    # Complete all files in staging; publish only after every writer succeeds.
    with tempfile.TemporaryDirectory(prefix=".transcribe-", dir=output.parent) as staging:
        get_writer("all", staging)(result, "transcript")
        (Path(staging) / "provenance.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        output.mkdir(exist_ok=False)
        for item in Path(staging).iterdir():
            item.rename(output / item.name)
    print(f"Saved {len(segments)} segments ({result.get('language')}) to {output}")


if __name__ == "__main__":
    main()
