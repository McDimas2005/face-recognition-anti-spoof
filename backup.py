# import cv2
# import numpy as np
# import socket
# import psutil
# import os

# import tensorflow as tf
# from tensorflow.keras.layers import Dense, GlobalAveragePooling2D, Dropout, Flatten
# from tensorflow.keras.models import Model
# from tensorflow.keras.preprocessing.image import ImageDataGenerator
# from tensorflow.keras.optimizers import Adam
# from sklearn.metrics import classification_report, confusion_matrix
# import matplotlib.pyplot as plt

# # Required Imports
# from tensorflow.keras.models import load_model
# from keras.saving import register_keras_serializable
# import tensorflow as tf

# # Register the l2_normalize Function
# @register_keras_serializable(package="custom")
# def l2_normalize(x, axis=None, epsilon=1e-12):
#     return tf.math.l2_normalize(x, axis=axis, epsilon=epsilon)

# # Register the scaling Function
# @register_keras_serializable(package="custom")
# def scaling(x, **kwargs):  # Add **kwargs to handle unexpected arguments
#     return x / 255.0

# # Load the Model
# try:
#     # Pass the registered custom functions
#     model = load_model(
#         'FaceNet_fineTuned_model.h5',
#         custom_objects={"l2_normalize": l2_normalize, "scaling": scaling}
#     )
#     print("Model loaded successfully!")

# except Exception as e:
#     print("Error loading model:", e)

# # Function to get the Wi-Fi IP address
# def get_wifi_ip():
#     wifi_ip = "Not Connected"
#     try:
#         # Iterate through network interfaces
#         for iface, addrs in psutil.net_if_addrs().items():
#             if "Wi-Fi" in iface or "wlan" in iface.lower():  # Look for Wi-Fi interface
#                 for addr in addrs:
#                     if addr.family == socket.AF_INET:  # IPv4 address
#                         wifi_ip = addr.address
#                         break
#     except Exception as e:
#         print("Error fetching Wi-Fi IP:", e)
#     return wifi_ip

# # Load the DNN model for face detection
# model_path = "DNN/deploy.prototxt"  # Replace with your deploy.prototxt path
# weights_path = "DNN/res10_300x300_ssd_iter_140000.caffemodel"  # Replace with your model weights path
# net = cv2.dnn.readNetFromCaffe(model_path, weights_path)

# # Load the trained classification model
# # Assume `model` is already defined and loaded elsewhere in your script

# # Open webcam
# cap = cv2.VideoCapture(0)

# # Get the Wi-Fi IP address

# while True:
#     wifi_ip = get_wifi_ip()
#     # Read frame from the webcam
#     ret, frame = cap.read()
#     if not ret:
#         break

#     # Display the Wi-Fi IP address at the top-left corner
#     cv2.putText(frame, f"Wi-Fi IP: {wifi_ip}", (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)

#     # Get frame dimensions
#     (h, w) = frame.shape[:2]

#     # Prepare the frame for the DNN
#     blob = cv2.dnn.blobFromImage(frame, scalefactor=1.0, size=(300, 300),
#                                  mean=(104.0, 177.0, 123.0), swapRB=False, crop=False)
#     net.setInput(blob)
#     detections = net.forward()

#     for i in range(0, detections.shape[2]):
#         confidence = detections[0, 0, i, 2]
#         if confidence > 0.5:  # Confidence threshold
#             # Get bounding box for the face
#             box = detections[0, 0, i, 3:7] * [w, h, w, h]
#             (x1, y1, x2, y2) = box.astype("int")

#             # Ensure bounding box stays within the frame
#             x1, y1, x2, y2 = max(0, x1), max(0, y1), min(w, x2), min(h, y2)

#             # Extract the face from the frame
#             face = frame[y1:y2, x1:x2]
#             if face.size == 0:  # Skip invalid crops
#                 continue
            
#             # Preprocess the face for the classification model
#             try:
#                 face_resized = cv2.resize(face, (224, 224))  # Resize to match model input
#             except Exception as e:
#                 print("Error resizing face:", e)
#                 continue
            
#             face_normalized = face_resized / 255.0
#             face_array = np.expand_dims(face_normalized, axis=0)

#             # Predict using the trained model
#             prediction = model.predict(face_array, verbose=0)  # Suppress logging
#             similarity_score = prediction[0][0] * 100  # Convert to percentage
#             label = "You" if similarity_score > 80 else "Not You"

#             # Draw a rectangle and label around the face
#             color = (0, 255, 0) if label == "You" else (0, 0, 255)
#             cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
#             cv2.putText(frame, f"{label} ({similarity_score:.2f}%)", (x1, y1 - 10),
#                         cv2.FONT_HERSHEY_SIMPLEX, 0.9, color, 2)

#     # Display the frame with rectangles and IP
#     cv2.imshow('Face Recognition', frame)

#     # Break the loop if 'q' is pressed
#     if cv2.waitKey(1) & 0xFF == ord('q'):
#         break

# # Release the webcam and close the window
# cap.release()
# cv2.destroyAllWindows()
