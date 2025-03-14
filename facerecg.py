import cv2
import numpy as np

# Load pre-trained models
face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")

age_model = cv2.dnn.readNetFromCaffe(
    "https://raw.githubusercontent.com/opencv/opencv/master/samples/dnn/face_detector/deploy.prototxt",
    "https://raw.githubusercontent.com/opencv/opencv_3rdparty/master/opencv_face_detector/models/res10_300x300_ssd_iter_140000.caffemodel"
)

age_net = cv2.dnn.readNetFromCaffe(
    "https://raw.githubusercontent.com/opencv/opencv/master/samples/dnn/age_gender/age_deploy.prototxt",
    "https://raw.githubusercontent.com/opencv/opencv_3rdparty/master/opencv_face_detector/models/age_net.caffemodel"
)

# Age categories
age_labels = ["0-2", "4-6", "8-12", "15-20", "25-32", "38-43", "48-53", "60-100"]

# Open webcam
cap = cv2.VideoCapture(0)

while True:
    ret, frame = cap.read()
    if not ret:
        break

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    faces = face_cascade.detectMultiScale(gray, scaleFactor=1.2, minNeighbors=5, minSize=(50, 50))

    for (x, y, w, h) in faces:
        face_roi = frame[y:y+h, x:x+w]

        # Prepare face for age detection
        blob = cv2.dnn.blobFromImage(face_roi, 1.0, (227, 227), (78.426, 87.768, 114.895), swapRB=False)

        # Predict age
        age_net.setInput(blob)
        age_preds = age_net.forward()
        age = age_labels[age_preds[0].argmax()]

        # Draw rectangle and age
        cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
        cv2.putText(frame, f"Age: {age}", (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)

    cv2.imshow("Face & Age Detection", frame)

    # Press 'q' to quit
    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

cap.release()
cv2.destroyAllWindows()
