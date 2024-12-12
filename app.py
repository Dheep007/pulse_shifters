from flask import Flask, jsonify, request, render_template, Blueprint, send_from_directory
from flask_cors import CORS
from google.cloud import vision
import io
import re
from flask_socketio import SocketIO, emit
from gtts import gTTS
from google.oauth2 import service_account
import mysql.connector
from playsound import playsound
from pydub import AudioSegment
import tempfile
import pygame
import time
import base64
import os
from PIL import Image
from io import BytesIO
import speech_recognition as sr
from threading import Thread,Lock


lock=Lock()

app = Flask(__name__)
CORS(app) 
socketio = SocketIO(app)

# Initialize the client with credentials
credentials = service_account.Credentials.from_service_account_file(
    r"/home/sinthanai/S_I_H/pulse-shifters-fcd3684c2dde.json"
)
client = vision.ImageAnnotatorClient(credentials=credentials)


UPLOAD_DIRECTORY_IMAGE = r"/home/sinthanai/S_I_H/canvas_images" 
if not os.path.exists(UPLOAD_DIRECTORY_IMAGE):
    os.makedirs(UPLOAD_DIRECTORY_IMAGE)

UPLOAD_DIRECTORY_AUDIO = r"/home/sinthanai/S_I_H/canvas_images_audios"
if not os.path.exists(UPLOAD_DIRECTORY_AUDIO):
    os.makedirs(UPLOAD_DIRECTORY_AUDIO)
 
IMAGE_DIRECTORY = r"/home/sinthanai/S_I_H/saved_images"
if not os.path.exists(IMAGE_DIRECTORY):
    os.makedirs(IMAGE_DIRECTORY)



# Initialize the database
conn = mysql.connector.connect(host='localhost', user='root', password='root', database='audio_file', autocommit=True, connection_timeout=60)
c = conn.cursor()

# Ensure the table exists
c.execute('''CREATE TABLE IF NOT EXISTS text_data
                 (id INT AUTO_INCREMENT PRIMARY KEY, filename TEXT, text TEXT, timestamp TEXT)''')

c.execute('''CREATE TABLE IF NOT EXISTS audio_data
                 (id INT AUTO_INCREMENT PRIMARY KEY, file_name TEXT, text TEXT, audio BLOB, timestamp TEXT)''')

c.execute('''CREATE TABLE IF NOT EXISTS canvas_images 
          (id INT  AUTO_INCREMENT PRIMARY KEY, image LONGBLOB,audio BLOB, filename TEXT, time TEXT)''')

c.execute('''CREATE TABLE IF NOT EXISTS words
          (id INT AUTO_INCREMENT PRIMARY KEY, word TEXT , min_x INT NOT NULL, min_y INT NOT NULL, max_x INT NOT NULL, max_y INT NOT NULL, image LONGBLOB) ''')


def extract_text_google_vision(image_path, language_hint= 'en'):
    
    # Load the image into memory
    with io.open(image_path, 'rb') as image_file:
        content = image_file.read()

    image = vision.Image(content=content)

    # Prepare the image context with language hint if provided
    image_context = {"language_hints": [language_hint]} if language_hint else None

    # Perform text detection
    response = client.text_detection(image=image, image_context=image_context)
    texts = response.text_annotations

    if response.error.message:
        raise Exception(f"Google Vision API error: {response.error.message}")

    # The first item in `texts` contains the full text detected
    if texts:
        return texts[0].description.strip()
    return "No text detected"


def recognize_speech(language='en-IN'):
    global recognized_text, listening, filename, timestamp

    try:
        with sr.Microphone(sample_rate=48000, chunk_size=2048) as source:
            recognizer.adjust_for_ambient_noise(source, duration=1)
            print("Listening...")
            
            while listening:
                try:
                    audio = recognizer.listen(source, timeout=None, phrase_time_limit=None)
                    text = recognizer.recognize_google(audio, language=language).lower()
                    recognized_text = text
                    timestamp_1 = time.strftime("%Y%m%d-%H%M%S")
                    timestamp = timestamp_1
                    filename_1 = f"STT_Text_{timestamp}"
                    filename = filename_1
                    print(f"Recognized Text: {text}")
                except sr.UnknownValueError:
                    print("Could not understand the audio.")
                except sr.RequestError as e:
                    print(f"Error with Google Speech Recognition service: {e}")
    except Exception as e:
        print(f"Error during speech recognition: {e}")
    finally:
        listening = False 


def sanitize_filename(filename):
    sanitized = re.sub(r'[\\/*?:"<>|]', '_', filename)  
    sanitized = sanitized.replace('\n', '_').replace('\r', '_')  
    return sanitized

def reconnect_to_db():
    global conn, c
    if not conn.is_connected():
        conn.reconnect(attempts=3, delay=5)
        c = conn.cursor()


