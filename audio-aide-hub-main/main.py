import os
import webbrowser
import datetime
import random
import requests
import speech_recognition as sr
import pyttsx3
import sys
import google.generativeai as genai
from collections import deque
import urllib.parse
import time
import numpy as np
from datetime import datetime
from flask import Flask, request, jsonify
import base64
import tempfile

# System prompt for more Jarvis-like responses
SYSTEM_PROMPT = """You are JARVIS (Just A Rather Very Intelligent System), Tony Stark's AI assistant.
Respond in a formal, respectful manner, always addressing the user as 'sir'.
Be concise, intelligent, and slightly witty - similar to the JARVIS from Iron Man.
Focus on being helpful while maintaining a professional, butler-like demeanor."""


client = genai.GenerativeModel('gemini-1.5-flash')
# If you need to set API key:
genai.configure(api_key="AIzaSyCwR7CPvBQuUokwewv4fJM5fS3hY8HnCYg")


WEATHER_API_KEY = "8448164ea5f5b95842dfdfe5ebc88755"


CHAT_HISTORY = deque(maxlen=20)

engine = pyttsx3.init()

engine.setProperty('rate', 200)  # Increased from 180 to 200
engine.setProperty('volume', 0.9)

AMBIENT_DURATION = 3  # seconds to determine ambient noise
SILENCE_THRESHOLD = 1.5  # multiplier above ambient to detect speech
IDLE_TIMEOUT = 60  # seconds before idle message
LAST_INTERACTION = datetime.now()

app = Flask(__name__)

def say(text):
    print("JARVIS: {}".format(text))
    engine.say(text)
    engine.runAndWait()

def take_command():
    global LAST_INTERACTION
    recognizer = sr.Recognizer()

    with sr.Microphone() as source:
        print("JARVIS: Calibrating for ambient noise...")
        recognizer.adjust_for_ambient_noise(source, duration=AMBIENT_DURATION)
        ambient_energy = recognizer.energy_threshold
        recognizer.energy_threshold = ambient_energy * SILENCE_THRESHOLD
        
        while True:
            try:
                idle_time = (datetime.now() - LAST_INTERACTION).seconds
                if idle_time >= IDLE_TIMEOUT:
                    random_idle_message = random.choice([
                        "Still at your service, sir. Just maintaining systems while you think.",
                        "Taking the opportunity to optimize my circuits while you contemplate.",
                        "Standing by, sir. The workshop is rather quiet.",
                        "All systems nominal. Awaiting your next brilliant idea.",
                    ])
                    say(random_idle_message)
                    LAST_INTERACTION = datetime.now()
                
                print("JARVIS: Listening, sir...")
                audio = recognizer.listen(source, timeout=5, phrase_time_limit=10)
                
                LAST_INTERACTION = datetime.now()
                
                query = recognizer.recognize_google(audio, language="en-in")
                print("You: {}".format(query))
                return query.lower()
                
            except sr.WaitTimeoutError:
                continue
            except sr.RequestError:
                say("I apologize sir, but I'm having trouble connecting to my speech recognition servers.")
                return ""
            except sr.UnknownValueError:
                energy = np.mean([abs(x) for x in audio.get_raw_data()])
                if energy > ambient_energy * SILENCE_THRESHOLD:
                    say("I apologize sir, but I couldn't quite catch that. Could you please repeat?")
                return ""
            except Exception as e:
                print("Error in speech recognition: {}".format(str(e)))
                return ""

def get_weather(city):
    base_url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={WEATHER_API_KEY}&units=metric"
    response = requests.get(base_url)
    data = response.json()
    if data["cod"] != "404":
        temp = data["main"]["temp"]
        description = data["weather"][0]["description"]
        return f"The temperature in {city} is {temp}°C with {description}."
    else:
        return "City not found."

def tell_joke():
    jokes = [
        "Why don't scientists trust atoms? Because they make up everything!",
        "Why did the computer go to the doctor? Because it had a virus!",
        "What do you call fake spaghetti? An impasta!"
    ]
    return random.choice(jokes)

def extract_url_from_llm(command):
    # Add chat context to the prompt
    chat_context = "\n".join(["Previous: {}".format(chat) for chat in CHAT_HISTORY])
    prompt = f"""Context of recent conversation:
    {chat_context}
    
    Current command: '{command}'
    If it's about playing music/songs, generate a YouTube music search URL.
    If it's about opening a website, extract the most appropriate URL.
    If it's not about websites/music, return 'not_a_website'.
    
    For music commands, format: 'https://www.youtube.com/results?search_query=SEARCH_TERM&feature=music'
    For websites, format: 'https://website.com'"""
    try:
        response = client.generate_content(prompt, generation_config={"temperature": 0.2})
        url = response.text.strip().lower()
        
        # Handle music/song requests
        if "play" in command.lower() and ("song" in command.lower() or "music" in command.lower()):
            search_term = command.replace("play", "").replace("song", "").replace("music", "").strip()
            encoded_search = urllib.parse.quote(search_term)
            return "https://www.youtube.com/results?search_query={}&feature=music".format(encoded_search)
            
        # Handle regular website URLs
        if url.startswith('http'):
            return url
        elif "twitter" in command.lower():
            return "https://twitter.com"
        elif "youtube" in command.lower():
            return "https://youtube.com"
        elif "facebook" in command.lower():
            return "https://facebook.com"
        elif "instagram" in command.lower():
            return "https://instagram.com"
        else:
            search_term = command.replace("open", "").strip()
            return "https://www.google.com/search?q={}".format(search_term)
    except Exception as e:
        print("Error in URL extraction: {}".format(str(e)))
        return None

