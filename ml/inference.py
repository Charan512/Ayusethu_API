import json
import numpy as np
import tensorflow as tf
import joblib
from PIL import Image
from io import BytesIO

# Paths
BASE = "ml"

# Load once (IMPORTANT)
feature_extractor = tf.keras.models.load_model(f"{BASE}/feature_extractor.keras")
pca = joblib.load(f"{BASE}/pca.pkl")
svm = joblib.load(f"{BASE}/svm_model.pkl")

with open(f"{BASE}/class_names.json") as f:
    CLASS_NAMES = json.load(f)

IMG_SIZE = (300, 300)

def preprocess_image(image_bytes: bytes):
    img = Image.open(BytesIO(image_bytes)).convert("RGB")
    img = img.resize(IMG_SIZE)
    arr = np.array(img) / 255.0
    return np.expand_dims(arr, axis=0)

def predict_species(image_bytes: bytes) -> str:
    img = preprocess_image(image_bytes)

    features = feature_extractor.predict(img)
    features = pca.transform(features)

    pred_idx = svm.predict(features)[0]
    return CLASS_NAMES[str(pred_idx)]
