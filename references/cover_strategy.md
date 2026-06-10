# Cover Strategy Reference

Use this reference when deciding how to classify a video and how to shape the three covers.

## Video Types

| Type | Signals | Cover subject |
|---|---|---|
| `info_expression` | UI, charts, talking-head explanation, screen demos, AI/software/product reviews | screen, product, key object, readable headline |
| `object_operation` | hands, tools, parts, cooking/craft/repair steps, unboxing details | object, hands, tools, work surface |
| `lifestyle_scene` | person, street, travel, beauty, food, cinematic ambience, vlog scenes | real scene, person optional, mood-first image |

Priority: `object_operation` over `info_expression` over `lifestyle_scene`. If hands are doing a concrete action, classify as `object_operation`.

## Title Patterns

Chinese short-video covers usually work best with 4-10 characters:

- Pain point: `别再瞎买`, `效率翻倍`, `踩坑实测`
- Curiosity: `真有这么强?`, `结果意外`, `隐藏玩法`
- Outcome: `一键搞定`, `成片质感`, `新手也会`

English covers usually work best with 2-5 words:

- `Stop Wasting Time`
- `Worth It?`
- `Fast Setup`
- `Hidden Workflow`

## Text Rendering

Prefer model-rendered typography when the image model can write the target language reliably. The text is part of the composition, not an afterthought.

Use a two-level copy system:

- Primary title: 4-10 Chinese characters or 2-5 English words, the hook users notice first.
- Subtitle: 4-10 Chinese characters or 2-6 English words, clarifies what the video is actually about.

For Chinese tech covers, good pairings look like:

- `OpenClaw爆火` + `AI助手新范式`
- `不止是工具` + `可调度AI助手`
- `AI进入新阶段` + `从工具到队友`

If the generated text has typos, shorten the title first and rerun with simpler model-rendered text. Do not repair final covers with local title overlay; the cover and title must be generated together by the image model.

## Person Policy

Never let the image model invent a presenter, creator, or human face.

For talking-head videos:

- Use a no-person symbolic cover by default: product UI, terminal, risk/result symbols, microphone icon, timeline/checklist, or workflow diagram.
- If the cover needs a person, use a real frame/person cutout from the video or a user-uploaded portrait.
- If no clean person asset exists, do not make a fake portrait. Pick the no-person route.

The `extract_person_reference.py` helper can create a real-person reference crop from a frame. Treat it as a source asset for later compositing or image-reference workflows, not as permission to invent a new face.

## Variant Intent

`info-heavy`
: Maximize legibility and decision speed. Use a larger title, strong contrast, and a structured accent block. For software videos, generate an editorial tech cover with recognizable UI/product motifs, not a literal screenshot pasted into the center.

`visual-heavy`
: Make the subject feel premium. Use smaller text and let the generated scene, object, or product motif occupy more space.

`balanced`
: Keep title and subject equally important. This is the safest default when the video is ambiguous.

## Prompt Guidance For AI Image Generation

If using an image generator, preserve the real video subject. Do not replace a screen recording with a generic influencer portrait or abstract tech scene.

For screen/software videos:

- Use the real product name, UI shape, terminal/browser cues, code panes, workflow diagrams, or product mascot if present.
- Avoid raw screenshot thumbnails unless the user explicitly wants a screenshot cover.
- Use layered depth: hero product mark or UI panel, glow/rim light, subtle background grid, sharp foreground title space.
- Keep background UI and code as unreadable shapes when they are not the selected cover title.

Prompt structure:

1. Main subject from frames.
2. Scene or material details.
3. Lighting and color mood.
4. Selected title text using the OpenClaw `seedream.text` baseline wording: `主标题「...」` and `副标题「...」`.
5. High-impact vertical tech cover, readable mobile thumbnail.

Keep benchmark language out of routing decisions, but preserve the proven high-impact cover ingredients from the OpenClaw baseline: 3:4 vertical, title safety area, concrete hero subject, dark tech palette, layered background, and model-rendered title/subtitle.
