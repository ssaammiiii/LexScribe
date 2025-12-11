import azure.functions as func
import logging
import os
import json
import tempfile
import requests
import shutil

from infrastructure import video_to_audio, get_raw_transcription
from intelligence import generate_legal_report

app = func.FunctionApp()

@app.route(route="Transcriber", auth_level=func.AuthLevel.ANONYMOUS)
def Transcriber(req: func.HttpRequest) -> func.HttpResponse:
    logging.info(' Received request to Transcriber function.')

    # 1. PARSE INPUT
    try:
        req_body = req.get_json()
        video_input = req_body.get('video_url')
    except ValueError:
        return func.HttpResponse("Invalid JSON.", status_code=400)

    if not video_input:
        return func.HttpResponse("Missing 'video_url'.", status_code=400)

    # 2. SETUP TEMP FILES
    temp_dir = tempfile.gettempdir()
    video_path = os.path.join(temp_dir, "temp_input.mp4")
    audio_path = os.path.join(temp_dir, "temp_audio.mp3")
    transcript_path = os.path.join(temp_dir, "temp_transcript.txt")
    
    try:
        # 3. ACQUIRE VIDEO
        if video_input.startswith("http"):
            # URL DOWNLOAD
            logging.info(f"Downloading from URL: {video_input}...")
            with requests.get(video_input, stream=True) as r:
                r.raise_for_status()
                with open(video_path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
        else:
            # LOCAL FILE LOGIC
            # If the user just sent relative path like "sample.mp4", get working directory and join the relative path to get full local path
            if not os.path.isabs(video_input):
                current_folder = os.getcwd()
                video_input = os.path.join(current_folder, video_input)
                #video_input =  C:\Users\LENOVO\OneDrive\Desktop\Transcriber\sample.mp4
            
            logging.info(f"Looking for file at: {video_input}")
            
            if os.path.exists(video_input):
                shutil.copy(video_input, video_path)
            else:
                # DEBUG INFO: List files in folder so we know what Python sees
                files_here = os.listdir(os.getcwd())
                error_msg = (f" File not found at: {video_input}. "
                             f"Current folder contains: {files_here}")
                logging.error(error_msg)
                return func.HttpResponse(error_msg, status_code=400)

        # 4. INFRASTRUCTURE
        logging.info("Converting to audio...")
        if os.path.exists(audio_path): os.remove(audio_path)
        video_to_audio(video_path, audio_path)
        
        logging.info("Transcribing...")
        get_raw_transcription(audio_path, transcript_path)
        
        if not os.path.exists(transcript_path):
             return func.HttpResponse("Transcription failed.", status_code=500)

        with open(transcript_path, "r", encoding="utf-8") as f:
            raw_text = f.read()

        # 5. INTELLIGENCE
        logging.info("Analyzing...")
        final_json = generate_legal_report(raw_text)

        return func.HttpResponse(
            json.dumps(final_json, ensure_ascii=False),
            mimetype="application/json",
            status_code=200
        )

    except Exception as e:
        logging.error(f"Error: {e}")
        return func.HttpResponse(f"Internal Error: {str(e)}", status_code=500)
    
    finally:
        if os.path.exists(video_path): os.remove(video_path)
        if os.path.exists(audio_path): os.remove(audio_path)
        if os.path.exists(transcript_path): os.remove(transcript_path)