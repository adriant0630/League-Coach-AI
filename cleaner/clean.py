"""
Cleans raw wikitext scraped from the League Wiki and splits it into
labeled chunks ready for embedding.

Input:  raw_pages/*.txt        (raw wikitext, one file per champion)
Output: cleaned_chunks.json    (list of {champion, section, content} dicts)

Usage:
    python clean.py
"""

import re
import os
import json

INPUT_DIR = "../scraper/raw_pages"
OUTPUT_FILE = "cleaned_chunks.json"

# Minimum length (in characters) for a chunk to be worth keeping.
# Filters out near-empty sections (e.g. an empty "Mastery Usage" section).
MIN_CHUNK_LENGTH = 40


def clean_wikitext(text: str) -> str:
    """Strip MediaWiki template/markup syntax down to plain readable text.

    Handles the specific template patterns we saw in real wiki pages:
    {{ci|Champion}}, {{ai|Ability|Champion}}, {{tip|word|tooltip}}, etc.
    """

    # {{ai|Ability Name|Champion|DisplayText}} or {{ai|Ability Name|Champion}}
    # {{cai|...}} is a capitalized variant of the same template - handle both
    # -> keep just the ability name (first argument)
    text = re.sub(r"\{\{c?ai\|([^|}]+)(\|[^}]*)?\}\}", r"\1", text)

    # {{ci|Champion}} or {{ci|Champion|DisplayText}} (e.g. {{ci|Riven|Riven's}})
    # or {{cis|Champion}} (possessive form) -> keep the LAST argument if present
    # (the display text override), otherwise the champion name itself
    text = re.sub(r"\{\{cis?\|([^|}]+)\|([^}]+)\}\}", r"\2", text)  # two-arg form first
    text = re.sub(r"\{\{cis?\|([^|}]+)\}\}", r"\1", text)            # one-arg form

    # {{tip|word|tooltip text}} -> keep just the visible word, drop the tooltip
    text = re.sub(r"\{\{tip\|([^|}]+)(\|[^}]*)?\}\}", r"\1", text)

    # {{as|stat text}} -> keep just the stat text
    text = re.sub(r"\{\{as\|([^}]+)\}\}", r"\1", text)

    # {{sti|Stat Name}} or {{sti|Stat Name|link=true}} (stat icon template,
    # may have extra named params after the stat name) -> keep just the stat name
    text = re.sub(r"\{\{sti\|([^|}]+)(\|[^}]*)?\}\}", r"\1", text)

    # {{si|Summoner Spell Name}} (summoner spell icon template, e.g. {{si|Smite}},
    # {{si|Flash}}) -> keep just the spell name
    text = re.sub(r"\{\{si\|([^|}]+)(\|[^}]*)?\}\}", r"\1", text)

    # {{ri|Rune Name}} or {{ri|Rune Name|size=32}} (rune icon template, used
    # heavily in every champion's "Rune Usage" section, e.g. {{ri|Electrocute}})
    # -> keep just the rune name
    text = re.sub(r"\{\{ri\|([^|}]+)(\|[^}]*)?\}\}", r"\1", text)

    # {{sbc|text}} -> "strong/bold/colored" text wrapper, keep just the text
    text = re.sub(r"\{\{sbc\|([^}]+)\}\}", r"\1", text)

    # {{ii|Item Name}} -> item references, keep just the name
    text = re.sub(r"\{\{ii\|([^|}]+)(\|[^}]*)?\}\}", r"\1", text)

    # {{nie|Passive/Effect Name}} -> named item effects, keep just the name
    text = re.sub(r"\{\{nie\|([^}]+)\}\}", r"\1", text)

    # {{ui|Unit}} or {{uis|Unit}} -> jungle monster/unit references
    text = re.sub(r"\{\{uis?\|([^}]+)\}\}", r"\1", text)

    # {{g|amount}} -> gold amounts
    text = re.sub(r"\{\{g\|([^}]+)\}\}", r"\1 gold", text)

    # Zero-argument forms of stat/item/champion/ability templates ({{as}},
    # {{ii}}, {{sti}}, {{ci}}, {{ai}} with no pipe at all) rely on page
    # context we don't have access to (e.g. auto-filling "armor" based on
    # which champion's page this is) - drop these entirely rather than
    # leaking the bare template name as fake text (e.g. "As." or "Ii grants")
    text = re.sub(r"\{\{(as|ii|sti|ci|cis|ai|cai|si|ri|sbc|nie|g)\}\}", "", text)

    # {{fd|number}} -> formatted duration/decimal numbers
    text = re.sub(r"\{\{fd\|([^}]+)\}\}", r"\1", text)

    # [[Category:X]] tags are wiki metadata, not content - remove entirely
    text = re.sub(r"\[\[Category:[^\]]*\]\]", "", text, flags=re.IGNORECASE)

    # [[xx:Page Name]] language interlink tags (e.g. [[ru:Riven/Strategy]],
    # [[de:Akali#tab-Strategie]]) are links to other-language wiki versions,
    # not content - remove entirely. Pattern: two-letter lowercase code, colon.
    text = re.sub(r"\[\[[a-z]{2}:[^\]]*\]\]", "", text)

    # [[Link|Display Text]] -> keep just the display text
    text = re.sub(r"\[\[([^|\]]+)\|([^\]]+)\]\]", r"\2", text)
    # [[Link]] (no display text override) -> keep the link text itself
    text = re.sub(r"\[\[([^\]]+)\]\]", r"\1", text)

    # Reference tags <ref>...</ref> -> remove entirely (citations, not useful for our purposes)
    text = re.sub(r"<ref>.*?</ref>", "", text, flags=re.DOTALL)
    text = re.sub(r"<ref[^>]*/>", "", text)

    # HTML comments <!-- editor notes --> -> remove entirely, these are
    # instructions left for wiki editors, not actual strategy content
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)

    # Any other leftover HTML tags (e.g. <br />, <small>, </small>) -> remove
    # the tags themselves but keep any text they wrapped
    text = re.sub(r"<[^>]+>", "", text)

    # {{matchups |goodchamp1=X |goodtext1=Y |badchamp1=A |badtext1=B ...}} template
    # This template lists specific good/bad matchups with explanatory text.
    # Some champion pages have this fully filled in (real, valuable content);
    # others leave it completely empty (just bare |goodchamp1= with nothing after).
    # We need to extract real content where present, and drop it cleanly where empty.
    def expand_matchups_template(match):
        block = match.group(0)
        lines = []
        # Find every goodtext/badtext field with real content, and pair it with
        # its corresponding goodchamp/badchamp name from the same numbered slot
        for kind, label in [("good", "Good matchup with"), ("bad", "Difficult matchup against")]:
            champ_pattern = re.compile(rf"\|\s*{kind}champ(\d+)\s*=\s*([^\n|]*)")
            text_pattern = re.compile(rf"\|\s*{kind}text(\d+)\s*=\s*([^\n|]*(?:\n(?!\s*\|)[^\n]*)*)")

            champs = {m.group(1): m.group(2).strip() for m in champ_pattern.finditer(block)}
            texts = {m.group(1): m.group(2).strip() for m in text_pattern.finditer(block)}

            for num, champ_name in champs.items():
                explanation = texts.get(num, "").strip()
                if champ_name and explanation:
                    lines.append(f"{label} {champ_name}: {explanation}")

        return "\n".join(lines)

    text = re.sub(r"\{\{matchups.*?\n\}\}", expand_matchups_template, text, flags=re.DOTALL | re.IGNORECASE)
    # Catch the same template if it doesn't end with a newline before the closing braces
    text = re.sub(r"\{\{matchups.*?\}\}", expand_matchups_template, text, flags=re.DOTALL | re.IGNORECASE)
    # Clean up any stray leftover braces from imperfect template boundary matches
    text = re.sub(r"^\}\}\s*$", "", text, flags=re.MULTILINE)

    # '''bold text''' and ''italic text''' wikitext markup -> strip the
    # quote markers, keep the text itself
    text = re.sub(r"'''(.*?)'''", r"\1", text)
    text = re.sub(r"''(.*?)''", r"\1", text)

    # Any leftover === Sub-header === or == Header == markup that appears
    # WITHIN a section's content (not just at its boundary) -> strip the
    # markup but keep the heading text itself, since it's often a useful
    # label (e.g. "What do I build on Kai'Sa?")
    text = re.sub(r"={2,4}\s*([^=\n]+?)\s*={2,4}", r"\1", text)

    # Any remaining {{...}} templates we didn't explicitly handle: rather than
    # deleting them outright (which leaves dangling words and double-spaces
    # when the template held real content, e.g. an unhandled pronoun or stat
    # template), keep the template's LAST argument as fallback text. The last
    # argument is consistently where the human-readable display text lives
    # across these wiki templates (e.g. {{ci|Riven|Riven's}} -> "Riven's",
    # {{ai|Mystic Shot|Ezreal}} -> "Ezreal" would be wrong here, which is why
    # explicitly-handled templates above take priority; this fallback only
    # fires for template types we haven't named, where we can't know which
    # argument position holds the real content, so last-argument is the
    # safer general default since trailing args are usually the displayed text).
    def fallback_template_text(match):
        inner = match.group(1)
        args = [a.strip() for a in inner.split("|")]
        # Drop named parameters (key=value) - these are never readable content
        text_args = [a for a in args if "=" not in a]
        if not text_args:
            return ""
        # Skip the very first token if it looks like a template/type name
        # (single lowercase word, no spaces) and there's a more substantial
        # argument after it - that first token is almost always the template
        # identifier, not content, when more args follow
        if len(text_args) > 1 and re.match(r"^[a-z][a-zA-Z]*$", text_args[0]):
            return text_args[-1]
        return text_args[0]

    text = re.sub(r"\{\{([^}]*)\}\}", fallback_template_text, text)

    # Clean up any double (or more) spaces left behind by template removal,
    # and trailing spaces before sentence punctuation (e.g. "his ." -> "his.")
    # Note: semicolon is deliberately excluded here, since ";" at the start
    # of a line is also used as a wiki list marker and must keep its
    # preceding newline so it's correctly split into its own line below.
    text = re.sub(r"  +", " ", text)
    text = re.sub(r"[ \t]+([.,:!?])", r"\1", text)

    # Wiki list markers (*, **, ***, ;) at the start of lines -> convert to a simple dash
    text = re.sub(r"^[;*]+\s*", "- ", text, flags=re.MULTILINE)

    # Remove bare empty bullet lines (just "-" with nothing else) - these come
    # from wiki entries where an editor added a bullet placeholder but never
    # filled in the actual content (common on incomplete/abandoned sections)
    text = re.sub(r"^-\s*$\n?", "", text, flags=re.MULTILINE)

    # Collapse multiple blank lines into one
    text = re.sub(r"\n\s*\n+", "\n", text)

    # Trim leading/trailing whitespace on each line and the whole block
    text = "\n".join(line.strip() for line in text.split("\n"))
    text = text.strip()

    return text


