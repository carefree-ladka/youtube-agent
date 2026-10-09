"""Centralized prompt templates for all LLM interactions.

Keeping prompts in one place makes them easy to tune without touching service
logic. Each builder returns a fully-rendered prompt string.
"""

from __future__ import annotations

# --------------------------------------------------------------------------- #
# Script generation
# --------------------------------------------------------------------------- #

SCRIPT_SYSTEM = (
    "You are an award-winning YouTube scriptwriter and storyteller. "
    "You write spoken-word scripts that are engaging, clear, and natural to "
    "read aloud for a text-to-speech narrator. You avoid stage directions, "
    "emojis, markdown, and bracketed notes in the narration itself."
)

# Used for programming / algorithm / technical topics where correctness matters.
TECHNICAL_SCRIPT_SYSTEM = (
    "You are a senior software engineer and a brilliant technical educator. You "
    "explain programming, algorithms, and computer-science concepts with 100% "
    "factual ACCURACY and real substance - the way a top conference speaker "
    "would. You never oversimplify into something incorrect, and you never use "
    "vague or misleading analogies. You write clean spoken-word narration (no "
    "stage directions, markdown, or emojis)."
)


def _technical_block() -> str:
    """Extra rules that force accurate, substantive technical explanations."""
    return """
TECHNICAL ACCURACY & DEPTH (this is critical - do not ignore):
- Be 100% CORRECT. If you are not sure how it actually works, do not invent it.
- Explain the REAL mechanism concretely: name the actual steps, the data it
  tracks, and WHY it works. A developer should genuinely understand it after.
- State the single KEY insight explicitly, and when it helps, say the core
  operation or line of code in words (e.g. for Kadane's:
  "current = max of the number itself, or current plus the number; track the
  best current you've seen"). Mention time/space complexity if relevant.
- NO vague or misleading analogies. An analogy is allowed ONLY if it is
  technically precise. Prefer concrete specifics over cute comparisons.
- Cut ALL filler and empty hype. Every sentence must teach something true."""


def build_script_prompt(
    topic: str,
    tone: str,
    audience: str,
    target_minutes: int,
    language: str,
    technical: bool = False,
) -> str:
    """Prompt the model to produce a clean, TTS-ready narration script."""
    approx_words = target_minutes * 150  # ~150 spoken words per minute
    tech = _technical_block() if technical else ""
    return f"""Write a complete YouTube video narration script.

TOPIC: {topic}
TARGET LANGUAGE: {language}
TONE: {tone}
AUDIENCE: {audience}
TARGET LENGTH: about {target_minutes} minute(s) of speech (~{approx_words} words)

STRUCTURE REQUIREMENTS:
1. A strong 2-3 sentence HOOK that grabs attention in the first 10 seconds.
2. A short intro that states what the viewer will learn or gain.
3. A well-organized body with clear, logically ordered, CONCRETE points.
4. A concise, memorable conclusion.
5. A natural call-to-action (like, subscribe, comment) woven into the outro.
{tech}

WRITING RULES:
- Output ONLY the narration text that should be spoken aloud.
- Do NOT include scene directions, speaker labels, timestamps, headings,
  markdown, asterisks, or emojis.
- Use short, conversational sentences that flow smoothly when read by a
  text-to-speech voice.
- Be specific and genuinely useful - no filler, no empty hype.
- Write numbers and symbols as words where it aids natural speech.
- Do NOT add any preface or title like "Here is the script". Start directly with
  the first spoken word.

Begin the script now:"""


# --------------------------------------------------------------------------- #
# Short-form / Reel script generation
# --------------------------------------------------------------------------- #

SHORT_SCRIPT_SYSTEM = (
    "You are a viral short-form video scriptwriter for Instagram Reels, YouTube "
    "Shorts, and TikTok. You write tight, punchy, fast-paced spoken scripts that "
    "hook in the first second and hold attention to the last. You avoid stage "
    "directions, emojis, markdown, and bracketed notes in the narration."
)

# Technical short-form: punchy BUT correct and genuinely instructive.
TECHNICAL_SHORT_SCRIPT_SYSTEM = (
    "You are a senior software engineer who makes viral but TECHNICALLY ACCURATE "
    "short videos about programming and algorithms. You hook fast, then teach the "
    "real concept correctly in a few tight sentences - no misleading analogies, "
    "no filler. You avoid stage directions, emojis, markdown, and bracketed notes."
)


