import logging
import os
from llama_cpp import Llama

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("model_test")

model_path = r"c:\Users\rohit\OneDrive\Desktop\project Beta\sidecar\models\phi-3.5-mini.Q4_K_M.gguf"

def test_load():
    print(f"--- Attempting to load model from {model_path} ---")
    if not os.path.exists(model_path):
        print("❌ Error: Model file not found!")
        return

    try:
        # Load with minimal context for a quick test
        llm = Llama(
            model_path=model_path,
            n_ctx=512,
            n_gpu_layers=0, # Force CPU for verification
            verbose=False
        )
        print("✅ Success: Model loaded successfully into llama-cpp-python!")
    except Exception as e:
        print(f"❌ Error: Failed to load model: {e}")

if __name__ == "__main__":
    test_load()
