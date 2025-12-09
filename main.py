from infrastructure import video_to_audio, get_raw_transcription
from intelligence import fetching_transcript
import os

def main():
    #filenames
    video_source = "sample.mp4"
    audio_target = "output.mp3"
    text_target = "output.txt"

    # 2. Convert Video -> Audio
    if not os.path.exists(audio_target):
        video_to_audio(video_source, audio_target)
    
    # 3. Transcribe Audio -> Text File ,if transcript not existing
    if not os.path.exists(text_target):
        print("🎧 Generating transcript file...")
        get_raw_transcription(audio_target, text_target)
    
    # 4. Analyze Text File -> JSON Report
    if os.path.exists(text_target):
        print("🧠 Starting Intelligence analysis...")
        fetching_transcript(text_target)
    else:
        print(" Error: Transcript file was not created.")

if __name__ == "__main__":
    main()