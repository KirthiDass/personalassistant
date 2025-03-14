import os
import time
import webbrowser
import speech_recognition as sr
import pyttsx3
import pywhatkit
import wikipedia
import datetime
import requests
import openai
import psutil
import smtplib
import pyautogui
import subprocess
import json
import logging
import threading
import tkinter as tk
from tkinter import messagebox
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from bs4 import BeautifulSoup
from datetime import datetime as dt

# Configuration file
CONFIG_FILE = "buddy_config.json"
LOG_FILE = "buddy.log"

# OpenAI API Key (Replace with your own)
openai.api_key = "Your_OpenAI_API_Key"

# Setup logging
logging.basicConfig(filename=LOG_FILE, level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')

# Initialize text-to-speech engine
engine = pyttsx3.init()
engine.setProperty('rate', 170)  # Speaking speed
engine.setProperty('volume', 1.0)  # Volume
voices = engine.getProperty('voices')
engine.setProperty('voice', voices[0].id)  # Default voice

# Load or create configuration
def load_config():
    default_config = {
        "email": {"sender": "your_email@gmail.com", "password": "your_password"},
        "wake_word": "are you there buddy",
        "news_api_key": "your_newsapi_key",
        "weather_api_key": "your_openweathermap_key",
        "city": "New York"
    }
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    else:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(default_config, f, indent=4)
        return default_config

config = load_config()

# Utility Functions
def speak(text):
    """Convert text to speech."""
    print(f"Buddy: {text}")
    logging.info(f"Speaking: {text}")
    engine.say(text)
    engine.runAndWait()

def listen(timeout=5):
    """Listen for voice commands with timeout."""
    recognizer = sr.Recognizer()
    with sr.Microphone() as source:
        print("Listening...")
        recognizer.adjust_for_ambient_noise(source, duration=1)
        try:
            audio = recognizer.listen(source, timeout=timeout)
            command = recognizer.recognize_google(audio).lower()
            print(f"You said: {command}")
            logging.info(f"Command received: {command}")
            return command
        except sr.WaitTimeoutError:
            return ""
        except sr.UnknownValueError:
            speak("Sorry, I didn't catch that.")
            return ""
        except sr.RequestError:
            speak("Microphone or internet issue detected.")
            return ""

def chat_with_gpt(prompt):
    """Use ChatGPT for natural conversation."""
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are Buddy, a helpful AI assistant."},
                {"role": "user", "content": prompt}
            ]
        )
        return response["choices"][0]["message"]["content"]
    except Exception as e:
        logging.error(f"GPT error: {e}")
        return "Sorry, I couldn't connect to the AI brain. Try again later!"

# System Monitoring
def get_system_info():
    """Fetch detailed system usage."""
    cpu_usage = psutil.cpu_percent(interval=1)
    ram = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    battery = psutil.sensors_battery()
    battery_info = f"Battery: {battery.percent}% (Charging: {battery.power_plugged})" if battery else "Battery: Unknown"
    return (f"CPU Usage: {cpu_usage}%\n"
            f"RAM: {ram.percent}% used ({ram.available / (1024**3):.2f} GB free)\n"
            f"Disk: {disk.percent}% used ({disk.free / (1024**3):.2f} GB free)\n"
            f"{battery_info}")

# File Management
def create_file(filename):
    """Create a new file."""
    try:
        with open(filename, 'w') as f:
            f.write("")
        speak(f"File {filename} created.")
    except Exception as e:
        speak("Failed to create file.")
        logging.error(f"File creation error: {e}")

def read_file(filename):
    """Read content of a file."""
    try:
        with open(filename, 'r') as f:
            content = f.read()
        speak(f"Content of {filename}: {content[:100]}")  # Limit to 100 chars
        return content
    except Exception as e:
        speak("File not found or unreadable.")
        logging.error(f"File read error: {e}")
        return ""

# Weather and News
def get_weather(city=None):
    """Fetch weather information."""
    city = city or config["city"]
    url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={config['weather_api_key']}&units=metric"
    try:
        response = requests.get(url).json()
        if response.get("cod") != 200:
            raise Exception(response.get("message"))
        temp = response["main"]["temp"]
        desc = response["weather"][0]["description"]
        speak(f"In {city}, it's {temp}°C with {desc}.")
    except Exception as e:
        speak("Couldn't fetch weather data.")
        logging.error(f"Weather error: {e}")

