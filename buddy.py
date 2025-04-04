import os
import time
import webbrowser
import speech_recognition as sr
import pyttsx3
import pywhatkit
import wikipedia
import datetime
import requests
import psutil
import smtplib
import pyautogui
import subprocess
import json
import logging
import threading
import tkinter as tk
from tkinter import messagebox, ttk
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from bs4 import BeautifulSoup
from datetime import datetime as dt
import re
import platform
import sys
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM

# Configuration and Constants
CONFIG_FILE = "buddy_config.json"
LOG_FILE = "buddy.log"

# Setup logging
logging.basicConfig(filename=LOG_FILE, level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')

# Check Python version
if sys.version_info < (3, 7):
    print("Error: Python 3.7 or higher is required.")
    logging.error("Python version too old.")
    exit(1)

# Initialize text-to-speech engine
try:
    engine = pyttsx3.init()
    engine.setProperty('rate', 170)
    engine.setProperty('volume', 1.0)
    voices = engine.getProperty('voices')
    if voices:
        engine.setProperty('voice', voices[0].id)
    else:
        raise ValueError("No voices available for text-to-speech.")
except Exception as e:
    print(f"Failed to initialize text-to-speech: {e}")
    logging.error(f"TTS init error: {e}")
    exit(1)

# Load GPT-2 model and tokenizer
try:
    tokenizer = AutoTokenizer.from_pretrained("openai-community/gpt2")
    # Set a distinct padding token
    if tokenizer.pad_token is None:
        tokenizer.add_special_tokens({'pad_token': '[PAD]'})
    model = AutoModelForCausalLM.from_pretrained("openai-community/gpt2")
    # Resize model embeddings to account for new pad token
    model.resize_token_embeddings(len(tokenizer))
    # Move to GPU if available
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)
    print(f"GPT-2 model loaded successfully on {device}.")
    logging.info(f"GPT-2 model loaded successfully on {device}.")
except Exception as e:
    print(f"Failed to load GPT-2 model: {e}")
    logging.error(f"GPT-2 load error: {e}")
    exit(1)

# Load or create configuration
def load_config():
    """Load configuration from JSON file or create default."""
    default_config = {
        "email": {"sender": "your_email@gmail.com", "password": "your_password"},
        "wake_word": "are you there buddy",
        "news_api_key": "390427571d96423e97c1040796d6b159",
        "weather_api_key": "bf244f1626d9347db0bf15ee4af0d746",
        "city": "New York",
        "language": "en",
        "voice_index": 0,
        "max_history": 10
    }
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
                for key in default_config:
                    if key not in config:
                        config[key] = default_config[key]
                        logging.warning(f"Missing key '{key}' in config, using default: {default_config[key]}")
                return config
        else:
            with open(CONFIG_FILE, 'w') as f:
                json.dump(default_config, f, indent=4)
            logging.info(f"Created new config file: {CONFIG_FILE}")
            return default_config
    except json.JSONDecodeError as e:
        logging.error(f"Invalid JSON in {CONFIG_FILE}: {e}. Using default config.")
        return default_config
    except Exception as e:
        logging.error(f"Config load error: {e}. Using default config.")
        return default_config

config = load_config()

# Conversation history for context
conversation_history = []

# Utility Functions
def speak(text, lang=None):
    """Convert text to speech with optional translation."""
    lang = lang or config.get("language", "en")
    print(f"Buddy ({lang}): {text}")
    logging.info(f"Speaking: {text}")
    try:
        engine.say(text)
        engine.runAndWait()
    except Exception as e:
        logging.error(f"Speech error: {e}")
        print(f"Speech error: {e}")

def listen(timeout=5):
    """Listen for voice commands with timeout."""
    recognizer = sr.Recognizer()
    try:
        with sr.Microphone() as source:
            print("Listening...")
            recognizer.adjust_for_ambient_noise(source, duration=1)
            audio = recognizer.listen(source, timeout=timeout)
            command = recognizer.recognize_google(audio, language=config.get("language", "en")).lower()
            print(f"You said: {command}")
            logging.info(f"Command received: {command}")
            return command
    except sr.WaitTimeoutError:
        return ""
    except sr.UnknownValueError:
        speak("Sorry, I didn't catch that.")
        return ""
    except sr.RequestError as e:
        speak("Microphone or internet issue detected.")
        logging.error(f"Speech recognition error: {e}")
        return ""
    except Exception as e:
        speak("Microphone not detected or access denied. Please check your mic settings.")
        logging.error(f"Unexpected listen error: {e}")
        return ""