def split_into_sections(wikitext: str, champion: str) -> list[dict]:
    """Split a champion's raw Strategy page into labeled section chunks.

    Looks for the specific section headers we found in real pages:
    == Tips ==, == Tricks ==, with sub-labels like
    "Playing As", "Playing Against", "Ability Usage", "Item Usage", "Countering".
    """

    # Some raw wiki source omits the newline before a ";Sub-header" marker,
    # so it appears glued onto the end of the previous sentence (e.g.
    # "...swinging!;Five Point Strike [Q]"). Force a line break before any
    # mid-line semicolon-marker so marker-position detection below finds it
    # correctly as its own line, not buried inside the prior sentence.
    wikitext = re.sub(r"(?<!^)(?<!\n);(?=[A-Z])", "\n;", wikitext)

    chunks = []

    # Map of regex patterns (sub-section labels) to our clean section names.
    # Patterns are case-insensitive since different champion pages were
    # written by different editors with inconsistent capitalization
    # (e.g. "Playing As" vs "Playing as").
    section_markers = [
        (r";\s*Playing [Aa]s\b(?!\s+[Ww]ith)", "playing_as"),  # avoid matching "Playing with"
        (r";\s*Playing [Aa]gainst", "playing_against"),
        (r";\s*Mastery Usage", "mastery_usage"),
        (r";\s*Ability Usage", "ability_usage"),
        (r"^===?\s*Ability Usage\s*===?", "ability_usage"),     # some pages use a header instead of a ; marker
        (r";\s*Item Usage", "item_usage"),
        (r"^==\s*Items\s*==", "item_usage"),                    # some pages use a top-level "Items" header instead
        (r";\s*Countering", "countering"),
        (r"^==\s*Synergies\s*(&|and)\s*Counterpicks\s*==", "countering"),  # alternate top-level header style
        (r"^==\s*Counterpicks\s*==", "countering"),  # yet another variant, seen on some pages
        (r"^==\s*Countering\s*==", "countering"),    # and another - some pages use this exact word as a header too
    ]

    # Find the position of each marker in the raw text, in order of appearance
    positions = []
    for pattern, label in section_markers:
        match = re.search(pattern, wikitext, re.IGNORECASE | re.MULTILINE)
        if match:
            positions.append((match.start(), label))

    # Also track markers we deliberately don't extract (e.g. "Playing with",
    # which is consistently empty/unused on real pages) purely as boundaries,
    # so they stop the previous section from bleeding into them.
    ignored_markers = [r";\s*Playing [Ww]ith"]
    for pattern in ignored_markers:
        match = re.search(pattern, wikitext, re.IGNORECASE | re.MULTILINE)
        if match:
            positions.append((match.start(), None))  # None = boundary only, not extracted

    # Also find top-level == Header == lines, which should act as hard
    # boundaries even when no specific sub-marker follows immediately after.
    # This stops a section from "bleeding" into the next top-level heading.
    header_positions = [m.start() for m in re.finditer(r"^==[^=].*?==\s*$", wikitext, re.MULTILINE)]

    # {{Section bot}} and == References == mark the end of real content on
    # every page (boilerplate footer), but aren't always preceded by a
    # top-level == Header == of their own - add them as explicit boundaries
    # so the last real section doesn't bleed into this footer junk.
    footer_positions = [m.start() for m in re.finditer(r"\{\{Section bot\}\}", wikitext, re.IGNORECASE)]
    header_positions.extend(footer_positions)

    # Sort sub-section markers by where they appear in the text
    positions.sort(key=lambda x: x[0])

    # Slice the text between each marker and the next boundary (next marker,
    # next top-level header, or end of text - whichever comes first)
    for i, (start, label) in enumerate(positions):
        if label is None:
            continue  # boundary-only marker, not a real section to extract

        next_marker = positions[i + 1][0] if i + 1 < len(positions) else len(wikitext)
        # Find the nearest top-level header that comes after this marker
        later_headers = [h for h in header_positions if h > start]
        next_header = later_headers[0] if later_headers else len(wikitext)

        end = min(next_marker, next_header)
        raw_section = wikitext[start:end]

        # Drop the marker line itself, whether it's a ";Label" style marker
        # or a "== Header ==" / "=== Header ===" style marker, since the
        # section label is already stored separately in the "section" field
        raw_section = re.sub(r"^;[^\n]*\n?", "", raw_section)
        raw_section = re.sub(r"^={2,3}[^\n=]*={2,3}\n?", "", raw_section)

        cleaned = clean_wikitext(raw_section)

        if len(cleaned) >= MIN_CHUNK_LENGTH:
            chunks.append({
                "champion": champion,
                "section": label,
                "content": cleaned,
            })

    return chunks


def main():
    if not os.path.isdir(INPUT_DIR):
        print(f"[ERROR] Input directory not found: {INPUT_DIR}")
        print("Make sure you've run scrape.py first, and that this script")
        print("is being run from the right folder relative to raw_pages/.")
        return

    all_chunks = []
    files = [f for f in os.listdir(INPUT_DIR) if f.endswith(".txt")]

    if not files:
        print(f"[ERROR] No .txt files found in {INPUT_DIR}")
        return

    print(f"Found {len(files)} raw files to process.\n")

    for filename in sorted(files):
        champion = filename.replace(".txt", "").replace("_", " ")
        filepath = os.path.join(INPUT_DIR, filename)

        with open(filepath, "r", encoding="utf-8") as f:
            raw_text = f.read()

        chunks = split_into_sections(raw_text, champion)

        if chunks:
            print(f"{champion}: extracted {len(chunks)} chunks "
                  f"({', '.join(c['section'] for c in chunks)})")
            all_chunks.extend(chunks)
        else:
            print(f"[WARN] {champion}: no recognizable sections found - "
                  f"page structure may differ from expected format")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(all_chunks, f, indent=2, ensure_ascii=False)

    print(f"\nDone. {len(all_chunks)} total chunks saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()