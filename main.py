import os
import uuid
import speech_recognition as sr
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse
from transformers import GPT2LMHeadModel, GPT2Tokenizer
from gtts import gTTS
from pydantic import BaseModel
import torch
from pymongo import MongoClient
from datetime import datetime

# Initialize FastAPI App
app = FastAPI()

# Enable CORS for frontend connection
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# MongoDB Connection
MONGO_URI = "mongodb+srv://riyasinhapat1:WfQESWFGt2E9u8RQ@cluster0.yvrcl.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
client = MongoClient(MONGO_URI)
db = client.get_database("voice-assistant")
interactions_collection = db.get_collection("interaction")

# Load GPT-2 Model & Tokenizer
model_name = "gpt2"
tokenizer = GPT2Tokenizer.from_pretrained(model_name)
model = GPT2LMHeadModel.from_pretrained(model_name)

# Manually set pad token if missing
if tokenizer.pad_token is None:
    tokenizer.pad_token = tokenizer.eos_token

# Text-to-Speech Function
def text_to_speech(response_text):
    tts = gTTS(text=response_text, lang="en")
    os.makedirs("static", exist_ok=True)
    audio_filename = f"static/response_{uuid.uuid4().hex}.mp3"
    tts.save(audio_filename)
    return audio_filename

# Function to Generate Response from GPT-2
def generate_response(prompt):
    input_ids = tokenizer.encode(prompt, return_tensors="pt")
    attention_mask = torch.ones_like(input_ids)

    output = model.generate(
        input_ids,
        attention_mask=attention_mask,
        max_length=100,
        num_return_sequences=1,
        temperature=0.7,
        top_p=0.8,
        repetition_penalty=1.3,
        pad_token_id=tokenizer.eos_token_id,
    )

    response_text = tokenizer.decode(output[0], skip_special_tokens=True)
    return response_text.strip()

# Request Model for Speech Data
class VoiceRequest(BaseModel):
    text: str

# Home Route - Serves the HTML Page
@app.get("/", response_class=HTMLResponse)
async def home():
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Voice Assistant</title>
        <style>
            body { font-family: Arial, sans-serif; text-align: center; padding: 50px; background-color: #f4f4f4; }
            h1 { color: #333; }
            .mic-button { background-color: #007bff; border: none; border-radius: 50%; width: 80px; height: 80px; cursor: pointer; display: flex; align-items: center; justify-content: center; margin: 20px auto; }
            .mic-icon { width: 40px; height: 40px; }
        </style>
    </head>
    <body>
        <h1>Welcome! How can I help you?</h1>
        <button class="mic-button" id="micButton">
            <img src="https://cdn-icons-png.flaticon.com/512/25/25682.png" class="mic-icon">
        </button>
        <p id="result"></p>
        <p> Please wait 10 sec for response</p>
        <audio id="audioPlayer" controls style="display: none;"></audio>

        <script>
            document.getElementById("micButton").addEventListener("click", startListening);
            function startListening() {
                if (!("webkitSpeechRecognition" in window || "SpeechRecognition" in window)) {
                    alert("Speech recognition is not supported in your browser.");
                    return;
                }
                const recognition = new (window.SpeechRecognition || window.webkitSpeechRecognition)();
                recognition.lang = "en-US";
                recognition.start();

                recognition.onresult = function(event) {
                    let userText = event.results[0][0].transcript.trim();
                    if (!userText) {
                        document.getElementById("result").innerText = "No speech detected.";
                        return;
                    }
                    document.getElementById("result").innerText = "You said: " + userText;
                    fetch("/voice-assistant", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ text: userText })
                    })
                    .then(response => response.json())
                    .then(data => {
                        document.getElementById("result").innerText = "Bot: " + data.response;
                        if (data.audio_url) {
                            let audio = document.getElementById("audioPlayer");
                            audio.src = data.audio_url;
                            audio.style.display = "block";
                            audio.play();
                        }
                    })
                    .catch(error => console.error("Error fetching response:", error));
                };
                recognition.onerror = function(event) {
                    console.error("Speech recognition error:", event.error);
                    document.getElementById("result").innerText = "Error in speech recognition.";
                };
            }
        </script>
    </body>
    </html>
    """

# API to Handle Voice Assistant Interaction
@app.post("/voice-assistant")
async def voice_assistant(request: VoiceRequest):
    user_text = request.text.strip()
    print(f"User said: {user_text}")
    
    if not user_text:
        return JSONResponse(content={"response": "I could not understand that.", "audio_url": None})
    
    response = generate_response(user_text)
    audio_response_file = text_to_speech(response)

    # Store interaction in MongoDB
    interaction = {
        "user_text": user_text,
        "bot_response": response,
        "timestamp": datetime.utcnow()
    }
    interactions_collection.insert_one(interaction)  # Fixed incorrect variable

    return JSONResponse(content={"response": response, "audio_url": f"/{audio_response_file}"})

# Serve Audio Files
@app.get("/static/{filename}")
async def serve_audio(filename: str):
    file_path = os.path.join("static", filename)
    if os.path.exists(file_path):
        return FileResponse(file_path, media_type="audio/mpeg")
    return JSONResponse(content={"error": "Audio file not found"}, status_code=404)