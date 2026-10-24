import os
import shutil
import tempfile

import yt_dlp
from pydub import AudioSegment


def _ensure_ffmpeg() -> None:
    """Make sure ffmpeg/ffprobe are reachable on PATH.

    System installs (local dev, VPS, Docker) are preferred. On hosts without
    them — e.g. Streamlit Community Cloud, where the apt.txt step may not have
    installed packages — fall back to the static-ffmpeg pip package, which
    bundles prebuilt binaries and adds them to PATH on first use.
    """
    if shutil.which("ffmpeg") and shutil.which("ffprobe"):
        return
    try:
        import static_ffmpeg

        static_ffmpeg.add_paths()
    except Exception as exc:
        raise RuntimeError(
            "ffmpeg/ffprobe not found. Install FFmpeg on the host "
            "(https://ffmpeg.org/download.html) or add `static-ffmpeg` to requirements."
        ) from exc


def download_youtube_audio(url: str, out_dir: str) -> str:
    """Download only the audio of ONE video (never a playlist) into out_dir."""
    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": os.path.join(out_dir, "%(id)s.%(ext)s"),
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "postprocessors": [
            {"key": "FFmpegExtractAudio", "preferredcodec": "wav"}
        ],
        "postprocessor_args": {"extractaudio": ["-ar", "16000", "-ac", "1"]},
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        return os.path.splitext(ydl.prepare_filename(info))[0] + ".wav"


def convert_to_wav(input_path: str, out_dir: str) -> str:
    output_path = os.path.join(out_dir, "converted.wav")
    audio = AudioSegment.from_file(input_path)
    audio = audio.set_channels(1).set_frame_rate(16000)
    audio.export(output_path, format="wav")
    return output_path


def chunk_audio(wav_path: str, chunk_minutes: int = 10) -> list:
    audio = AudioSegment.from_wav(wav_path)
    chunk_ms = chunk_minutes * 60 * 1000
    base = os.path.splitext(wav_path)[0]

    chunks = []
    for i, start in enumerate(range(0, len(audio), chunk_ms)):
        chunk = audio[start: start + chunk_ms]
        chunk_path = f"{base}_chunk_{i}.wav"
        chunk.export(chunk_path, format="wav")
        chunks.append(chunk_path)
    return chunks


def process_input(source: str) -> list:
    _ensure_ffmpeg()
    work_dir = tempfile.mkdtemp(prefix="video_assistant_")
    try:
        if source.startswith(("http://", "https://")):
            print("Detected YouTube URL. Downloading audio...")
            wav_path = download_youtube_audio(source, work_dir)
        else:
            print("Detected local file. Converting to WAV...")
            wav_path = convert_to_wav(source, work_dir)

        print("Chunking audio...")
        chunks = chunk_audio(wav_path)
        os.remove(wav_path)  # chunks are copies, drop the full file now
        print(f"Audio ready - {len(chunks)} chunk(s) created.")
        return chunks
    except Exception:
        shutil.rmtree(work_dir, ignore_errors=True)
        raise


def cleanup_files(chunks: list) -> None:
    for work_dir in {os.path.dirname(c) for c in chunks}:
        shutil.rmtree(work_dir, ignore_errors=True)


