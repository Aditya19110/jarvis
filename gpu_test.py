import os
import time
import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification

# -----------------------------
# 1. Check device (GPU / CPU)
# -----------------------------
device = "mps" if torch.backends.mps.is_available() else "cpu"
print(f"Using device: {device}")

# -----------------------------
# 2. Load model from HuggingFace / Local Path
# -----------------------------
model_name = "distilbert-base-uncased"
local_model_path = f"./models/{model_name}"

start = time.time()

if not os.path.exists(local_model_path):
    print(f"Downloading model and saving locally to {local_model_path}...")
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForSequenceClassification.from_pretrained(model_name)
    
    # Save the model and tokenizer to our local project folder
    tokenizer.save_pretrained(local_model_path)
    model.save_pretrained(local_model_path)
else:
    print(f"Loading model from local directory: {local_model_path}")

# Load directly from the local path
tokenizer = AutoTokenizer.from_pretrained(local_model_path)
model = AutoModelForSequenceClassification.from_pretrained(local_model_path)

model.to(device)

end = time.time()
print(f"Model load time: {end - start:.2f} sec")

# -----------------------------
# 3. Prepare input
# -----------------------------
text = "This is a test sentence for AI performance."

inputs = tokenizer(text, return_tensors="pt").to(device)

# -----------------------------
# 4. Inference timing
# -----------------------------
start = time.time()

with torch.no_grad():
    outputs = model(**inputs)

end = time.time()
print(f"Inference time: {end - start:.4f} sec")

# -----------------------------
# 5. Training step (forward + backward)
# -----------------------------
labels = torch.tensor([1]).to(device)

start = time.time()

outputs = model(**inputs, labels=labels)
loss = outputs.loss

loss.backward()  # backprop

end = time.time()
print(f"Training step time: {end - start:.4f} sec")

# -----------------------------
# 6. GPU memory check (MPS doesn't show full stats)
# -----------------------------
print("Test completed.")