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


def build_script_prompt(
    topic: str,
    tone: str,
    audience: str,
    target_minutes: int,
    language: str,
) -> str:
    """Prompt the model to produce a clean, TTS-ready narration script."""
    approx_words = target_minutes * 150  # ~150 spoken words per minute
    return f"""Write a complete YouTube video narration script.

TOPIC: {topic}
TARGET LANGUAGE: {language}
TONE: {tone}
AUDIENCE: {audience}
TARGET LENGTH: about {target_minutes} minute(s) of speech (~{approx_words} words)

STRUCTURE REQUIREMENTS:
1. A strong 2-3 sentence HOOK that grabs attention in the first 10 seconds.
2. A short intro that states what the viewer will learn or gain.
3. A well-organized body with clear, logically ordered points.
4. A concise, memorable conclusion.
5. A natural call-to-action (like, subscribe, comment) woven into the outro.

WRITING RULES:
- Output ONLY the narration text that should be spoken aloud.
- Do NOT include scene directions, speaker labels, timestamps, headings,
  markdown, asterisks, or emojis.
- Use short, conversational sentences that flow smoothly when read by a
  text-to-speech voice.
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


def build_short_script_prompt(
    topic: str,
    tone: str,
    audience: str,
    target_seconds: int,
    language: str,
) -> str:
    """Prompt the model for a tight, TTS-ready vertical short/reel script."""
    approx_words = max(int(target_seconds * 2.5), 25)  # ~2.5 spoken words/second
    return f"""Write a punchy short-form VERTICAL video script (Reel / YouTube Short).

TOPIC: {topic}
TARGET LANGUAGE: {language}
TONE: {tone}
AUDIENCE: {audience}
TARGET LENGTH: about {target_seconds} seconds of speech (~{approx_words} words). Stay close to this - it MUST be short.

STRUCTURE:
1. HOOK (first line): a scroll-stopping opener in the first 1-2 seconds - a bold
   claim, a question, or a surprising fact. No slow warm-up.
2. VALUE: 2-4 rapid, concrete points or one tight story. Every sentence earns
   its place. No filler, no "in this video".
3. PAYOFF + CTA: a satisfying takeaway, then a quick call to action such as
   "follow for more" or "save this".

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