def build_short_script_prompt(
    topic: str,
    tone: str,
    audience: str,
    target_seconds: int,
    language: str,
    technical: bool = False,
) -> str:
    """Prompt the model for a tight, TTS-ready vertical short/reel script."""
    approx_words = max(int(target_seconds * 2.5), 25)  # ~2.5 spoken words/second
    tech = _technical_block() if technical else ""
    return f"""Write a punchy short-form VERTICAL video script (Reel / YouTube Short).

TOPIC: {topic}
TARGET LANGUAGE: {language}
TONE: {tone}
AUDIENCE: {audience}
TARGET LENGTH: about {target_seconds} seconds of speech (~{approx_words} words). Stay close to this - it MUST be short.

STRUCTURE:
1. HOOK (first line): a scroll-stopping opener in the first 1-2 seconds - a bold
   claim, a question, or a surprising fact. No slow warm-up.
2. VALUE: the real substance - 2-4 rapid, CONCRETE, correct points that actually
   explain the concept. Every sentence earns its place. No filler, no "in this video".
3. PAYOFF + CTA: a satisfying, accurate takeaway, then a quick call to action
   such as "follow for more" or "save this".
{tech}

WRITING RULES:
- Output ONLY the spoken narration text. No labels, timestamps, headings,
  markdown, asterisks, or emojis.
- Very short, snappy sentences with high energy. Speak directly to "you".
- Front-load the most interesting idea; keep momentum throughout.
- Write numbers and symbols as words where it aids natural speech.
- Do NOT add any preface, title, or quotation marks around lines. Start directly
  with the first spoken word (the hook).

Begin the script now:"""


# --------------------------------------------------------------------------- #
# Metadata generation (YouTube + Instagram + LinkedIn)
# --------------------------------------------------------------------------- #

METADATA_SYSTEM = (
    "You are a world-class YouTube growth strategist, SEO specialist, and social "
    "media copywriter who has grown channels to millions of views. You understand "
    "search intent, click-through psychology, and how each platform's algorithm "
    "surfaces content. Every title, tag, and hashtag you write is intentional, "
    "specific, and chosen to maximize genuine reach - never generic filler. "
    "You always respond with valid JSON only."
)


def build_metadata_prompt(topic: str, script_excerpt: str, language: str) -> str:
    """Prompt the model to return high-quality cross-platform metadata as JSON."""
    return f"""Create publishing metadata engineered for maximum reach and CTR.

TOPIC: {topic}
TARGET LANGUAGE: {language}
SCRIPT EXCERPT (for context):
\"\"\"
{script_excerpt}
\"\"\"

QUALITY BAR (this matters more than hitting any count):
- TITLES: Use proven high-CTR patterns - curiosity gaps, specific numbers,
  clear benefit/outcome, or a bold claim. Front-load the most searched keyword.
  Under 70 characters. No clickbait you can't back up. Make each option
  genuinely different in angle (how-to, listicle, mistake-to-avoid, result).
- DESCRIPTION: Hook in the first 2 lines (shown before "...more"). Then a
  keyword-rich summary of what the viewer learns, then a call-to-action. Write
  it to rank in search - weave the main keyword and close variants in naturally.
- TAGS (YouTube): real phrases people actually type into search. Blend three
  buckets: (1) broad head terms, (2) specific long-tail phrases, (3) close
  variations/synonyms. Every tag must be relevant to THIS video.
- HASHTAGS: relevant and reach-oriented. Blend high-volume discovery tags with
  precise niche tags the target audience follows. No unrelated trend-jacking.

Return ONLY a JSON object with EXACTLY this shape (no commentary):
{{
  "titles": ["6-8 distinct, high-CTR YouTube title options, best first"],
  "youtube": {{
    "title": "the single strongest title from the list",
    "description": "SEO-optimized 3-4 paragraph description: strong 2-line hook, keyword-rich summary, then CTA",
    "tags": ["20-30 relevant YouTube search tags, lowercase, no # symbol, mixing broad + long-tail + variants"],
    "hashtags": ["10-15 relevant YouTube hashtags each starting with #"],
    "chapters": ["optional list like '00:00 Intro' - may be empty"]
  }},
  "instagram": {{
    "caption": "a scroll-stopping caption with a hook line, value, and CTA, plus 1-2 tasteful emojis",
    "hashtags": ["25-30 relevant Instagram hashtags each starting with #, mixing high-reach, niche, and community tags"]
  }},
  "linkedin": {{
    "post": "a professional, insight-driven LinkedIn post with a strong opening line and a takeaway (no clickbait)",
    "hashtags": ["10-12 relevant professional LinkedIn hashtags each starting with #"]
  }},
  "keywords": ["12-15 core SEO keywords/phrases that match real search intent"]
}}

Rules:
- Valid JSON only. No trailing commas. No markdown fences.
- No duplicates and NO generic filler - every item must earn its place by being
  relevant to this specific topic and useful for discovery.
- Prefer fewer excellent tags over many weak ones, but aim for the ranges above."""


