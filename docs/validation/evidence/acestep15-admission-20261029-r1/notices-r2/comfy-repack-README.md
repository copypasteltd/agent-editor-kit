---
license: apache-2.0
tags:
- comfyui
- diffusion-single-file
base_model:
- ACE-Step/Ace-Step1.5
pipeline_tag: text-to-audio
---

# ACE-Step 1.5

Repackaged model files for ComfyUI.

Original model repository: https://huggingface.co/ACE-Step/Ace-Step1.5

Place the files in the following folders:

```
📂 ComfyUI/
├── 📂 models/
│   ├── 📂 checkpoints/
│   │   └── ace_step_1.5_turbo_aio.safetensors
│   ├── 📂 diffusion_models/
│   │   ├── acestep_v1.5_base.safetensors
│   │   ├── acestep_v1.5_turbo.safetensors
│   │   ├── acestep_v1.5_xl_base_bf16.safetensors
│   │   ├── acestep_v1.5_xl_sft_bf16.safetensors
│   │   └── acestep_v1.5_xl_turbo_bf16.safetensors
│   ├── 📂 text_encoders/
│   │   ├── qwen_0.6b_ace15.safetensors
│   │   ├── qwen_1.7b_ace15.safetensors
│   │   └── qwen_4b_ace15.safetensors
│   ├── 📂 vae/
│   │   └── ace_1.5_vae.safetensors
```

---

These are repackaged files to work with ComfyUI, original model repo is: https://huggingface.co/ACE-Step/Ace-Step1.5

## Workflows

<table>
<thead>
<tr><th align="center" valign="middle" style="text-align:center;vertical-align:middle">Workflow</th><th colspan="2" align="center" valign="middle" style="text-align:center;vertical-align:middle">Thumb / Preview</th></tr>
</thead>
<tbody>
<tr><td align="center" valign="middle" style="text-align:center;vertical-align:middle"><a href="https://github.com/Comfy-Org/workflow_templates/blob/main/templates/audio_ace_step1_5_xl_turbo.json">ACE-Step 1.5XL Turbo: Text to Music</a></td><td colspan="2" align="center" valign="middle" style="text-align:center;vertical-align:middle"><a href="https://github.com/Comfy-Org/workflow_templates/blob/main/templates/audio_ace_step1_5_xl_turbo.json"><img src="https://raw.githubusercontent.com/Comfy-Org/workflow_templates/main/templates/audio_ace_step1_5_xl_turbo-1.webp" width="200" height="200" alt="ACE-Step 1.5XL Turbo: Text to Music"></a></td></tr>
<tr><td align="center" valign="middle" style="text-align:center;vertical-align:middle"><a href="https://github.com/Comfy-Org/workflow_templates/blob/main/templates/audio_ace_step1_5_xl_sft.json">ACE-Step 1.5XL SFT： Text to Music</a></td><td colspan="2" align="center" valign="middle" style="text-align:center;vertical-align:middle"><a href="https://github.com/Comfy-Org/workflow_templates/blob/main/templates/audio_ace_step1_5_xl_sft.json"><img src="https://raw.githubusercontent.com/Comfy-Org/workflow_templates/main/templates/audio_ace_step1_5_xl_sft-1.webp" width="200" height="200" alt="ACE-Step 1.5XL SFT： Text to Music"></a></td></tr>
<tr><td align="center" valign="middle" style="text-align:center;vertical-align:middle"><a href="https://github.com/Comfy-Org/workflow_templates/blob/main/templates/audio_ace_step_1_5_checkpoint.json">ACE-Step 1.5 Music Generation AIO</a></td><td colspan="2" align="center" valign="middle" style="text-align:center;vertical-align:middle"><audio controls preload="none"><source src="https://raw.githubusercontent.com/Comfy-Org/workflow_templates/main/templates/audio_ace_step_1_5_checkpoint-1.mp3" type="audio/mpeg"></audio></td></tr>
<tr><td align="center" valign="middle" style="text-align:center;vertical-align:middle"><a href="https://github.com/Comfy-Org/workflow_templates/blob/main/templates/audio_ace_step1_5_xl_base.json">ACE-Step 1.5XL Base: Text to Music</a></td><td colspan="2" align="center" valign="middle" style="text-align:center;vertical-align:middle"><a href="https://github.com/Comfy-Org/workflow_templates/blob/main/templates/audio_ace_step1_5_xl_base.json"><img src="https://raw.githubusercontent.com/Comfy-Org/workflow_templates/main/templates/audio_ace_step1_5_xl_base-1.webp" width="200" height="200" alt="ACE-Step 1.5XL Base: Text to Music"></a></td></tr>
<tr><td align="center" valign="middle" style="text-align:center;vertical-align:middle"><a href="https://github.com/Comfy-Org/workflow_templates/blob/main/templates/audio_ace_step_1_5_split.json">ACE-Step 1.5 Music Generation Workflow</a></td><td colspan="2" align="center" valign="middle" style="text-align:center;vertical-align:middle"><audio controls preload="none"><source src="https://raw.githubusercontent.com/Comfy-Org/workflow_templates/main/templates/audio_ace_step_1_5_split-1.mp3" type="audio/mpeg"></audio></td></tr>
<tr><td align="center" valign="middle" style="text-align:center;vertical-align:middle"><a href="https://github.com/Comfy-Org/workflow_templates/blob/main/templates/audio_ace_step_1_5_split_llm.json">ACE-Step 1.5 AI Lyric Song Generation</a></td><td colspan="2" align="center" valign="middle" style="text-align:center;vertical-align:middle"><audio controls preload="none"><source src="https://raw.githubusercontent.com/Comfy-Org/workflow_templates/main/templates/audio_ace_step_1_5_split_llm-1.mp3" type="audio/mpeg"></audio></td></tr>
<tr><td align="center" valign="middle" style="text-align:center;vertical-align:middle"><a href="https://github.com/Comfy-Org/workflow_templates/blob/main/templates/audio_ace_step_1_5_split_4b.json">ACE-Step 1.5 Music Generation (4B LLM )</a></td><td colspan="2" align="center" valign="middle" style="text-align:center;vertical-align:middle"><audio controls preload="none"><source src="https://raw.githubusercontent.com/Comfy-Org/workflow_templates/main/templates/audio_ace_step_1_5_split_4b-1.mp3" type="audio/mpeg"></audio></td></tr>
</tbody>
</table>