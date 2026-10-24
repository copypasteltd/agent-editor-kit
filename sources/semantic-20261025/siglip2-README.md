---
license: apache-2.0
tags:
- vision
widget:
  - src: >-
      https://huggingface.co/datasets/huggingface/documentation-images/resolve/main/bee.jpg
    candidate_labels: bee in the sky, bee on the flower
    example_title: Bee
library_name: transformers
pipeline_tag: zero-shot-image-classification
---

# SigLIP 2 Base

[SigLIP 2](https://huggingface.co/papers/2502.14786) extends the pretraining objective of
[SigLIP](https://huggingface.co/papers/2303.15343) with prior, independently developed techniques
into a unified recipe, for improved semantic understanding, localization, and dense features.

## Intended uses

You can use the raw model for tasks like zero-shot image classification and
image-text retrieval, or as a vision encoder for VLMs (and other vision tasks).

Here is how to use this model to perform zero-shot image classification:

```python
from transformers import pipeline

# load pipeline
ckpt = "google/siglip2-base-patch16-224"
image_classifier = pipeline(model=ckpt, task="zero-shot-image-classification")

# load image and candidate labels
url = "http://images.cocodataset.org/val2017/000000039769.jpg"
candidate_labels = ["2 cats", "a plane", "a remote"]

# run inference
outputs = image_classifier(image, candidate_labels)
print(outputs)
```

You can encode an image using the Vision Tower like so:

```python
import torch
from transformers import AutoModel, AutoProcessor
from transformers.image_utils import load_image

# load the model and processor
ckpt = "google/siglip2-base-patch16-224"
model = AutoModel.from_pretrained(ckpt, device_map="auto").eval()
processor = AutoProcessor.from_pretrained(ckpt)

# load the image
image = load_image("https://huggingface.co/datasets/merve/coco/resolve/main/val2017/000000000285.jpg")
inputs = processor(images=[image], return_tensors="pt").to(model.device)

# run infernece
with torch.no_grad():
    image_embeddings = model.get_image_features(**inputs)    

print(image_embeddings.shape)
```

For more code examples, we refer to the [siglip documentation](https://huggingface.co/transformers/main/model_doc/siglip.html#).

## Training procedure

SigLIP 2 adds some clever training objectives on top of SigLIP:

1. Decoder loss
2. Global-local and masked prediction loss
3. Aspect ratio and resolution adaptibility 

### Training data

SigLIP 2 is pre-trained on the WebLI dataset [(Chen et al., 2023)](https://arxiv.org/abs/2209.06794).

### Compute

The model was trained on up to 2048 TPU-v5e chips.

## Evaluation results

Evaluation of SigLIP 2 is shown below (taken from the paper).

![Evaluation Table](https://huggingface.co/datasets/huggingface/documentation-images/resolve/main/blog/sg2-blog/eval_table.png)

### BibTeX entry and citation info

```bibtex
@misc{tschannen2025siglip2multilingualvisionlanguage,
      title={SigLIP 2: Multilingual Vision-Language Encoders with Improved Semantic Understanding, Localization, and Dense Features}, 
      author={Michael Tschannen and Alexey Gritsenko and Xiao Wang and Muhammad Ferjad Naeem and Ibrahim Alabdulmohsin and Nikhil Parthasarathy and Talfan Evans and Lucas Beyer and Ye Xia and Basil Mustafa and Olivier Hénaff and Jeremiah Harmsen and Andreas Steiner and Xiaohua Zhai},
      year={2025},
      eprint={2502.14786},
      archivePrefix={arXiv},
      primaryClass={cs.CV},
      url={https://arxiv.org/abs/2502.14786}, 
}
```