# --------------------------------------------------------------------------- #
# Metadata expansion (quality top-up when a list comes back short)
# --------------------------------------------------------------------------- #

METADATA_EXPANSION_SYSTEM = (
    "You are a YouTube SEO and social discovery expert. You generate additional "
    "high-quality, specific, relevant tags and hashtags that help content get "
    "found. You never produce generic filler or anything off-topic. You always "
    "respond with valid JSON only."
)


def build_metadata_expansion_prompt(
    topic: str,
    title: str,
    needs: dict[str, int],
    existing: dict[str, list[str]],
) -> str:
    """Ask for N MORE genuinely relevant items for only the lists that are short.

    ``needs`` maps a field name to how many additional items are wanted.
    ``existing`` maps the same field names to items already chosen (to avoid
    duplicates).
    """
    return f"""We need MORE high-quality, relevant discovery metadata for this video.

TOPIC: {topic}
TITLE: {title}

For each field below, generate the requested number of ADDITIONAL items that are
specific and genuinely relevant to this exact topic. Every item must help real
users discover this video. Do NOT repeat any existing item. Do NOT add generic,
off-topic, or filler tags.

HOW MANY MORE ARE NEEDED (field: count):
{_format_needs(needs)}

ALREADY USED (do not repeat these):
{_format_existing(existing)}

Return ONLY a JSON object with these keys (include a key only if it was requested):
{{
  "youtube_tags": ["additional lowercase search tags, no # symbol"],
  "youtube_hashtags": ["additional #hashtags"],
  "instagram_hashtags": ["additional #hashtags"],
  "linkedin_hashtags": ["additional #hashtags"],
  "keywords": ["additional SEO keywords/phrases"]
}}

Rules: valid JSON only, no markdown fences, no duplicates, no filler."""


def _format_needs(needs: dict[str, int]) -> str:
    return "\n".join(f"- {field}: {count} more" for field, count in needs.items() if count > 0)


def _format_existing(existing: dict[str, list[str]]) -> str:
    lines = []
    for field, items in existing.items():
        if items:
            lines.append(f"- {field}: {', '.join(items)}")
    return "\n".join(lines) if lines else "- (none yet)"


# --------------------------------------------------------------------------- #
# Thumbnail concept generation
# --------------------------------------------------------------------------- #

THUMBNAIL_SYSTEM = (
    "You are a thumbnail designer. You write short, punchy overlay text that "
    "stays TRUE to the video's actual subject, and you describe background "
    "imagery that literally matches the video's topic and domain. You never "
    "invent an unrelated slogan and never drop the core keywords. You always "
    "respond with valid JSON only."
)


def build_thumbnail_prompt(topic: str, title: str) -> str:
    """Prompt the model for on-topic thumbnail text + visual direction as JSON."""
    return f"""Design a thumbnail for this specific video. Stay faithful to the topic.

TOPIC (source of truth - do NOT change its meaning): {topic}
TITLE (for tone only): {title}

Return ONLY a JSON object with EXACTLY this shape:
{{
  "headline": "2-5 WORD headline, UPPERCASE. It MUST contain the main keyword(s) of the TOPIC and keep its meaning. You may shorten or make it punchy, but do NOT replace it with an unrelated phrase.",
  "subtext": "optional 2-6 word supporting line that adds context (may be empty)",
  "accent_word": "one word that appears verbatim in the headline, to highlight",
  "image_prompt": "a detailed background-image prompt that LITERALLY depicts the topic's real subject and domain (see rules). Text-free scene.",
  "mood": "one or two words for the color mood (e.g. 'bold energetic')"
}}

HEADLINE RULES:
- Keep the core keywords from the TOPIC. Example: topic 'useState in React' ->
  good: 'REACT USESTATE HOOK' or 'USESTATE EXPLAINED'; BAD: 'STATE POWERED UI'.
- The accent_word must be one of the words in the headline (ideally the keyword).

IMAGE RULES (must match the topic's field):
- Identify the topic's domain and depict it literally and relevantly.
- Programming/tech topics -> code on a screen, an IDE/code editor, terminal,
  UI components, developer desk setup, abstract code/data - NOT random city
  streets, NOT unrelated scenes.
- Cooking -> food/kitchen; fitness -> gym/body; finance -> charts/money; etc.
- Keep it a clean, text-free background with empty space in the center.

Rules: valid JSON only, no markdown fences, no commentary."""