def chat_with_gpt(prompt, use_context=True):
    """Use local GPT-2 model for text generation with conversation history."""
    global conversation_history
    try:
        # Build input with system prompt and history
        input_text = "You are Buddy, a helpful AI assistant created by xAI. Provide accurate, concise, and friendly responses.\n"
        if use_context and conversation_history:
            for entry in conversation_history[-config["max_history"]:]:
                input_text += f"{entry['role']}: {entry['content']}\n"
        input_text += f"user: {prompt}\nassistant: "

        # Tokenize input with padding and attention mask
        inputs = tokenizer(
            input_text,
            return_tensors="pt",
            truncation=True,
            max_length=512,
            padding=True,
            return_attention_mask=True
        )
        inputs = {k: v.to(device) for k, v in inputs.items()}  # Move to GPU/CPU
        
        # Generate response with attention mask
        outputs = model.generate(
            input_ids=inputs["input_ids"],
            attention_mask=inputs["attention_mask"],
            max_length=500,
            num_return_sequences=1,
            temperature=0.7,
            top_k=50,
            top_p=0.95,
            pad_token_id=tokenizer.pad_token_id,
            do_sample=True
        )
        
        # Decode response
        reply = tokenizer.decode(outputs[0], skip_special_tokens=True).strip()
        # Extract only the generated part
        reply = reply[len(input_text):].strip()
        
        # Fallback if response is empty or too short
        if not reply or len(reply.split()) < 3:
            reply = "Sorry, I couldn’t come up with a good response. Try asking again!"

        # Update conversation history
        conversation_history.append({"role": "user", "content": prompt})
        conversation_history.append({"role": "assistant", "content": reply})
        if len(conversation_history) > config["max_history"] * 2:
            conversation_history.pop(0)
            conversation_history.pop(0)
        
        return reply
    except Exception as e:
        logging.error(f"GPT-2 error: {e}")
        return f"Sorry, GPT-2 failed: {str(e)}"

# Advanced AI Features
def summarize_text(text):
    if not text:
        return "No text provided to summarize."
    prompt = f"Summarize this text in a concise manner:\n\n{text}"
    return chat_with_gpt(prompt, use_context=False)

def analyze_sentiment(text):
    if not text:
        return "No text provided to analyze."
    prompt = f"Analyze the sentiment of this text (positive, negative, neutral) and explain why:\n\n{text}"
    return chat_with_gpt(prompt, use_context=False)

def generate_ideas(topic):
    if not topic:
        return "No topic provided."
    prompt = f"Generate 5 creative ideas related to {topic}."
    return chat_with_gpt(prompt, use_context=False)

# System Monitoring
def get_system_info():
    try:
        cpu_usage = psutil.cpu_percent(interval=1)
        ram = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        battery = psutil.sensors_battery()
        battery_info = f"Battery: {battery.percent}% (Charging: {battery.power_plugged})" if battery else "Battery: Unknown"
        return (f"CPU Usage: {cpu_usage}%\n"
                f"RAM: {ram.percent}% used ({ram.available / (1024**3):.2f} GB free)\n"
                f"Disk: {disk.percent}% used ({disk.free / (1024**3):.2f} GB free)\n"
                f"{battery_info}")
    except Exception as e:
        logging.error(f"System info error: {e}")
        return "Failed to retrieve system info."

# File Management
def create_file(filename):
    if not filename:
        speak("No filename provided.")
        return
    try:
        with open(filename, 'w') as f:
            f.write("")
        speak(f"File {filename} created.")
    except Exception as e:
        speak("Failed to create file.")
        logging.error(f"File creation error: {e}")

def read_file(filename):
    if not filename:
        speak("No filename provided.")
        return ""
    try:
        with open(filename, 'r') as f:
            content = f.read()
        speak(f"Content of {filename}: {content[:100]}")
        return content
    except Exception as e:
        speak("File not found or unreadable.")
        logging.error(f"File read error: {e}")
        return ""

# Weather and News
def get_weather(city=None):
    city = city or config["city"]
    if not config["weather_api_key"] or "your_openweathermap_key" in config["weather_api_key"]:
        speak("Weather API key is missing or invalid. Please configure it.")
        return
    url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={config['weather_api_key']}&units=metric"
    try:
        response = requests.get(url).json()
        if response.get("cod") != 200:
            raise Exception(response.get("message", "Unknown error"))
        temp = response["main"]["temp"]
        desc = response["weather"][0]["description"]
        speak(f"In {city}, it's {temp}°C with {desc}.")
    except Exception as e:
        speak("Couldn't fetch weather data.")
        logging.error(f"Weather error: {e}")

