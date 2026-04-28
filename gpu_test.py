import time
import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification

# -----------------------------
# 1. Check device (GPU / CPU)
# -----------------------------
device = "mps" if torch.backends.mps.is_available() else "cpu"
print(f"Using device: {device}")

# -----------------------------
# 2. Load model from HuggingFace
# -----------------------------
model_name = "distilbert-base-uncased"

start = time.time()

tokenizer = AutoTokenizer.from_pretrained(model_name)
model = AutoModelForSequenceClassification.from_pretrained(model_name)

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