# API Contract

Use this when connecting the skill to a multimodal understanding API or an image-generation API.

## Multimodal Understanding API

The bundled `scripts/analyze_with_vlm.py` adapter supports Doubao Seed responses by default:

```text
VCG_VLM_API_URL=https://ark.cn-beijing.volces.com/api/v3/responses
VCG_VLM_API_KEY=...
VCG_VLM_MODEL=doubao-seed-2-0-pro-260215
```

Doubao request shape:

```json
{
  "model": "doubao-seed-2-0-pro-260215",
  "input": [
    {
      "role": "user",
      "content": [
        {"type": "input_image", "image_url": "data:image/jpeg;base64,..."},
        {"type": "input_text", "text": "..."}
      ]
    }
  ]
}
```

The adapter can also use an OpenAI-style chat endpoint by passing `--provider openai`.

Expected response can be either a direct JSON object, a Doubao responses payload containing output text, or a chat-completions response whose `choices[0].message.content` is JSON.

Required JSON output:

```json
{
  "analysis": {
    "video_type": "info_expression",
    "subject_strategy": "screen-or-product",
    "key_elements": ["OpenClaw", "Claude Code", "AI assistant"],
    "mood": "premium software launch mood",
    "content_summary": "What the video explains in one sentence.",
    "recommended_frame": "frames/frame_06.jpg"
  },
  "titles": ["Title 1", "Title 2", "Title 3"]
}
```

## Image Generation API

The bundled `scripts/generate_ai_covers.py` adapter supports Doubao Seedream by default:

```text
VCG_IMAGE_API_URL=https://ark.cn-beijing.volces.com/api/v3/images/generations
VCG_IMAGE_API_KEY=...
VCG_IMAGE_MODEL=doubao-seedream-5-0-260128
VCG_IMAGE_SIZE=2K
```

Default request shape:

```json
{
  "model": "doubao-seedream-5-0-260128",
  "prompt": "...",
  "sequential_image_generation": "disabled",
  "response_format": "url",
  "size": "2K",
  "stream": false,
  "watermark": false,
  "n": 1
}
```

The adapter can parse these response shapes automatically:

- `{"data": [{"b64_json": "..."}]}`
- `{"data": [{"url": "https://..."}]}`
- `{"b64_json": "..."}`
- `{"base64": "..."}`
- `{"image": "...base64 or data URL..."}`
- `{"url": "https://..."}`
- `{"image_url": "https://..."}`

For a custom response, set `VCG_IMAGE_RESPONSE_PATH`, for example:

```text
VCG_IMAGE_RESPONSE_PATH=result.images.0.url
VCG_IMAGE_RESPONSE_PATH=payload.image_base64
```

## What To Ask The User For

Ask for these details when the API is not already known:

- VLM endpoint, model name, auth header style, and one sample request/response.
- Image endpoint, model name, supported size/aspect-ratio parameter, auth header style, and one sample request/response.
- Whether the image API supports reference images. If yes, ask for the exact field name and accepted format.
- Whether the image API can reliably render Chinese text. For this workflow, final covers must still use model-rendered text; if text is unreliable, simplify the title/subtitle and regenerate instead of using local overlay.
