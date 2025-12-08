import os
import json
from openai import AzureOpenAI
from dotenv import load_dotenv
from infrastructure import get_raw_transcription
load_dotenv()

client = AzureOpenAI(
    api_key = os.getenv("AZURE_OPENAI_API_KEY"),
    api_version= os.getenv("AZURE_OPENAI_API_VERSION"),
    azure_endpoint= os.getenv("AZURE_OPENAI_ENDPOINT")    
)
deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")

def chunk_text(text,max_length = 12000):
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

# LOGIC FIX 1: Added 'previous_context' argument
def analyze_chunks(chunked_text, previous_context):
    system_prompt = f"""
    You are a legal-domain transcription analysis assistant.
    
    CRITICAL CONTEXT FROM PREVIOUS PART: "{previous_context}"
    (Use this to know who was speaking last. If the previous part ended with the Lawyer asking a question, the Client is likely answering now).

    You will receive a raw transcript that  has NO speaker labels.

   Your tasks:

    1. DIARIZATION (MULTI-LAWYER SUPPORT)
       - Assign each utterance to: "Client", "Lawyer 1", "Lawyer 2", etc., or "Unknown".
       - Distinguish between lawyers based on:
         * Introductions (e.g., "I am Mr. Smith").
         * Opposing viewpoints (Defense vs. Prosecution).
         * Seniority/Role (Partner vs. Associate).
       - Keep specific identities consistent (e.g., if Lawyer 1 is "Sarah", keep her as Lawyer 1).
       
    2. TRANSCRIPT STRUCTURING
       - Split the transcript into entries.
       - Each entry must contain:
           "speaker"
           "text"

    3. SUMMARY
       - Provide a clear, concise summary of the meeting.

    4. ACTION ITEMS
       - Extract all tasks, responsibilities, decisions, or follow-ups mentioned.
       
    5. LAST SPEAKER (Internal Logic)
       - Identify who the very last speaker was in this chunk.

    OUTPUT FORMAT (MANDATORY)
    You must always respond ONLY with this JSON structure:

    {{
      "transcript": [
        {{
          "speaker": "Client | Lawyer 1 | Lawyer 2 | Unknown",
          "text": "<text>"
        }}
      ],
      "summary": "<summary>",
      "action_items": [
        "<action item 1>",
        "<action item 2>"
      ],
      "last_speaker_role": "Client | Lawyer 1 | Lawyer 2"
    }}


    RULES:
    - Never output text outside JSON.
    - Never hallucinate  content.
    - Never assume speakers without contextual support.
    - Keep speaker labeling consistent throughout.
    - If the input is empty or unusable, output empty JSON fields in the same structure.
    """
    
    response = client.chat.completions.create(
        model = deployment,
        messages = [
            
            {"role": "system", "content": system_prompt},
            {"role" : "user" , "content" : f"Here is the transcript chunk:\n\n{chunked_text}\n\nPlease analyze it as per the instructions."}
        ],
        response_format= {"type": "json_object"},
        temperature=0.2
    )
    
    return json.loads(response.choices[0].message.content)


def pooling_chunks(all_summaries,all_actions):
    """
    combines the chunked summaries and action item with the help of LLM
    """

    input_data = f""" 
    
        CHUNKED SUMMARIES : {json.dumps(all_summaries)}
        ALL ACTION ITEMS : {json.dumps(all_actions)}

    """
    prompt = """
    
    
    You are a Senior Legal Partner responsible for producing a final, high-level deliverable.

            Input will contain:
            - Multiple chunk summaries
            - Multiple chunk action-item lists

            Your tasks:
            1. Merge all segment summaries into a single, cohesive Executive Summary.
            - Preserve all important details.
            - Ensure logical flow and no contradictions.
            - Eliminate repetition.

            2. Combine all action items into one clean, deduplicated checklist.
            - Remove duplicates.
            - Merge similar items.
            - Rewrite items to be clear, actionable, and specific.

            Output ONLY the following JSON:

            {
            "final_summary": "<merged executive summary>",
            "final_action_items": [
                "<item 1>",
                "<item 2>",
                "<item 3>"
            ]
            }
            
    """
    response = client.chat.completions.create(
        
        model = deployment,
        messages= [
            { "role" : "system", "content" : prompt},
             { "role" : "user", "content" :   input_data},   
        ],
        response_format= { "type" : "json_object"}        
    )
    return json.loads(response.choices[0].message.content)

def fetching_transcript(audio_file_path):
    print(f"fetching the raw transcript")
    raw_text = get_raw_transcription(audio_file_path)
    if not raw_text:
        print("no transcript was generated")
        return
     #chunking
    chunks = chunk_text(raw_text)
    print(f'processing {len(chunks)} chunks of the Transcript')
    
    full_transcript = []
    chunk_summaries =[]
    chunk_actions = []
    
    # LOGIC FIX 2: Initialize Context
    current_context = "Start of meeting. Speakers are unknown."

    for i,chunk in enumerate(chunks):
        print(f'processing {i+1}/{len(chunks)}')
        try:
            # LOGIC FIX 3: Pass context to the function
            result = analyze_chunks(chunk, current_context)
            
            full_transcript.extend(result.get("transcript", []))
            chunk_summaries.append(result.get("summary", ""))
            chunk_actions.extend(result.get("action_items", []))
            
            # LOGIC FIX 4: Update context for the next loop
            last_role = result.get("last_speaker_role", "Unknown")
            current_context = f"Previous chunk ended. The last speaker was {last_role}."

        except Exception as e :
            print(f"Error in chunk {i}: {e}")
            
    #final report
    final_report = pooling_chunks(chunk_summaries,chunk_actions)
    
    #final output
    final_output = {
        
        "transcript": full_transcript,
        "summary": final_report.get("final_summary"),
        "action_items": final_report.get("final_action_items")  
    }
    
    # Save the file
    with open("LEGAL_RESULT.json", "w") as f:
        json.dump(final_output, f, indent=2)
    print("DONE. Saved to LEGAL_RESULT.json")

if __name__ == "__main__":
    target = "output.mp3"
    if os.path.exists(target):
        fetching_transcript(target)
    else:
        print("output.mp3 not found")