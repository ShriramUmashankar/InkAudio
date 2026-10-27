"""Fetch only PDF assets at image build time, never Qwen or Whisper."""
from pathlib import Path

from huggingface_hub import snapshot_download
from docling.models.stages.ocr.rapid_ocr_model import RapidOcrModel

root = Path("/opt/docling-models")
for repo, revision, patterns in [
    ("docling-project/docling-layout-heron", "8f39ad3c0b4c58e9c2d2c84a38465abf757272d8",
     ["*.json", "model.safetensors"]),
    ("docling-project/docling-models", "fc0f2d45e2218ea24bce5045f58a389aed16dc23",
     ["model_artifacts/tableformer/**"]),
]:
    snapshot_download(repo_id=repo, revision=revision, allow_patterns=patterns,
                      local_dir=root / repo.replace("/", "--"), max_workers=2)

# rapidocr==3.9.2 pins the OCR registry and its versioned v3.9.2 model URLs.
RapidOcrModel.download_models(backend="onnxruntime", local_dir=root / "RapidOcr")