# --------------------------------------------------------------------------- #
# Storyboard generation (generic, data-driven video)
# --------------------------------------------------------------------------- #

STORYBOARD_SYSTEM = (
    "You are a short-form video director and motion designer. You turn a "
    "narration script into a GENERIC visual storyboard: a timeline of scenes, "
    "each with a few on-screen visual elements. You never assume a specific "
    "rendering technology and you only use these element types: text, svg, image, "
    "code, diagram, shape, bullets, stat, quote. You always respond with valid "
    "JSON only."
)


_STORYBOARD_CODE_RULES = """CODE RULES (important for engagement):
- Since this IS a programming/technical topic, include 1-2 scenes with a "code"
  element showing a SHORT, CORRECT, directly-relevant snippet that demonstrates
  the idea.
- Keep code to a MAXIMUM of 8 lines and each line under ~40 characters so it is
  readable on a vertical screen. Set "language" (e.g. "javascript", "python").
- FORMAT the code properly: put each statement on its OWN line using "\\n", with
  2-space indentation for nested blocks. NEVER put the whole snippet on one line.
- Use MODERN, idiomatic syntax. For JavaScript/TypeScript use ES6+: prefer
  "const" (use "let" ONLY when the variable is reassigned), use arrow functions
  where natural, and never use "var".
- Pair each code scene with a brief "text" headline that names what the snippet
  shows, and let the narration explain it."""

_STORYBOARD_NO_CODE_RULE = """CONTENT RULE (critical):
- This is NOT a programming/technical topic. Do NOT use the "code" element type
  at all, and do NOT invent code. Use text, bullets, stat, quote, diagram, image,
  and shape to tell the story visually."""


def build_storyboard_prompt(
    topic: str,
    script: str,
    orientation: str,
    target_seconds: int,
    language: str,
    technical: bool = False,
) -> str:
    """Prompt the model to produce a generic, data-driven storyboard as JSON."""
    frame = (
        "vertical 9:16 (portrait)" if orientation == "portrait" else "horizontal 16:9 (landscape)"
    )
    code_doc = (
        '- "code": a REAL code snippet. Fields: language, code. Use "\\n" for newlines.'
        if technical
        else '- (do NOT use a "code" element for this topic)'
    )
    code_rules = _STORYBOARD_CODE_RULES if technical else _STORYBOARD_NO_CODE_RULE
    variety = (
        "a headline, then bullets, then a stat, then code, then a diagram, then a quote"
        if technical
        else "a headline, then bullets, then a stat, then a diagram, then a quote, then an image"
    )
    # Aim for roughly one scene every ~4.5s so videos feel dense, not like three
    # slides holding for the whole narration.
    min_scenes = max(5, round(target_seconds / 4.5))
    max_scenes = max(min_scenes + 2, round(target_seconds / 3))
    return f"""Create a visual STORYBOARD for a {frame} video narrating the script below.

TOPIC: {topic}
TARGET LANGUAGE: {language}
APPROX TOTAL DURATION: {target_seconds} seconds
NARRATION SCRIPT:
\"\"\"
{script}
\"\"\"

Break the narration into a sequence of SCENES that visually support what is being
said at that moment. For each scene choose the most fitting visual element(s).

Return ONLY a JSON object with EXACTLY this shape:
{{
  "scenes": [
    {{
      "id": "scene-1",
      "duration": 4,
      "transition": "slide",
      "elements": [
        {{ "type": "text", "content": "SHORT on-screen phrase (2-6 words)", "style": {{ "role": "headline" }} }},
        {{ "type": "image", "image_prompt": "detailed, literal description of a relevant background image - NO text in the image" }}
      ]
    }}
  ]
}}

ELEMENT TYPES you may use (choose what fits the moment):
- "text": a short on-screen phrase. Fields: content, style.role in
  ["title","headline","caption","bullet"].
- "svg": a PREFERRED, topic-specific vector visual authored just for this scene -
  a flat illustration, a mock UI/app/phone/browser/editor "screen", a labelled
  concept diagram, or a simple chart. Fields: image_prompt (describe EXACTLY what
  to draw, concrete to this scene's idea), style.svg_kind in
  ["illustration","screen","diagram","chart"]. Prefer "svg" over "image" for most
  scenes so every scene looks different and on-topic.
- "image": a generated PHOTOGRAPHIC background. Fields: image_prompt (literal,
  relevant to the topic's domain, NO text/letters in the image). Use only when a
  photo-real look beats a vector illustration.
{code_doc}
- "diagram": a simple concept diagram. Fields: data = {{ "kind": "flow"|"list",
  "nodes": ["A","B","C"] }}.
- "bullets": 2-4 ULTRA-short key points. Fields: data = ["point one","point two",
  "point three"] (each 2-5 words).
- "stat": one big number/metric with a label. Fields: content = the value (e.g.
  "O(n)", "100x", "3"), data = the label (e.g. "time complexity").
- "quote": a short, punchy key takeaway (one line). Fields: content.
- "shape": a decorative accent. Fields: shape in ["blob","circle","grid","wave"].

SCENE COUNT (IMPORTANT - keep it dense and fast-moving):
- Produce BETWEEN {min_scenes} AND {max_scenes} scenes. Fewer than {min_scenes}
  is TOO SLOW and boring - a short clip must change visuals every few seconds.
- Each scene is 3-5 seconds; durations should ADD UP to roughly {target_seconds}
  (they will be auto-adjusted to the real audio length).

VARIETY RULE (keep it visually interesting):
- Use a MIX of element types across scenes - e.g. {variety}. Do NOT use the same
  element type in every scene. Pick whichever type best fits each moment.
- Across the whole storyboard you MUST use at least 3-4 DIFFERENT element types,
  including at least ONE "bullets" scene and at least ONE "stat" OR "quote" scene.
- Do NOT just restate the narration as a headline on every scene. Each scene
  should ADD something: a key point list, a number, a diagram, a visual, a
  takeaway - not a paraphrase of what the voice is already saying.

{code_rules}

LAYOUT / CONTENT RULES:
- Each scene may contain AT MOST TWO flow elements from (text, code, diagram) so
  nothing is crowded - prefer ONE short headline + ONE visual (code/diagram/image).
- At most ONE visual background ("svg" OR "image") per scene; keep text very
  short and punchy (2-6 words), not full sentences.
- Give MOST scenes an "svg" visual whose image_prompt is specific to THAT scene's
  point, so no two scenes look alike. Vary svg_kind across the video (some
  illustrations, a mock screen, a diagram, a chart).
- An "image" image_prompt (photographic) must contain NO text, words, letters,
  logos, or watermarks.
- Valid JSON only. No markdown fences. No commentary."""


