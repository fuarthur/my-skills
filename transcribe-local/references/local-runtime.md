# Local runtime and recovery

## Install and inspect

From the skill directory, run `bash scripts/setup.sh`. Runtime defaults to `~/.local/share/mlx-whisper`; override with `MLX_WHISPER_HOME` consistently for setup and transcription. `MLX_WHISPER_PYTHON` can choose a native Python executable. A missing `ffmpeg`/`ffprobe` can be installed with `brew install ffmpeg` when Homebrew is available.

Setup uses a shallow sparse clone of [the requested upstream repository](https://github.com/ml-explore/mlx-examples/tree/main/whisper) and installs its `whisper/` package into `venv/`. It preserves an existing checkout rather than silently pulling updates. `source-commit.txt` and `installed-packages.txt` identify the installed version. Source, dependencies, and models are runtime data; keep them outside the skill/repository.

The first use of each model downloads its MLX weights from Hugging Face to the normal local Hub cache. Use `--model /absolute/path/to/model-directory` for preloaded weights, or `--offline` for already cached ones. Offline failures require obtaining the weights first; do not switch to a cloud STT provider. The default [mlx-community/whisper-small-mlx](https://huggingface.co/mlx-community/whisper-small-mlx) is multilingual; an `.en` model is English-only. For a quality upgrade, [mlx-community/whisper-large-v3-turbo](https://huggingface.co/mlx-community/whisper-large-v3-turbo) is available. Verify exact model IDs rather than deriving them from size names. The upstream [README](https://github.com/ml-explore/mlx-examples/blob/main/whisper/README.md) documents additional models and options.

## Existing subtitles and audio tracks

```sh
ffprobe -v error -show_streams -show_format -of json "/path/lecture.mp4"
# Use the observed subtitle index; this example extracts the first subtitle track.
ffmpeg -nostdin -n -i "/path/lecture.mp4" -map 0:s:0 "/path/task/captions.srt"
```

Sidecar/embedded captions can be automatic, incomplete, translated, or from another recording: verify their provenance and coverage. Image subtitles require OCR. For multiple audio tracks, inspect language tags and listen to choose one; the wrapper uses ffmpeg's default audio selection. Extract a specific observed track when necessary:

```sh
ffmpeg -nostdin -n -i "/path/lecture.mp4" -map 0:a:1 -vn -ac 1 -ar 16000 "/path/task/lecture-audio.wav"
```

Extraction is normally unnecessary: ffmpeg lets Whisper read common audio/video formats directly. The transcript covers speech, not slide text or visuals.

## Long recordings, clips, and quality

Try a representative short range before a large run by adding `--start 600 --end 660 --output-dir /path/task/sample`. Upstream clip processing preserves original-media timestamps but still loads the full audio, so it does not solve memory exhaustion. Inspect language detection for clips: detection may use the recording's opening, so set a known clip language explicitly.

If the full run exceeds memory or needs resumability, extract manageable chunks with `ffmpeg -ss START -t DURATION ...`, giving each a unique output directory. Record each chunk's original start offset. Before combining outputs, add that offset to **both** start/end for every segment and word, regenerate subtitles, and check boundary omissions or overlapping duplicates. Keep chunk files and outputs until validation; label any missing coverage explicitly. Do not report a short pilot as a complete transcript.

Use `--word-timestamps` for fine alignment; it costs extra work and is still an estimate. Recheck high-impact terms against audio and related slides. Repetition or speech generated during silence calls for a targeted rerun; consult the installed `mlx_whisper --help`/API for options such as `condition_on_previous_text=False`, save the rerun separately, and compare. Preserve raw ASR and document corrections rather than presenting guesses as verbatim speech.

## Verification and failures

The wrapper propagates inference/decoding errors and refuses existing output directories. By contrast, the upstream CLI can catch per-file exceptions and finish with exit code zero; inspect its output files and log before claiming success when using it directly.

Successful output includes TXT, SRT, VTT, TSV, JSON and `provenance.json`. Confirm duration/coverage and check representative audio passages. Silence-only recordings may legitimately contain no speech, but the wrapper stops so the agent must investigate. A GPU permission error can require running outside a restrictive sandbox through the normal approval mechanism. On unsupported hardware, report the incompatibility and seek another authorized local engine.