def get_news():
    if not config["news_api_key"] or "your_newsapi_key" in config["news_api_key"]:
        speak("News API key is missing or invalid. Please configure it.")
        return
    url = f"https://newsapi.org/v2/top-headlines?country=us&apiKey={config['news_api_key']}"
    try:
        response = requests.get(url).json()
        articles = response["articles"][:3]
        speak("Here are the latest news headlines:")
        for i, article in enumerate(articles, 1):
            speak(f"{i}. {article['title']}")
    except Exception as e:
        speak("Couldn't fetch news.")
        logging.error(f"News error: {e}")

# Email Functionality
def send_email(to_email, subject, message):
    sender_email = config["email"]["sender"]
    sender_password = config["email"]["password"]
    if "your_email" in sender_email or "your_password" in sender_password:
        speak("Email credentials are not configured. Please update them.")
        return
    if not all([to_email, subject, message]):
        speak("Missing email details (to, subject, or message).")
        return
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = to_email
    msg['Subject'] = subject
    msg.attach(MIMEText(message, 'plain'))
    
    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, to_email, msg.as_string())
        server.quit()
        speak("Email sent successfully!")
        logging.info(f"Email sent to {to_email}")
    except Exception as e:
        speak("Failed to send email.")
        logging.error(f"Email error: {e}")

# Reminders
reminders = []

def set_reminder(task, delay_minutes):
    if not task:
        speak("No task provided.")
        return
    try:
        delay = int(delay_minutes)
        if delay < 0:
            speak("Delay cannot be negative.")
            return
        reminder_time = dt.now() + datetime.timedelta(minutes=delay)
        reminders.append({"task": task, "time": reminder_time})
        speak(f"Reminder set for '{task}' in {delay} minutes.")
        threading.Timer(delay * 60, remind, args=(task,)).start()
    except (ValueError, TypeError):
        speak("Please provide a valid number of minutes.")
        logging.error(f"Invalid delay value: {delay_minutes}")

def remind(task):
    try:
        speak(f"Reminder: Time to {task}!")
        if reminders and reminders[0]["task"] == task:
            reminders.pop(0)
    except Exception as e:
        logging.error(f"Reminder error: {e}")

# Enhanced GUI
def start_gui():
    print("Starting GUI thread...")
    logging.info("Attempting to start GUI")
    
    def update_status(text):
        try:
            status_label.config(text=text)
            log_text.insert(tk.END, f"{dt.now().strftime('%H:%M:%S')}: {text}\n")
            log_text.see(tk.END)
        except Exception as e:
            logging.error(f"Update status error: {e}")

    def gui_listen():
        try:
            command = listen()
            if command:
                update_status(f"You said: {command}")
                execute_command(command)
            root.after(1000, gui_listen)
        except Exception as e:
            logging.error(f"GUI listen error: {e}")

    def execute_from_entry():
        command = command_entry.get().strip()
        if command:
            update_status(f"Typed: {command}")
            execute_command(command)
            command_entry.delete(0, tk.END)

    def clear_log():
        log_text.delete(1.0, tk.END)
        update_status("Log cleared.")

    try:
        root = tk.Tk()
        print("Tkinter root created.")
        root.title("Buddy AI Assistant")
        root.geometry("700x500")
        root.configure(bg="#f0f0f0")
        root.resizable(True, True)

        # Header Frame
        header_frame = tk.Frame(root, bg="#f0f0f0")
        header_frame.pack(pady=10)
        tk.Label(header_frame, text="Buddy AI", font=("Arial", 24, "bold"), bg="#f0f0f0").pack()

        # Status Label
        status_label = tk.Label(root, text="Listening for commands...", wraplength=650, bg="#f0f0f0", font=("Arial", 12))
        status_label.pack(pady=5)

        # Log Area
        log_frame = tk.Frame(root, bg="#f0f0f0")
        log_frame.pack(pady=10, padx=10, fill=tk.BOTH, expand=True)
        log_text = tk.Text(log_frame, height=15, width=80, font=("Arial", 10), wrap=tk.WORD)
        scrollbar = tk.Scrollbar(log_frame, command=log_text.yview)
        log_text.config(yscrollcommand=scrollbar.set)
        log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Command Entry
        entry_frame = tk.Frame(root, bg="#f0f0f0")
        entry_frame.pack(pady=5)
        tk.Label(entry_frame, text="Type Command:", bg="#f0f0f0", font=("Arial", 10)).pack(side=tk.LEFT, padx=5)
        command_entry = tk.Entry(entry_frame, width=50, font=("Arial", 10))
        command_entry.pack(side=tk.LEFT, padx=5)
        ttk.Button(entry_frame, text="Run", command=execute_from_entry).pack(side=tk.LEFT)

        # Buttons Frame
        button_frame = tk.Frame(root, bg="#f0f0f0")
        button_frame.pack(pady=10)
        ttk.Button(button_frame, text="News", command=lambda: execute_command("news")).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Weather", command=lambda: execute_command(f"weather in {config['city']}")).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Screenshot", command=lambda: execute_command("screenshot")).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="System Status", command=lambda: execute_command("system status")).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Send Email", command=lambda: execute_command("send email")).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Clear Log", command=clear_log).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Exit", command=root.quit).pack(side=tk.LEFT, padx=5)

        root.after(1000, gui_listen)
        print("GUI mainloop starting...")
        root.mainloop()
    except tk.TclError as e:
        speak("GUI failed: Display issue detected. Are you running this on a graphical environment?")
        logging.error(f"TclError in GUI: {e}")
    except Exception as e:
        speak("Failed to launch GUI.")
        logging.error(f"GUI error: {e}")
    finally:
        print("GUI thread ended.")

