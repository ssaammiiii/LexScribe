import os
import json
from openai import AzureOpenAI
from dotenv import load_dotenv
from infrastructure import get_raw_transcription

load_dotenv()

client = AzureOpenAI(
    api_key = os.getenv("AZURE_OPENAI_API_KEY"),
    api_version= "2025-01-01-preview",
    azure_endpoint= os.getenv("AZURE_OPENAI_ENDPOINT")    
)
deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")

# --- HELPER 1: CHUNKING ---
def chunk_text(text, max_length=12000):
    lines = text.split('\n')
    chunks = []
    current_chunk = ""
    for line in lines:
        if len(current_chunk) + len(line) < max_length:
            current_chunk += line + "\n"
        else:
            chunks.append(current_chunk)
            current_chunk = line + "\n"
            
    if current_chunk:
        chunks.append(current_chunk)
    return chunks

# --- HELPER 2: ANALYZE SINGLE CHUNK ---
def analyze_chunks(chunked_text, previous_context):
    system_prompt = f"""
    You are a legal-domain transcription analysis assistant.
    
    CRITICAL CONTEXT FROM PREVIOUS PART: "{previous_context}"
    
    Tasks:
    1. DIARIZATION: Assign utterances to "Client", "Lawyer 1", "Lawyer 2", etc.
    2. TRANSCRIPT STRUCTURING: List of {{"speaker": "...", "text": "..."}}
    3. SUMMARY: Concise summary of this chunk.
    4. ACTION ITEMS: tasks/decisions.
    5. LAST SPEAKER: Identify the very last speaker role.

    OUTPUT JSON ONLY:
    {{
      "transcript": [ 
        {{
          "speaker": "Client | Lawyer 1 | Lawyer 2 | Unknown",
          "text": "<text>"
        }} 
      ],
      "summary": "<summary>",
      "action_items": ["<action item 1>", "<action item 2>"],
      "last_speaker_role": "Client | Lawyer 1 | Lawyer 2"
    }}
    """
    
    response = client.chat.completions.create(
        model=deployment,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Chunk:\n\n{chunked_text}"}
        ],
        response_format={"type": "json_object"},
        temperature=0.2
    )
    return json.loads(response.choices[0].message.content)

# --- HELPER 3: POOLING RESULTS (With Keywords & Detailed Actions) ---
def pooling_chunks(all_summaries, all_actions):
    input_data = f""" 
        CHUNKED SUMMARIES : {json.dumps(all_summaries)}
        ALL ACTION ITEMS : {json.dumps(all_actions)}
    """
    prompt = """
    You are a Senior Legal Partner.
    
    Tasks:
    1. Merge summaries into one Executive Summary.
    2. Deduplicate and refine Action Items into a detailed checklist.
       - Each item must have an ID, Text, Assigned To, and Completed status.
    3. Extract 3-5 high-value "Keywords" (e.g., "Contract Review", "Liability").
    
    Output JSON ONLY:
    {
      "final_summary": "<merged executive summary>",
      "keywords": ["Tag1", "Tag2"],
      "final_action_items": [
          {
            "id": "1",
            "text": "Draft the NDA clause...",
            "assigned_to": "Lawyer 1",
            "completed": false
          }
      ]
    }
    """
    response = client.chat.completions.create(
        model=deployment,
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": input_data},   
        ],
        response_format={"type": "json_object"}        
    )
    return json.loads(response.choices[0].message.content)

# ======================================================
#  THE SHARED BRAIN
# ======================================================
def generate_legal_report(raw_text):
    """
    PURE LOGIC: Takes text string -> Returns Dict.
    Used by BOTH Local Script and Azure Function.
    """
    chunks = chunk_text(raw_text)
    print(f'Processing {len(chunks)} chunks...')
    
    full_transcript = []
    chunk_summaries = []
    chunk_actions = []
    
    current_context = "Start of meeting. Speakers are unknown."

    for i, chunk in enumerate(chunks):
        try:
            # Analyze
            result = analyze_chunks(chunk, current_context)
            
            # Aggregate
            full_transcript.extend(result.get("transcript", []))
            chunk_summaries.append(result.get("summary", ""))
            chunk_actions.extend(result.get("action_items", []))
            
            # Update Context
            last_role = result.get("last_speaker_role", "Unknown")
            current_context = f"Previous chunk ended. Last speaker was {last_role}."

        except Exception as e:
            print(f"Error in chunk {i}: {e}")

    # 2. Final Pooling
    final_report = pooling_chunks(chunk_summaries, chunk_actions)
    
    
    # A. Add Timestamp (Hardcoded as requested)
    for entry in full_transcript:
        entry["timestamp"] = "00:00"

    # B. Calculate Unique Speaker Count (Python is better at math than LLMs)
    unique_speakers = set()
    for entry in full_transcript:
        if entry.get("speaker"):
            unique_speakers.add(entry["speaker"])
    speaker_count = len(unique_speakers)

    # 4. Build Final Output
    final_output = {
        "transcript": full_transcript,
        "summary": final_report.get("final_summary"),
        "action_items": final_report.get("final_action_items"),
        "keywords": final_report.get("keywords"),
        "speaker_count": speaker_count  
    }
    
    return final_output  

# ======================================================
#  LOCAL TEST WRAPPER
# ======================================================
def fetching_transcript(transcript_file_path):
    print(f"Reading transcript from: {transcript_file_path}")
    
    try:
        with open(transcript_file_path, "r", encoding="utf-8") as f:
            raw_text = f.read()
    except FileNotFoundError:
        print(" File not found.")
        return

    if not raw_text:
        return

    final_output = generate_legal_report(raw_text)
    
    with open("LEGAL_RESULT.json", "w", encoding="utf-8") as f:
        json.dump(final_output, f, indent=2, ensure_ascii=False) 
        
    print("DONE. Saved to LEGAL_RESULT.json")

if __name__ == "__main__":
    target = "output.txt"
    if os.path.exists(target):
        fetching_transcript(target)