from __future__ import annotations

import re
from typing import Any

_HEADER_KEY_RE = re.compile(r"^([A-Za-z_][\w-]*)\s*:\s*(.*)$")


def _split_frontmatter(text: str) -> tuple[str, str]:
    stripped = (text or "").lstrip()
    if not stripped.startswith("---"):
        return "", text or ""
    lines = stripped.splitlines()
    if not lines or lines[0].strip() != "---":
        return "", text or ""
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            header = "\n".join(lines[1:idx])
            body = "\n".join(lines[idx + 1 :])
            return header, body
    return "", text or ""


def _extract_inline_header(text: str) -> tuple[str, str]:
    lines = (text or "").splitlines()
    header_lines: list[str] = []
    body_lines: list[str] = []
    in_header = True
    for line in lines:
        if in_header and _HEADER_KEY_RE.match(line):
            header_lines.append(line)
            continue
        if in_header and not line.strip():
            in_header = False
            continue
        in_header = False
        body_lines.append(line)
    return "\n".join(header_lines), "\n".join(body_lines)


def _parse_header(header: str) -> dict[str, Any]:
    data: dict[str, Any] = {}
    lines = (header or "").splitlines()
    index = 0
    while index < len(lines):
        line = lines[index].rstrip()
        if not line.strip():
            index += 1
            continue

        match = _HEADER_KEY_RE.match(line)
        if not match:
            index += 1
            continue

        key = match.group(1).lower().replace("-", "_")
        value = match.group(2).strip()

        if value == "|":
            index += 1
            block: list[str] = []
            while index < len(lines):
                next_line = lines[index]
                if _HEADER_KEY_RE.match(next_line) and not next_line.startswith(" "):
                    break
                block.append(next_line.lstrip())
                index += 1
            data[key] = "\n".join(block).strip()
            continue

        if value == "":
            index += 1
            items: list[str] = []
            while index < len(lines):
                next_line = lines[index]
                if _HEADER_KEY_RE.match(next_line) and not next_line.startswith(" "):
                    break
                if next_line.lstrip().startswith("-"):
                    items.append(next_line.lstrip()[1:].strip())
                index += 1
            data[key] = items
            continue

        data[key] = value
        index += 1

    return data


def parse_skill_definition(definition: str) -> dict[str, Any]:
    raw = definition or ""
    header, body = _split_frontmatter(raw)
    if not header:
        header, body = _extract_inline_header(raw)
    data = _parse_header(header) if header else {}

    name = str(data.get("name") or "").strip()
    description = str(data.get("description") or "").strip() or None
    prompt = str(data.get("prompt") or "").strip()
    if not prompt:
        prompt = (body or "").strip()

    triggers: list[str] = []
    raw_triggers = data.get("triggers")
    if isinstance(raw_triggers, str):
        triggers = [t.strip() for t in re.split(r"[;,]", raw_triggers) if t.strip()]
    elif isinstance(raw_triggers, list):
        triggers = [str(t).strip() for t in raw_triggers if str(t).strip()]

    return {
        "name": name,
        "description": description,
        "triggers": triggers,
        "prompt": prompt,
        "definition": raw,
    }


def match_skills(prompt: str, skills: list[dict], limit: int = 3) -> list[dict]:
    if not prompt:
        return []
    normalized = re.sub(r"\s+", " ", prompt.lower()).strip()
    if not normalized:
        return []

    matched: list[dict] = []
    for skill in skills:
        triggers = skill.get("triggers") or []
        for raw_trigger in triggers:
            trigger = str(raw_trigger or "").strip().lower()
            if not trigger:
                continue
            if " " in trigger:
                if trigger in normalized:
                    matched.append(skill)
                    break
            else:
                if re.search(rf"\b{re.escape(trigger)}\b", normalized):
                    matched.append(skill)
                    break
        if len(matched) >= limit:
            break
    return matched


def build_skill_context(skills: list[dict]) -> str:
    if not skills:
        return ""
    blocks: list[str] = []
    for skill in skills:
        name = str(skill.get("name") or "").strip()
        description = str(skill.get("description") or "").strip()
        prompt = str(skill.get("prompt") or "").strip()
        header = name or "Skill"
        if description:
            header = f"{header} — {description}"
        if prompt:
            blocks.append(f"{header}\n{prompt}")
    return "\n\n".join(blocks)
