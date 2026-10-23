import re

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_text_splitters import RecursiveCharacterTextSplitter

from core.llm import get_llm

MAP_CHARS = 8000
MAX_REDUCE_CHARS = 12000
MAX_COMPRESS_ROUNDS = 5

NOTES_PROMPT = (
    "You are an expert meeting analyst. From this part of a transcript, write concise "
    "bullet-point notes: key points, decisions, action items (with owner and deadline if "
    "mentioned) and unresolved questions. Notes only, no introduction."
)

COMPRESS_PROMPT = (
    "Merge these meeting notes into a shorter set of notes. Keep every decision, every "
    "action item (owner, deadline) and every open question. Bullet points only."
)

REPORT_PROMPT = """You are an expert meeting analyst. Using the transcript or notes below, \
return EXACTLY this format, with these headings and nothing before or after:

## TITLE
<a professional title, maximum 8 words>
## SUMMARY
<a professional summary in bullet points>
## ACTION ITEMS
<numbered list; each item has the task, the owner, and the deadline or 'Not specified'. \
If none, write: No action items found.>
## KEY DECISIONS
<numbered list. If none, write: No key decisions found.>
## OPEN QUESTIONS
<numbered list of unresolved questions. If none, write: No open questions found.>"""

SECTIONS = {
    "TITLE": "title",
    "SUMMARY": "summary",
    "ACTION ITEMS": "action_items",
    "KEY DECISIONS": "key_decisions",
    "OPEN QUESTIONS": "open_questions",
}
_SPLIT = re.compile(
    r"^##\s*(TITLE|SUMMARY|ACTION ITEMS|KEY DECISIONS|OPEN QUESTIONS)\s*$",
    flags=re.MULTILINE | re.IGNORECASE,
)


def _chain(system_prompt: str, temperature: float = 0.2):
    prompt = ChatPromptTemplate.from_messages([("system", system_prompt), ("human", "{text}")])
    return prompt | get_llm(temperature) | StrOutputParser()


def parse_report(text: str) -> dict:
    result = {name: "" for name in SECTIONS.values()}
    parts = _SPLIT.split(text)
    for heading, body in zip(parts[1::2], parts[2::2]):
        result[SECTIONS[heading.upper()]] = body.strip()
    if not any(result.values()):  # मॉडल ने फ़ॉर्मैट नहीं माना: उसका टेक्स्ट बचा लो
        result["summary"] = text.strip()
    result["title"] = (result["title"].splitlines() or [""])[0].strip() or "Untitled meeting"
    return result


def _split(text: str, size: int, overlap: int = 0) -> list:
    return RecursiveCharacterTextSplitter(chunk_size=size, chunk_overlap=overlap).split_text(text)


def analyze(transcript: str) -> dict:
    """छोटा ट्रांसक्रिप्ट: 1 कॉल। लंबा: हर ~8000 अक्षर पर 1 कॉल + आखिर में 1 कॉल।"""
    pieces = _split(transcript, MAP_CHARS, overlap=300)

    if len(pieces) == 1:
        notes = pieces[0]
    else:
        notes_chain = _chain(NOTES_PROMPT)
        notes = "\n\n".join(notes_chain.invoke({"text": p}) for p in pieces)

        compress_chain = _chain(COMPRESS_PROMPT)
        for _ in range(MAX_COMPRESS_ROUNDS):
            if len(notes) <= MAX_REDUCE_CHARS:
                break
            groups = _split(notes, MAX_REDUCE_CHARS)
            notes = "\n\n".join(compress_chain.invoke({"text": g}) for g in groups)
        notes = notes[: MAX_REDUCE_CHARS * 2]

    return parse_report(_chain(REPORT_PROMPT).invoke({"text": notes}))