def perform_action(command):
    # Add command to chat history
    CHAT_HISTORY.append(command)
    
    command = command.lower()
    
    # Handle exit commands more naturally
    if any(word in command for word in ["stop", "exit", "goodbye", "bye", "shut down"]):
        say("Shutting down systems, sir. Have a wonderful day.")
        exit()

    # Handle music/song requests
    if "play" in command and ("song" in command or "music" in command):
        url = extract_url_from_llm(command)
        if url:
            webbrowser.open(url)
            return "Playing the requested music for you, sir."

    # Handle search commands
    if any(word in command for word in ["search", "search for", "look up", "google"]):
        search_query = command
        for term in ["search", "search for", "look up", "google"]:
            search_query = search_query.replace(term, "").strip()
        
        encoded_query = urllib.parse.quote(search_query)
        search_url = "https://www.google.com/search?q={}".format(encoded_query)
        webbrowser.open(search_url)
        return "Searching for '{}' for you, sir.".format(search_query)

    # Smart website opening using LLM
    if "open" in command:
        # First check for local applications
        app_map = {
            "facetime": "/System/Applications/FaceTime.app",
            "safari": "/Applications/Safari.app",
            "music": "/System/Applications/Music.app",
            "photos": "/System/Applications/Photos.app",
            "whatsapp": "/Applications/WhatsApp.app",
            "visual studio code": "/Applications/Visual Studio Code.app",
            "calculator": "/System/Applications/Calculator.app",
        }

        for app in app_map:
            if app in command:
                os.system(f"open {app_map[app]}")
                return f"Opening {app.capitalize()} for you, sir."

        # If not a local app, try to interpret as a website
        url = extract_url_from_llm(command)
        if url:
            webbrowser.open(url)
            return f"Opening the requested website for you, sir."

    # Handle other commands...
    elif "weather in" in command:
        city = command.split("in")[-1].strip()
        return get_weather(city)

    elif "time" in command:
        time = datetime.datetime.now().strftime("%I:%M %p")
        return f"The time is {time}, sir."

    elif "joke" in command:
        return f"Here's one for you, sir: {tell_joke()}"

    return None

def ask_llm(prompt):
    try:
        # Include chat history in the context
        chat_context = "\n".join(["Previous: {}".format(chat) for chat in CHAT_HISTORY])
        full_prompt = f"""Recent conversation context:
        {chat_context}
        
        Current query: {prompt}"""
        response = client.generate_content(full_prompt, generation_config={"temperature": 0.7}, system_instruction=SYSTEM_PROMPT)
        # Add response to chat history
        CHAT_HISTORY.append("User: {}".format(prompt))
        CHAT_HISTORY.append("JARVIS: {}".format(response.text))
        return response.text
    except Exception as e:
        return f"I apologize sir, but I'm having trouble connecting to my neural networks at the moment. Error: {str(e)}"

def tts_to_base64(text):
    temp_fd, temp_path = tempfile.mkstemp(suffix='.mp3')
    os.close(temp_fd)
    tts_engine = pyttsx3.init()
    tts_engine.save_to_file(text, temp_path)
    tts_engine.runAndWait()
    with open(temp_path, 'rb') as f:
        audio_b64 = base64.b64encode(f.read()).decode('utf-8')
    os.remove(temp_path)
    return audio_b64

@app.route('/api/command', methods=['POST'])
def api_command():
    data = request.get_json()
    command = data.get('command', '')
    if not command:
        return jsonify({'error': 'No command provided'}), 400
    action_response = perform_action(command)
    if action_response:
        response_text = action_response
    else:
        response_text = ask_llm(command)
    audio_b64 = tts_to_base64(response_text)
    return jsonify({
        'response': response_text,
        'audio_base64': audio_b64
    })

# Modify the main loop to handle interruptions gracefully
def main():
    global LAST_INTERACTION
    
    # Initialize JARVIS
    say("JARVIS online. Calibrating systems for optimal performance, sir.")
    LAST_INTERACTION = datetime.now()
    
    try:
        while True:
            user_input = take_command()
            if user_input:
                action_response = perform_action(user_input)
                if action_response:
                    say(action_response)
                else:
                    llm_response = ask_llm(user_input)
                    say(llm_response)
            
            # Small sleep to prevent CPU overuse
            time.sleep(0.1)
            
    except KeyboardInterrupt:
        say("Shutting down gracefully, sir. It has been a pleasure serving you.")
        sys.exit(0)
    except Exception as e:
        say("I apologize sir, but I've encountered an unexpected error: {}".format(str(e)))
        sys.exit(1)

if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == 'api':
        app.run(host='0.0.0.0', port=5000, debug=True)
    else:
        main()

