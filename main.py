from infrastructure import video_to_audio
from intelligence import fetching_transcript
import os

def main():
    video = "sample.mp4"
    video_to_audio(video,"output.mp3")
    target = "output.mp3"
    if os.path.exists(target):
        fetching_transcript(target)
    else:
        print("output.mp3 not found")


if __name__ == "__main__":
    main()