# Global variables
listening = False
recognized_text =""
recognizer = sr.Recognizer()
filename = ""
timestamp = ""
extracted_text = ""


# Route to serve the HTML page
@app.route('/')
def index():
    return render_template('index.html')


def speak_mode(message):
    global filename_mp3, mp3_path
    try:
        # Sanitize the message to create a valid filename
        sanitized_message = re.sub(r'[^\w\s-]', '', message).strip().replace(' ', '_')
        
        # Fallback if the message is empty after sanitization
        if not sanitized_message:
            sanitized_message = "audio"
        
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        filename_mp3 = f'{sanitized_message}_{timestamp}.mp3'
        filename_wav = f'{sanitized_message}_{timestamp}.wav'

        # Full path for saving the files
        mp3_path = os.path.join(UPLOAD_DIRECTORY_AUDIO, filename_mp3)
        
        # Generate speech and save as .mp3
        speech = gTTS(text=message, lang= 'en')
        speech.save(mp3_path)
        
        # Convert .mp3 to .wav
        sound = AudioSegment.from_mp3(mp3_path)
        sound.export(filename_wav, format="wav")
        
        # Initialize pygame mixer for audio playback
        pygame.mixer.init()

        try:
            pygame.mixer.music.load(filename_wav)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                pygame.time.Clock().tick(10)
        except Exception as e:
            print(f"Error playing audio: {e}")

        pygame.mixer.music.stop()
        pygame.mixer.quit()
        time.sleep(0.5)

        print(f"Audio saved as {filename_mp3}.")
        
    except Exception as e:
        print(f"Error: {e}")



@app.route('/listen_thread', methods=['GET'])
def listen_thread():
    global listening, recognized_text
    with lock:
        if not listening:  # Start only if not already listening
            listening = True
            recognized_text=""
            thread = Thread(target=recognize_speech, daemon=True)
            thread.start()
            return jsonify({"message": "Listening started"}), 200
        else:
            return jsonify({"message": "Already listening"}), 200


@app.route('/stop', methods=['GET'])
def stop():
    global listening
    with lock:
        if listening:  # Stop only if currently listening
            listening = False
            print("Listening stopped.")
            return jsonify({"message": "Listening stopped"}), 200
        else:
            return jsonify({"message": "Not currently listening"}), 200


@app.route('/display_text', methods=['GET'])
def display_text():
    global recognized_text, listening
    if listening:
        listening = False  

    if recognized_text:
        return jsonify({"text": recognized_text}), 200
    else:
        return jsonify({"message": "No text recognized yet!"}), 200



@app.route('/save', methods=['POST'])
def save():
    global filename, timestamp, recognized_text
    if recognized_text:
        c.execute("INSERT INTO text_data (filename, text, timestamp) VALUES (%s, %s, %s)", 
                  (filename, recognized_text, timestamp))
        conn.commit()
        return jsonify({"message": "saved"}), 200
    return jsonify({"message": "No text to save"}), 400


@app.route('/image_extraction_js', methods=['POST'])
def image_extraction_js():
    try:
        # Get JSON data from the request
        data = request.get_json()
        image_base64 = data.get('image')
        min_x = int(data.get('min_x'))
        min_y = int(data.get('min_y'))
        max_x = int(data.get('max_x'))
        max_y = int(data.get('max_y'))

        if not image_base64:
            return jsonify({"status": "error", "message": "No image provided."}), 400

        # Decode the base64 image
        image_data = base64.b64decode(image_base64.split(",")[1])
        image = Image.open(io.BytesIO(image_data))

        # Crop the image using the bounding box
        cropped_image = image.crop((0, 0, max_x - min_x, max_y - min_y))

        # Save the cropped image to a temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as temp_image_file:
            temp_image_file_path = temp_image_file.name
            cropped_image.save(temp_image_file_path)

        # Extract text from the cropped image
        extraction = extract_text_google_vision(temp_image_file_path)

        # Delete the temporary file after extracting text
        os.remove(temp_image_file_path)

        if extraction:
            return jsonify({"extracted_text": extraction})
        else:
            return jsonify({"status": "error", "message": "No text found in the image."})
    
    except Exception as e:
        print("Error extracting text:", e)
        return jsonify({
            "status": "error",
            "message": f"Error occurred while extracting text: {str(e)}"
        }), 500


