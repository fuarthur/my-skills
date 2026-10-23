#!/usr/bin/env bash
set -euo pipefail

runtime="${MLX_WHISPER_HOME:-$HOME/.local/share/mlx-whisper}"
if [[ "$(uname -s)" != Darwin || "$(uname -m)" != arm64 ]]; then
  echo "MLX Whisper requires a native Apple Silicon macOS environment." >&2
  exit 1
fi
for tool in git ffmpeg ffprobe; do
  command -v "$tool" >/dev/null || { echo "Missing $tool; install it first." >&2; exit 1; }
done
if [[ ! -x "$runtime/venv/bin/python" ]]; then
  python_bin="${MLX_WHISPER_PYTHON:-}"
  if [[ -z "$python_bin" ]]; then
    for candidate in python3.13 python3.12 python3.11 python3; do
      if command -v "$candidate" >/dev/null; then python_bin="$candidate"; break; fi
    done
  fi
  [[ -n "$python_bin" ]] || { echo "Install a native Python 3 first." >&2; exit 1; }
  "$python_bin" -c 'import platform; assert platform.machine() == "arm64", "Use native arm64 Python"'
  mkdir -p "$runtime"
  "$python_bin" -m venv "$runtime/venv"
fi
if [[ ! -d "$runtime/source/.git" ]]; then
  git clone --depth 1 --filter=blob:none --sparse \
    https://github.com/ml-explore/mlx-examples.git "$runtime/source"
fi
git -C "$runtime/source" sparse-checkout set whisper
"$runtime/venv/bin/python" -m pip install "$runtime/source/whisper"
git -C "$runtime/source" rev-parse HEAD > "$runtime/source-commit.txt"
"$runtime/venv/bin/python" -m pip freeze > "$runtime/installed-packages.txt"
"$runtime/venv/bin/python" -c 'import mlx.core as mx; import mlx_whisper; print("MLX device:", mx.default_device())'
echo "Runtime ready: $runtime"
echo "Model weights will be downloaded on the first transcription with that model."
