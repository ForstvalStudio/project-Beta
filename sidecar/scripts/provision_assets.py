import os
import shutil
from huggingface_hub import hf_hub_download, snapshot_download

# Enable high-speed downloads (parallellized Rust-based hf-transfer)
os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "1"

# Paths relative to the script's directory
SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(SCRIPTS_DIR)
MODELS_DIR = os.path.join(BASE_DIR, "models")

# 1. Phi-3.5-mini GGUF Configuration
GGUF_REPO = "bartowski/Phi-3.5-mini-instruct-GGUF"
GGUF_FILE = "Phi-3.5-mini-instruct-Q4_K_M.gguf"
GGUF_TARGET = "phi-3.5-mini.Q4_K_M.gguf"

# 2. Nomic Embed Text Configuration
EMBED_REPO = "nomic-ai/nomic-embed-text-v1.5"
EMBED_TARGET_DIR = os.path.join(MODELS_DIR, "nomic-embed-text-v1.5")

def provision():
    print("--- Project Beta: Production Asset Provisioning ---")
    
    if not os.path.exists(MODELS_DIR):
        print(f"Creating models directory at {MODELS_DIR}...")
        os.makedirs(MODELS_DIR)

    # A. Provision GGUF Model
    target_path = os.path.join(MODELS_DIR, GGUF_TARGET)
    if not os.path.exists(target_path):
        print(f"Downloading {GGUF_FILE} from {GGUF_REPO}...")
        try:
            downloaded = hf_hub_download(repo_id=GGUF_REPO, filename=GGUF_FILE)
            shutil.move(downloaded, target_path)
            print(f"✅ Successfully provisioned GGUF model: {GGUF_TARGET}")
        except Exception as e:
            print(f"❌ Failed to download GGUF model: {e}")
    else:
        print(f"✅ GGUF model already exists: {GGUF_TARGET}")

    # B. Provision Embedding Model (Full snapshot for offline use)
    if not os.path.exists(EMBED_TARGET_DIR):
        print(f"Downloading embedding weights from {EMBED_REPO}...")
        try:
            snapshot_download(
                repo_id=EMBED_REPO,
                local_dir=EMBED_TARGET_DIR,
                local_dir_use_symlinks=False,
                trust_remote_code=True
            )
            print(f"✅ Successfully provisioned embedding model at {EMBED_TARGET_DIR}")
        except Exception as e:
            print(f"❌ Failed to download embedding weights: {e}")
    else:
        print(f"✅ Embedding weights already exist: {EMBED_TARGET_DIR}")

    print("\n--- Provisioning Complete ---")

if __name__ == "__main__":
    provision()
