from flask import Flask, request, jsonify, send_file
from main import perform_action, ask_llm, say
import tempfile
import pyttsx3
import os

app = Flask(__name__)

# Text command endpoint
def text_to_speech(text):
    engine = pyttsx3.init()
    fd, path = tempfile.mkstemp(suffix='.mp3')
    engine.save_to_file(text, path)
    engine.runAndWait()
    return path

@app.route('/api/command', methods=['POST'])
def handle_command():
    data = request.json
    command = data.get('command', '')
    if not command:
        return jsonify({'error': 'No command provided'}), 400
    action_response = perform_action(command)
    if action_response:
        response_text = action_response
    else:
        response_text = ask_llm(command)
    # Generate TTS audio
    audio_path = text_to_speech(response_text)
    return jsonify({'response': response_text, 'audio': '/api/audio?path=' + audio_path})

@app.route('/api/audio')
def serve_audio():
    path = request.args.get('path')
    if not path or not os.path.exists(path):
        return '', 404
    return send_file(path, mimetype='audio/mpeg')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
