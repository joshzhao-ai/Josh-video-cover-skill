# Style Reference Workflow

Use this workflow when adding the user's GPT Image 2 covers to the skill.

## Core idea

Do not treat every good cover as a separate prompt template. Group covers into a small set of reusable **style families**. A family captures visual grammar:

- what kind of hook leads the cover
- title hierarchy and typography
- portrait scale and placement
- palette and material treatment
- the proof object that makes the promise feel credible
- separate `3:4` and `4:3` composition behavior

The image files are few-shot references, not training data. The skill must still supply the current video's content, portrait, exact copy, and factual constraints.

## Reference roles

Keep roles explicit and ordered in every Image 2 call:

1. `identity_reference`: the user's portrait or a selected video frame
2. `selected_vertical_reference`: the selected 3:4 cover, only when generating its 4:3 continuation
3. `content_reference`: an official logo, product, screenshot, document, or object that must appear accurately
4. `style_reference`: one ratio-matched cover from the selected style family

Use one style reference by default. A second style reference is acceptable only when both belong to the same family. Too many visual references average out the style and increase content leakage.

For branded products, models, apps, and tools, obtain `content_reference` from an official source or from the user. Never crop a logo from another creator's cover. Content accuracy comes from `content_reference`; visual energy comes from `style_reference`.

## Registering a family

1. Put the selected images in `assets/style_references/`.
2. Prefer a paired `3:4` and `4:3` example.
3. Add one entry to `references/style_profiles.json`.
4. Describe the transferable visual DNA, not the source cover's subject.
5. State when the family should and should not be selected.
6. State a copy policy: primary length, optional promise line, and whether a proof card is allowed.
7. Validate that each registered image exists and has the declared ratio.

## Content leakage guard

Every prompt that uses a style reference must say:

> Learn only hierarchy, composition, typography, palette, material treatment, and density. Do not copy the reference image's words, person identity, facts, notebook text, UI text, logos, or subject matter.

Replace all source content with verified information from the current video.

## What to learn from feedback

Record feedback at the family level:

- selected or rejected
- thumbnail readability
- hook strength
- identity fidelity
- content leakage
- text accuracy
- whether the family matched the video's emotional tone

Do not conclude that a family is universally good from one winning image. Promote it only after it wins across at least three different videos or topics.