# --------------------------------------------------------------------------- #
# Code snippet generation (guarantees a code scene for technical topics)
# --------------------------------------------------------------------------- #

CODE_SNIPPET_SYSTEM = (
    "You are a senior software engineer. You write tiny, correct, idiomatic code "
    "snippets that demonstrate a concept clearly. For JavaScript/TypeScript you "
    "use modern ES6+ (const by default, arrow functions, no var). You always "
    "respond with valid JSON only."
)


def build_code_snippet_prompt(topic: str) -> str:
    """Prompt for ONE short, correct, well-formatted code snippet as JSON."""
    return f"""Write ONE short code snippet that best demonstrates this topic.

TOPIC: {topic}

Return ONLY a JSON object with EXACTLY this shape:
{{
  "language": "the language, e.g. javascript | python | typescript",
  "headline": "a 2-5 word UPPERCASE label for the snippet (e.g. 'A CLOSURE IN ACTION')",
  "code": "the snippet, with real newlines as \\n and 2-space indentation"
}}

RULES:
- Maximum 8 lines, each under ~40 characters (it must fit a vertical phone screen).
- Correct and runnable-looking; demonstrate the core idea, nothing extra.
- JavaScript/TypeScript: modern ES6+ only - use const (let only if reassigned),
  arrow functions where natural, NEVER var.
- Format with proper line breaks (\\n) and indentation. Not one long line.
- Valid JSON only. No markdown fences. No commentary."""


# --------------------------------------------------------------------------- #
# Topic classification (is this a programming / technical topic?)
# --------------------------------------------------------------------------- #

TOPIC_CLASSIFY_SYSTEM = (
    "You are a precise topic classifier. You decide whether a video topic is a "
    "SOFTWARE/PROGRAMMING/computer-science topic for which showing a real code "
    "snippet would genuinely help (e.g. algorithms, data structures, a language "
    "feature, an API, a framework). Topics like cars, history, cooking, finance, "
    "fitness, biology, or general science are NOT programming topics. You always "
    "respond with valid JSON only."
)