# Command Execution
def execute_command(command):
    if not command:
        return
    
    system = platform.system()
    print(f"Executing command: {command}")
    
    if "open notepad" in command:
        if system == "Windows":
            try:
                subprocess.Popen("notepad.exe")
                speak("Notepad opened.")
            except FileNotFoundError:
                speak("Notepad not found.")
        elif system == "Darwin":
            try:
                subprocess.Popen(["open", "-a", "TextEdit"])
                speak("TextEdit opened.")
            except:
                speak("TextEdit not found.")
        else:
            try:
                subprocess.Popen(["gedit"])
                speak("Gedit opened.")
            except:
                speak("Text editor not found.")
    elif "open chrome" in command:
        if system == "Windows":
            try:
                subprocess.Popen("chrome.exe")
                speak("Google Chrome opened.")
            except FileNotFoundError:
                speak("Chrome not found.")
        elif system == "Darwin":
            try:
                subprocess.Popen(["open", "-a", "Google Chrome"])
                speak("Google Chrome opened.")
            except:
                speak("Chrome not found.")
        else:
            try:
                subprocess.Popen(["google-chrome"])
                speak("Google Chrome opened.")
            except:
                speak("Chrome not found.")
    elif "search google for" in command:
        query = command.replace("search google for", "").strip()
        if not query:
            speak("What should I search for?")
            query = listen()
        if query:
            webbrowser.open(f"https://www.google.com/search?q={query}")
            speak(f"Searching Google for {query}.")
    elif "play" in command:
        song = command.replace("play", "").strip()
        if not song:
            speak("What should I play?")
            song = listen()
        if song:
            try:
                pywhatkit.playonyt(song)
                speak(f"Playing {song} on YouTube.")
            except Exception as e:
                speak("Failed to play song.")
                logging.error(f"Play error: {e}")
    elif "tell me about" in command:
        topic = command.replace("tell me about", "").strip()
        if not topic:
            speak("What should I tell you about?")
            topic = listen()
        if topic:
            try:
                info = wikipedia.summary(topic, sentences=2)
                speak(info)
            except Exception as e:
                speak(f"No info found on {topic}.")
                logging.error(f"Wikipedia error: {e}")
    elif "system status" in command:
        speak(get_system_info())
    elif "screenshot" in command:
        try:
            file_path = f"screenshot_{int(time.time())}.png"
            pyautogui.screenshot().save(file_path)
            speak(f"Screenshot saved as {file_path}.")
        except Exception as e:
            speak("Failed to take screenshot.")
            logging.error(f"Screenshot error: {e}")
    elif "send email" in command:
        speak("Who should I send it to?")
        to_email = listen()
        if not to_email:
            speak("No email address provided.")
            return
        speak("What's the subject?")
        subject = listen()
        if not subject:
            speak("No subject provided.")
            return
        speak("What's the message?")
        message = listen()
        if not message:
            speak("No message provided.")
            return
        send_email(to_email, subject, message)
    elif "weather in" in command:
        city = command.replace("weather in", "").strip()
        if not city:
            speak("Which city?")
            city = listen()
        if city:
            get_weather(city)
    elif "news" in command:
        get_news()
    elif "create file" in command:
        filename = command.replace("create file", "").strip()
        if not filename:
            speak("What’s the filename?")
            filename = listen()
        if filename:
            create_file(filename)
    elif "read file" in command:
        filename = command.replace("read file", "").strip()
        if not filename:
            speak("Which file?")
            filename = listen()
        if filename:
            content = read_file(filename)
            if content and "summarize" in command:
                summary = summarize_text(content)
                speak(f"Summary: {summary}")
    elif "summarize" in command:
        speak("Please provide the text to summarize by reading a file or saying it.")
        text = listen()
        if not text:
            speak("No text provided.")
            return
        if "file" in text.lower():
            speak("Which file?")
            filename = listen()
            if filename:
                content = read_file(filename)
                if content:
                    summary = summarize_text(content)
                    speak(f"Summary: {summary}")
        else:
            summary = summarize_text(text)
            speak(f"Summary: {summary}")
    elif "analyze sentiment" in command:
        speak("Please provide the text to analyze by reading a file or saying it.")
        text = listen()
        if not text:
            speak("No text provided.")
            return
        if "file" in text.lower():
            speak("Which file?")
            filename = listen()
            if filename:
                content = read_file(filename)
                if content:
                    analysis = analyze_sentiment(content)
                    speak(f"Sentiment analysis: {analysis}")
        else:
            analysis = analyze_sentiment(text)
            speak(f"Sentiment analysis: {analysis}")
    elif "generate ideas" in command:
        topic = command.replace("generate ideas", "").strip()
        if not topic:
            speak("What topic should I generate ideas for?")
            topic = listen()
        if topic:
            ideas = generate_ideas(topic)
            speak(f"Here are some ideas: {ideas}")
    elif "set reminder" in command:
        speak("What’s the task?")
        task = listen()
        if not task:
            speak("No task provided.")
            return
        speak("In how many minutes?")
        delay = listen()
        if delay:
            set_reminder(task, delay)
        else:
            speak("No delay provided.")
    elif "clear history" in command:
        conversation_history.clear()
        speak("Conversation history cleared.")
    elif "shutdown" in command:
        if system == "Windows":
            try:
                speak("Shutting down in 10 seconds.")
                os.system("shutdown /s /t 10")
            except:
                speak("Shutdown failed.")
        elif system == "Darwin":
            try:
                speak("Shutting down in 10 seconds.")
                os.system("sudo shutdown -h +10")
            except:
                speak("Shutdown failed. May require sudo privileges.")
        elif system == "Linux":
            try:
                speak("Shutting down in 10 seconds.")
                os.system("sudo shutdown -h 10")
            except:
                speak("Shutdown failed. May require sudo privileges.")
        else:
            speak("Shutdown not supported on this system.")
    elif "restart" in command:
        if system == "Windows":
            try:
                speak("Restarting in 10 seconds.")
                os.system("shutdown /r /t 10")
            except:
                speak("Restart failed.")
        elif system == "Darwin":
            try:
                speak("Restarting in 10 seconds.")
                os.system("sudo shutdown -r +10")
            except:
                speak("Restart failed. May require sudo privileges.")
        elif system == "Linux":
            try:
                speak("Restarting in 10 seconds.")
                os.system("sudo reboot")
            except:
                speak("Restart failed. May require sudo privileges.")
        else:
            speak("Restart not supported on this system.")
    elif "exit" in command:
        speak("Goodbye!")
        exit(0)
    elif "gui" in command:
        speak("Starting GUI mode.")
        print("GUI command triggered.")
        threading.Thread(target=start_gui, daemon=True).start()
    else:
        response = chat_with_gpt(command)
        speak(response)

# Main Loop
def main():
    speak("Hello! I am Buddy, your AI assistant with a local GPT-2 brain. Say 'Are you there, Buddy?' to wake me up.")
    while True:
        try:
            wake_word = listen()
            if wake_word and config["wake_word"] in wake_word:
                speak("I am ready! How can I assist you today?")
                while True:
                    command = listen()
                    if command:
                        execute_command(command)
                    time.sleep(1)
        except Exception as e:
            logging.error(f"Main loop error: {e}")
            print(f"Error in main loop: {e}. Check {LOG_FILE} for details.")
            time.sleep(5)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        speak("Shutting down Buddy.")
        logging.info("Buddy terminated by user.")
    except Exception as e:
        print(f"Critical error occurred: {e}. Check {LOG_FILE} for details.")
        logging.error(f"Program error: {e}")
        exit(1)