@app.route("/save-word", methods=["POST"])
def save_word():
    data = request.json
    word = data.get("word")
    min_x = data.get("min_x")
    min_y = data.get("min_y")
    max_x = data.get("max_x")
    max_y = data.get("max_y")
    image_base64 = data.get("image")

    if not all([word, min_x, min_y, max_x, max_y, image_base64]):
        return jsonify({"error": "All fields are required"}), 400

    try:
        # Decode the base64 image
        image_data = base64.b64decode(image_base64.split(",")[1])
        image = Image.open(io.BytesIO(image_data))

        # Sanitize the word for a valid file name
        sanitized_word = sanitize_filename(word)

        # Ensure the directory exists
        if not os.path.exists(IMAGE_DIRECTORY):
            os.makedirs(IMAGE_DIRECTORY)

        # Save the cropped image
        image_filename = f"{sanitized_word}_{min_x}_{min_y}.png"
        image_path = os.path.join(IMAGE_DIRECTORY, image_filename)
        image.save(image_path)

        # Insert into database (stub functionality; replace with actual database logic)
        query = """
            INSERT INTO words (word, min_x, min_y, max_x, max_y, image)
            VALUES (%s, %s, %s, %s, %s, %s)
        """
        c.execute(query, (sanitized_word, min_x, min_y, max_x, max_y, image_path))
        conn.commit()

        return jsonify({"message": "Word and image saved successfully!"}), 200

    except Exception as e:
        conn.rollback()
        print("Database error:", e)
        return jsonify({"error": "Failed to save to database"}), 500


@app.route("/bbox_to_text", methods=["POST"])
def bbox_to_speech():
    try:
        data = request.json
        text = data.get("text")

        if not text:
            return jsonify({"message": "Text is missing.", "status": "error"}), 400
        
        speak_mode(text)
        return jsonify({"message": "Converted successfully!", "status": "success"})
    except Exception as e:
        print(f"Error in bbox_to_speech: {e}")
        return jsonify({"message": "An error occurred during speech conversion.", "status": "error"}), 500



@app.route("/save_canvas_image", methods=["POST"])
def save_canvas_image():
    global file_path
    try:
        UPLOAD_DIRECTORY_IMAGE = r"C:\Users\Dhas prakash\Desktop\S_I_H\canvas_images"
        # Get image data from the request
        data = request.json
        if not data or "image" not in data:
            raise ValueError("No image data provided")

        image_data = data["image"]

        # Check if the image data is empty
        if not image_data.startswith("data:image/png;base64,"):
            raise ValueError("Invalid image format or empty canvas")

        # Remove the "data:image/png;base64," prefix and decode
        base64_image = image_data.split(",")[1]
        decoded_image = base64.b64decode(base64_image)

        if len(decoded_image) == 0:
            raise ValueError("Decoded image data is empty")

        # Open the image using Pillow
        image = Image.open(BytesIO(decoded_image))

        # Create a new image with a white background and the same size
        new_image = Image.new("RGBA", image.size, (255, 255, 255, 255))  # White background
        new_image.paste(image, (0, 0), image)  # Paste the original image on top (with transparency)

        # Convert the image back to PNG format (with the white background)
        output_image = BytesIO()
        new_image.save(output_image, format="PNG")
        output_image.seek(0)

        # Save the image to the file system
        timing = time.strftime("%Y%m%d-%H%M%S")
        file_name = f"Handwritten_Image_{timing}.png"
        file_path = os.path.join(UPLOAD_DIRECTORY_IMAGE, file_name)

        with open(file_path, "wb") as f:
            f.write(output_image.read())

        # Insert image metadata into the database
        c.execute(
            "INSERT INTO canvas_images (image, filename, time) VALUES (%s, %s, %s)",
            (mysql.connector.Binary(decoded_image), file_name, timing),)
        conn.commit()

        return jsonify({"success": True, "message": f"Image saved as {file_name}"})
    
    except Exception as e:
        print("Error saving image:", e)
        return jsonify({"success": False, "error": str(e)})
    

@app.route('/extract_text', methods=['POST'])
def extract_text():
    global extracted_text
    try:
        image_path = file_path
        extracted_text_1 = extract_text_google_vision(image_path)
        extracted_text = extracted_text_1
        
        print("Extracted Text:")
        print(extracted_text)

        if extracted_text:
            return jsonify({
                "status": "success",
                "message": "Text extracted successfully!",
                "extracted_text": extracted_text
            })
        else:
            return jsonify({
                "status": "error",
                "message": "No text found in the image."
            })
    
    except Exception as e:
        print("Error extracting text:", e)
        return jsonify({
            "status": "error",
            "message": f"Error occurred while extracting text: {str(e)}"
        })


@app.route("/convert_text", methods=["POST"])
def convert_text():
    global extracted_text 
    text = extracted_text
    if text:
        speak_mode(text) 
        return jsonify({
            "message": "Converted successfully!",
            "status": "success",
            "extracted_text": text  
        })
    
    return jsonify({
        "message": "Text is required.",
        "status": "error"
    })



if __name__ == '__main__':
    app.run(debug=True, use_reloader=False, threaded=False, port=5555)
