
import os
import subprocess
import static_ffmpeg 
from dotenv import load_dotenv
from openai import AzureOpenAI
from pydub import AudioSegment 

# Load env vars once here, so Coder B doesn't have to worry about it
load_dotenv()
static_ffmpeg.add_paths()

def get_azure_client():

    return AzureOpenAI(
        api_key=os.getenv("AZURE_OPENAI_KEY"),
        api_version= "2025-01-01-preview",
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
        )

# convert video to audio 
def video_to_audio(input_file, output_file):
    ffmpeg_cmd = [
        "ffmpeg",
        "-i", input_file,
        "-vn",
        "-acodec", "libmp3lame",
        "-ab", "192k",
        "-ar", "44100",
        "-y",
        output_file
    
    ] 
    video_path = "sample_video.mp4"
    print(f"🎬 Extracting audio from {video_path}...")
    try:
        subprocess.run(ffmpeg_cmd, check=True)
        print(f"Conversion successful: {output_file}")
    except subprocess.CalledProcessError as e:
        print(f"Error during conversion: {e}")

    
def get_raw_transcription(audio_file, output_path="transcription_output.txt"):
    
    deployment_name = "whisper"

    """
    Transcribes audio. If >25MB, splits it into chunks.
    Returns CLEAN TEXT (No timestamps).
    """
    client = get_azure_client()
    
    # Check if file exists first
    if not os.path.exists(audio_file):
        print(f" Error: File not found at {audio_file}")
        return ""

    # Check size
    file_size_mb = os.path.getsize(audio_file) / (1024 * 1024)
    print(f" File size: {file_size_mb:.2f} MB")

    # --- CASE 1: File is Big (> 25MB) ---
    if file_size_mb > 25:
        print(" File is too large. Splitting...")
        audio = AudioSegment.from_mp3(audio_file)
        
        chunk_length_ms = 10 * 60 * 1000 # 10 minutes
        chunks = [audio[i:i+chunk_length_ms] for i in range(0, len(audio), chunk_length_ms)]
        
        full_transcript = []
        print(f" Splitting into {len(chunks)} chunks.")
        
        for i, chunk in enumerate(chunks):
            chunk_filename = f"temp_chunk_{i}.mp3"
            chunk.export(chunk_filename, format="mp3", bitrate="192k")
            
            print(f"   - Transcribing chunk {i+1}/{len(chunks)}...")
            
            with open(chunk_filename, "rb") as audio_file:
                # We use 'json' format now to get simple clean text
                response = client.audio.transcriptions.create(
                    model=deployment_name, 
                    file=audio_file,
                    response_format="json" 
                )
                full_transcript.append(response.text)
            
            os.remove(chunk_filename)
            
        final_text =  " ".join(full_transcript)

    # --- CASE 2: Small File ---
    else:
        print(" File is within limits. Sending directly...")
        with open(audio_file, "rb") as audio_file:
            response = client.audio.transcriptions.create(
                model=deployment_name, 
                file=audio_file,
                response_format="json"
            )
        final_text = response.text

    try:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(final_text)
        print(f"✅ Transcription successfully saved to: {output_path}")
    except Exception as e:
        print(f"⚠️ Error saving transcription to file: {e}")
        
    return final_text
