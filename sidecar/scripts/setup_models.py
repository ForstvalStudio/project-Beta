import os
import sys

# Define model path relative to sidecar
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELS_DIR = os.path.join(BASE_DIR, "models")
MODEL_FILENAME = "phi-3.5-mini.Q4_K_M.gguf"
MODEL_PATH = os.path.join(MODELS_DIR, MODEL_FILENAME)

def setup():
    print("--- Project Beta: Model Setup Utility ---")
    
    if not os.path.exists(MODELS_DIR):
        print(f"Creating models directory at {MODELS_DIR}...")
        os.makedirs(MODELS_DIR)

    if os.path.exists(MODEL_PATH):
        print(f"✅ Model found: {MODEL_PATH}")
        print("Everything is ready for production AI reasoning.")
    else:
        print(f"❌ Model NOT found at {MODEL_PATH}")
        print("\nTo proceed with production AI mapping (AGT-01):")
        print(f"1. Download '{MODEL_FILENAME}' from HuggingFace (e.g. from the Microsoft/Phi-3.5-mini-instruct-GGUF repo)")
        print(f"2. Place the file in: {MODELS_DIR}")
        print("\nNote: Distribution builds will expect the model at this exact path.")

if __name__ == "__main__":
    setup()
