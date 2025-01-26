import subprocess
import json
import io
from datetime import datetime
import logging
import typer
from pydub import AudioSegment
from pydub.silence import detect_silence

app = typer.Typer()

def get_audio_duration(filename):
    """Get duration of audio file using ffprobe."""
    cmd = [
        'ffprobe', '-i', filename,
        '-show_entries', 'format=duration',
        '-v', 'quiet',
        '-of', 'json'
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return float(json.loads(result.stdout)['format']['duration']) * 1000  # convert to ms

def extract_chunk(filename, start_ms, duration_ms):
    """Extract a chunk of audio using ffmpeg."""
    cmd = [
        'ffmpeg',
        '-ss', str(start_ms/1000),  # start time in seconds
        '-t', str(duration_ms/1000),  # duration in seconds
        '-i', filename,
        '-f', 'wav',
        '-acodec', 'pcm_s16le',
        '-ar', '44100',
        '-ac', '2',
        '-'  # output to pipe
    ]
    process = subprocess.run(cmd, capture_output=True)
    return AudioSegment.from_wav(io.BytesIO(process.stdout))

@app.command()
def generate_chapters(
    input_file: str = typer.Argument(..., help="Input audio file path"),
    output_file: str = typer.Option("metadata.txt", help="Output metadata file path"),
    min_silence_len: int = typer.Option(3000, help="Minimum silence length in milliseconds"),
    silence_thresh: int = typer.Option(-30, help="Silence threshold in dB"),
    chunk_size: int = typer.Option(600, help="Chunk size in seconds"),
):
    """Generate chapter metadata from silence detection in audio file."""
    logging.basicConfig(level=logging.INFO)
    logging.info(f"Generating chapters for audio file: {input_file}")

    # Get total duration
    total_length = get_audio_duration(input_file)
    chunk_size_ms = chunk_size * 1000

    logging.info(f"Total audio length: {total_length}ms")

    silences = []
    current_offset = 0


    while current_offset < total_length:
        start_time = datetime.now()
        # Extract the current chunk
        chunk = extract_chunk(input_file, current_offset, chunk_size_ms)
        # Detect silences in the current chunk
        chunk_silences = detect_silence(chunk, min_silence_len=min_silence_len, silence_thresh=silence_thresh)
        end_time = datetime.now()
        logging.info(f"Processed chunk at offset {current_offset}ms ({end_time - start_time})")

        # Adjust silence times to account for the chunk offset
        adjusted_silences = [(start + current_offset, end + current_offset) for start, end in chunk_silences]
        silences.extend(adjusted_silences)
        # Move to the next chunk
        current_offset += chunk_size_ms

    # Write metadata
    with open(output_file, "w") as meta_file:
        meta_file.write(";FFMETADATA1\n")
        for i, (start, end) in enumerate(silences):
            meta_file.write(f"[CHAPTER]\n")
            meta_file.write(f"TIMEBASE=1/1000\n")
            meta_file.write(f"START={start}\n")
            meta_file.write(f"END={end}\n")
            meta_file.write(f"title=Tag {i + 1}\n")

if __name__ == "__main__":
    app()