def build_topic_classify_prompt(topic: str) -> str:
    """Prompt the model to classify a topic as technical (code-worthy) or not."""
    return f"""Classify this video topic.

TOPIC: {topic}

Return ONLY this JSON object:
{{
  "technical": true or false,
  "reason": "a few words",
  "code_language": "the most relevant programming language if technical (e.g. 'javascript', 'python'), else null"
}}

Rules:
- "technical" is true ONLY if the topic is about software, programming, coding,
  algorithms, data structures, computer science, or a specific tech/dev tool
  where a CODE snippet would actually help explain it.
- Non-software topics (cars, history, sports, cooking, finance, nature, etc.)
  must be false, even if they mention numbers or systems.
- Valid JSON only. No markdown, no commentary."""


# --------------------------------------------------------------------------- #
# SVG scene visuals (topic-specific vector illustrations / screens / diagrams)
# --------------------------------------------------------------------------- #

SVG_ASSET_SYSTEM = (
    "You are a senior motion/vector illustrator. You hand-write clean, modern, "
    "flat-design SVG markup for a single full-screen video background. You use "
    "simple primitives (rect, circle, ellipse, path, line, polygon, polyline, "
    "linearGradient, radialGradient, g) and gradients, never raster images, never "
    "scripts, never external resources, never <foreignObject>. You respond with "
    "SVG MARKUP ONLY - starting with <svg and ending with </svg>, nothing else."
)

_SVG_KIND_GUIDE: dict[str, str] = {
    "illustration": (
        "A bold, flat, conceptual ILLUSTRATION of the idea (metaphor, objects, "
        "scene). Clean shapes, generous negative space, 2-4 focal elements."
    ),
    "screen": (
        "A stylised MOCK UI SCREEN relevant to the idea: a browser window, phone, "
        "app, dashboard, code editor, or terminal. Include a title bar, panels, "
        "and placeholder rows/blocks. Minimal, legible labels are allowed here."
    ),
    "diagram": (
        "A clear concept DIAGRAM: 2-5 labelled boxes/nodes connected by arrows or "
        "lines (flow, cycle, hierarchy, or before/after). Short labels allowed."
    ),
    "chart": (
        "A simple, clean CHART that fits the idea: bar, line, donut, or progress. "
        "A few data marks with an axis/baseline. Short numeric labels allowed."
    ),
}


def build_svg_asset_prompt(
    *,
    topic: str,
    brief: str,
    kind: str,
    width: int,
    height: int,
    palette: list[str],
    accent: str,
    language: str = "English",
) -> str:
    """Prompt the model to hand-author one self-contained SVG for a scene.

    ``brief`` is the scene's visual description; ``kind`` is one of
    illustration/screen/diagram/chart; colors come from the video's theme so the
    SVG matches the rest of the video.
    """
    kind_guide = _SVG_KIND_GUIDE.get(kind, _SVG_KIND_GUIDE["illustration"])
    colors = ", ".join(palette) if palette else "#0F2027, #2C5364"
    allow_text = kind in ("screen", "diagram", "chart")
    text_rule = (
        "- You MAY include a FEW very short labels (<= 3 words each) where it adds "
        "clarity, but keep them small and sparse - burned-in captions are added "
        "separately."
        if allow_text
        else "- Do NOT include any <text> - this is a pure illustration; captions "
        "are added separately."
    )
    return f"""Hand-write ONE self-contained SVG to fill a {width}x{height} video background.

VIDEO TOPIC: {topic}
THIS SCENE SHOULD SHOW: {brief}
VISUAL KIND: {kind} - {kind_guide}
LABEL LANGUAGE (if any text): {language}

DESIGN:
- Use viewBox="0 0 {width} {height}" and width="100%" height="100%".
- Fill the WHOLE canvas edge-to-edge (start with a full-size background rect or
  gradient). Leave the lower ~22% visually calmer (subtitles sit there).
- Theme colors (use these, build gradients from them): {colors}. Accent: {accent}.
- Modern flat design: smooth shapes, soft gradients, subtle depth. High contrast,
  but not pure white backgrounds.
{text_rule}

HARD RULES:
- Output SVG MARKUP ONLY: start with <svg ...> and end with </svg>. No markdown
  fences, no explanation, no XML prolog.
- Pure vector only: no <image>, no <script>, no <foreignObject>, no external URLs,
  no event handlers (onload etc.), no CSS @import.
- Keep it under ~120 elements so it renders fast."""