def get_news():
    """Fetch latest news headlines."""
    url = f"https://newsapi.org/v2/top-headlines?country=us&apiKey={config['news_api_key']}"
    try:
        response = requests.get(url).json()
        articles = response["articles"][:3]  # Top 3 headlines
        speak("Here are the latest news headlines:")
        for i, article in enumerate(articles, 1):
            speak(f"{i}. {article['title']}")
    except Exception as e:
        speak("Couldn't fetch news.")
        logging.error(f"News error: {e}")

# Email Functionality
def send_email(to_email, subject, message):
    """Send an email with error handling."""
    sender_email = config["email"]["sender"]
    sender_password = config["email"]["password"]
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
    """Set a reminder with a delay in minutes."""
    reminder_time = dt.now() + datetime.timedelta(minutes=delay_minutes)
    reminders.append({"task": task, "time": reminder_time})
    speak(f"Reminder set for '{task}' in {delay_minutes} minutes.")
    threading.Timer(delay_minutes * 60, remind, args=(task,)).start()

def remind(task):
    """Trigger reminder."""
    speak(f"Reminder: Time to {task}!")
    reminders.pop(0)  # Remove the first reminder

# GUI (Optional)
def start_gui():
    """Launch a simple GUI for Buddy."""
    root = tk.Tk()
    root.title("Buddy AI Assistant")
    root.geometry("400x300")
    
    tk.Label(root, text="Buddy AI", font=("Arial", 20)).pack(pady=10)
    status_label = tk.Label(root, text="Say 'Are you there, Buddy?' to wake me up.", wraplength=350)
    status_label.pack(pady=10)
    
    def update_status(text):
        status_label.config(text=text)
    
    def gui_listen():
        command = listen()
        if command:
            update_status(f"You said: {command}")
            execute_command(command)
        root.after(1000, gui_listen)
    
    root.after(1000, gui_listen)
    root.mainloop()

# Command Execution
def execute_command(command):
    """Process and execute voice commands."""
    if not command:
        return
    
    if "open notepad" in command:
        subprocess.Popen("notepad.exe")
        speak("Notepad opened.")
    elif "open chrome" in command:
        subprocess.Popen("chrome.exe")
        speak("Google Chrome opened.")
    elif "search google for" in command:
        query = command.replace("search google for", "").strip()
        webbrowser.open(f"https://www.google.com/search?q={query}")
        speak(f"Searching Google for {query}.")
    elif "play" in command:
        song = command.replace("play", "").strip()
        pywhatkit.playonyt(song)
        speak(f"Playing {song} on YouTube.")
    elif "tell me about" in command:
        topic = command.replace("tell me about", "").strip()
        try:
            info = wikipedia.summary(topic, sentences=2)
            speak(info)
        except:
            speak(f"No info found on {topic}.")
    elif "system status" in command:
        speak(get_system_info())
    elif "screenshot" in command:
        file_path = f"screenshot_{int(time.time())}.png"
        pyautogui.screenshot().save(file_path)
        speak(f"Screenshot saved as {file_path}.")
    elif "send email" in command:
        speak("Who should I send it to?")
        to_email = listen()
        speak("What's the subject?")
        subject = listen()
        speak("What's the message?")
        message = listen()
        send_email(to_email, subject, message)
    elif "weather in" in command:
        city = command.replace("weather in", "").strip()
        get_weather(city)
    elif "news" in command:
        get_news()
    elif "create file" in command:
        filename = command.replace("create file", "").strip()
        create_file(filename)
    elif "read file" in command:
        filename = command.replace("read file", "").strip()
        read_file(filename)
    elif "set reminder" in command:
        speak("What’s the task?")
        task = listen()
        speak("In how many minutes?")
        delay = int(listen() or 0)
        set_reminder(task, delay)
    elif "shutdown" in command:
        speak("Shutting down in 10 seconds.")
        os.system("shutdown /s /t 10")
    elif "restart" in command:
        speak("Restarting in 10 seconds.")
        os.system("shutdown /r /t 10")
    elif "exit" in command:
        speak("Goodbye!")
        exit()
    elif "gui" in command:
        speak("Starting GUI mode.")
        threading.Thread(target=start_gui, daemon=True).start()
    else:
        response = chat_with_gpt(command)
        speak(response)

# Main Loop
def main():
    """Main loop with wake word detection."""
    speak("Hello! I am Buddy, your AI assistant. Say 'Are you there, Buddy?' to wake me up.")
    while True:
        wake_word = listen()
        if config["wake_word"] in wake_word:
            speak("I am ready! How can I assist you?")
            while True:
                command = listen()
                if command:
                    execute_command(command)
                time.sleep(1)  # Prevent CPU overload

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        speak("Shutting down Buddy.")
        logging.info("Buddy terminated by user.")