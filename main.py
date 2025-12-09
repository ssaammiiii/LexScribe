from infrastructure import video_to_audio, get_raw_transcription


def main():
    print("Hello from lexscribe!")

    print("Transcribing the audio...")
    get_raw_transcription("audio.mp3")


if __name__ == "__main__":
    main()
