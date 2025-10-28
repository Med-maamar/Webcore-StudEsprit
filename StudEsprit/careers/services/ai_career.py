from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Set

from django.conf import settings

try:  # Optional dependency
    from openai import OpenAI
except ImportError:  # pragma: no cover - optional
    OpenAI = None  # type: ignore

try:  # Optional Gemini
    import google.generativeai as genai  # type: ignore
except Exception:  # pragma: no cover - optional
    genai = None  # type: ignore

logger = logging.getLogger(__name__)


SKILL_DICTIONARY: Dict[str, Sequence[str]] = {
    "python": ("python", "py"),
    "django": ("django",),
    "mongodb": ("mongodb", "mongo"),
    "rest": ("rest", "restful", "api"),
    "docker": ("docker",),
    "aws": ("aws", "amazon web services"),
    "git": ("git", "github", "gitlab"),
    "pandas": ("pandas",),
    "ml": ("machine learning", "ml"),
    "nlp": ("natural language processing", "nlp"),
    "react": ("react", "reactjs"),
    "linux": ("linux", "unix"),
    "htmx": ("htmx",),
    "graphql": ("graphql",),
    "fastapi": ("fastapi",),
}


SKILL_RESOURCES: Dict[str, List[Dict[str, str]]] = {
    "python": [
        {"title": "Python Official Tutorial", "url": "https://docs.python.org/3/tutorial/"},
        {"title": "Real Python - Practical Python", "url": "https://realpython.com"},
    ],
    "django": [
        {"title": "Django Getting Started", "url": "https://docs.djangoproject.com/en/5.0/intro/"},
        {"title": "Django for APIs", "url": "https://www.django-rest-framework.org/tutorial/"},
    ],
    "mongodb": [
        {"title": "MongoDB Developer Center", "url": "https://www.mongodb.com/developer"},
        {"title": "MongoEngine Docs", "url": "https://docs.mongoengine.org/"},
    ],
    "rest": [
        {"title": "REST API Design Guide", "url": "https://restfulapi.net"},
        {"title": "DRF Quickstart", "url": "https://www.django-rest-framework.org/tutorial/quickstart/"},
    ],
    "docker": [
        {"title": "Docker Getting Started", "url": "https://docs.docker.com/get-started"},
        {"title": "Play with Docker", "url": "https://labs.play-with-docker.com"},
    ],
    "aws": [
        {"title": "AWS Skill Builder", "url": "https://skillbuilder.aws"},
        {"title": "AWS Well-Architected Labs", "url": "https://www.wellarchitectedlabs.com"},
    ],
    "git": [
        {"title": "Git Immersion", "url": "https://gitimmersion.com"},
        {"title": "Oh My Git!", "url": "https://ohmygit.org"},
    ],
    "pandas": [
        {"title": "Pandas User Guide", "url": "https://pandas.pydata.org/docs/user_guide/index.html"},
        {"title": "Practical Pandas", "url": "https://realpython.com/pandas-python-explore-dataset/"},
    ],
    "ml": [
        {"title": "Fast.ai Practical ML", "url": "https://course.fast.ai"},
        {"title": "ML Crash Course", "url": "https://developers.google.com/machine-learning/crash-course"},
    ],
    "nlp": [
        {"title": "HuggingFace Course", "url": "https://huggingface.co/course/chapter1"},
        {"title": "CMU Neural NLP", "url": "https://phontron.com/class/nn4nlp2024"},
    ],
    "react": [
        {"title": "React Beta Docs", "url": "https://react.dev/learn"},
        {"title": "Epic React Patterns", "url": "https://epicreact.dev"},
    ],
    "linux": [
        {"title": "Linux Journey", "url": "https://linuxjourney.com"},
        {"title": "Explain Shell", "url": "https://explainshell.com"},
    ],
    "htmx": [
        {"title": "HTMX Docs", "url": "https://htmx.org/docs"},
        {"title": "HTMX Examples", "url": "https://htmx.org/examples"},
    ],
}


DEFAULT_RESOURCES = [
    {"title": "CS50 Web Track", "url": "https://cs50.harvard.edu/web"},
    {"title": "MDN Web Docs", "url": "https://developer.mozilla.org"},
]


SKILL_PATTERN = re.compile(
    r"|".join(sorted({re.escape(v) for values in SKILL_DICTIONARY.values() for v in values}, key=len, reverse=True)),
    re.IGNORECASE,
)


def extract_skills(text: Optional[str]) -> Set[str]:
    if not text:
        return set()
    matches = {match.group(0).lower() for match in SKILL_PATTERN.finditer(text)}
    resolved: Set[str] = set()
    for canonical, variants in SKILL_DICTIONARY.items():
        if canonical in matches:
            resolved.add(canonical)
            continue
        for variant in variants:
            if variant.lower() in matches:
                resolved.add(canonical)
                break
    return resolved


@dataclass
class CareerAIService:
    mode: str = "rules"
    client: Optional[Any] = None

    def __post_init__(self):
        if self.mode == "rules":
            return
        if self.mode == "llm":
            if not settings.OPENAI_API_KEY:
                self.mode = "rules"
                return
            if OpenAI is None:
                logger.warning("OpenAI SDK not installed; falling back to RULES mode.")
                self.mode = "rules"
                return
            try:
                self.client = OpenAI(api_key=settings.OPENAI_API_KEY, timeout=15)
            except Exception as exc:  # pragma: no cover - init failure fallback
                logger.error("Failed to init OpenAI client: %s", exc)
                self.mode = "rules"

    @classmethod
    def create(cls) -> "CareerAIService":
        mode = "llm" if getattr(settings, "OPENAI_API_KEY", None) else "rules"
        return cls(mode=mode)

    # PUBLIC API
    def analyze_cv_gap(self, job_desc: str, cv_text: str = "", cv_url: str = "") -> Dict[str, Any]:
        payload = {"jobDesc": job_desc, "cvText": cv_text, "cvUrl": cv_url}
        if self.mode == "llm":
            result = self._chat_completion(
                system=(
                    "Tu analyses en français les écarts de compétences d'un(e) étudiant(e) par rapport à une offre. "
                    "Retourne du JSON strict avec les clés: missingSkills, matchedSkills, score, microLearningPlan. "
                    "microLearningPlan est un tableau d'objets {skill, resources:[{title,url}], hours}."
                ),
                user=json.dumps(payload),
            )
            if result:
                return result
        return self._rules_cv_gap(job_desc, cv_text)

    def generate_cover_letter(
        self, job_desc: str, cv_text: str = "", achievements: Optional[List[str]] = None, tone: str = "professional"
    ) -> Dict[str, Any]:
        payload = {
            "jobDesc": job_desc,
            "cvText": cv_text,
            "achievements": achievements or [],
            "tone": tone,
        }
        # Prefer Gemini if configured
        if getattr(settings, "GEMINI_API_KEY", None) and genai is not None:
            try:
                genai.configure(api_key=settings.GEMINI_API_KEY)
                model = genai.GenerativeModel("gemini-1.5-flash")
                prompt = (
                    "Rédige une lettre de motivation concise et professionnelle en Markdown pour un étudiant.\n"
                    f"Description de poste:\n{job_desc}\n---\nProfil (extraits):\n{cv_text}\n---\n"
                    f"Ton: {tone}."
                )
                resp = model.generate_content(prompt, safety_settings=None)
                if hasattr(resp, 'text') and resp.text:
                    return {"markdown": resp.text}
            except Exception as exc:  # pragma: no cover
                logger.warning("Gemini generation failed: %s", exc)
        if self.mode == "llm":
            result = self._chat_completion(
                system=(
                    "Rédige en français une lettre de motivation personnalisée en Markdown pour l'étudiant(e). "
                    "Le ton peut être 'professional' ou 'enthusiastic'."
                ),
                user=json.dumps(payload),
                expect_markdown=True,
            )
            if result:
                return result
        return {"markdown": self._rules_cover_letter(job_desc, cv_text, achievements or [], tone)}

    def generate_interview_prep(
        self, job_desc: str, skills: Optional[List[str]] = None, level: str = "junior"
    ) -> Dict[str, Any]:
        payload = {"jobDesc": job_desc, "skills": skills or [], "level": level}
        if self.mode == "llm":
            result = self._chat_completion(
                system="Generate interview preparation content. Return JSON with qa and rubric arrays.",
                user=json.dumps(payload),
            )
            if result:
                return result
        return self._rules_interview(job_desc, skills or [], level)

    def generate_hard_interview(self, job_desc: str, skills: Optional[List[str]] = None, n: int = 10) -> Dict[str, Any]:
        # Prefer Gemini if configured
        if getattr(settings, "GEMINI_API_KEY", None) and genai is not None:
            try:
                genai.configure(api_key=settings.GEMINI_API_KEY)
                model = genai.GenerativeModel("gemini-1.5-flash")
                import datetime, random
                seed = f"seed-{datetime.datetime.utcnow().isoformat()}-{random.randint(0, 999999)}"
                prompt = (
                    "Tu es un(e) intervieweur(se) expert(e). À partir de la description de poste, "
                    "génère les questions LES PLUS DIFFICILES, spécifiques au rôle.\n"
                    f"Retourne du JSON STRICT (sans texte libre) selon ce schéma: {{\"qa\":[{{\"question\":string,\"idealPoints\":[string]}}]}}.\n"
                    f"Produis entre 1 et {min(10, max(1, n))} questions UNIQUES.\n"
                    "Varie les styles (architecture, debugging, compromis, estimation, sécurité, cas limites, incidents).\n"
                    "Évite les formulations génériques comme 'Décrivez une fois où...'.\n"
                    "Chaque question doit être concise, autonome et spécifique au rôle.\n"
                    f"RANDOMIZER: {seed}.\n"
                    "DESCRIPTION DE POSTE:\n" + (job_desc or "(aucune description)") + "\n"
                )
                resp = model.generate_content(prompt, safety_settings=None, generation_config={"temperature": 0.9})
                text = getattr(resp, "text", "") or ""
                # Some models return markdown fenced JSON; try to extract
                extracted = text
                if "{" in text and "}" in text:
                    start = text.find("{")
                    end = text.rfind("}")
                    if start >= 0 and end > start:
                        extracted = text[start : end + 1]
                data = json.loads(extracted)
                if isinstance(data, dict) and "qa" in data:
                    # Normalize + limit to 10
                    qa = data.get("qa") or []
                    norm = []
                    seen = set()
                    for item in qa[: max(1, n)]:
                        q = (item or {}).get("question") or ""
                        pts = (item or {}).get("idealPoints") or []
                        if not q:
                            continue
                        key = q.strip().lower()
                        if key in seen:
                            continue
                        seen.add(key)
                        if not isinstance(pts, list) or not pts:
                            pts = [
                                "Contexte du défi",
                                "Actions spécifiques réalisées",
                                "Résultats mesurables / apprentissages",
                            ]
                        norm.append({"question": q.strip(), "idealPoints": pts[:5]})
                        if len(norm) >= n:
                            break
                    return {"qa": norm}
            except Exception as exc:  # pragma: no cover
                logger.warning("Gemini hard interview generation failed: %s", exc)
        # Fallback: use rules + increase difficulty via senior level
        out = self._rules_interview(job_desc, skills or [], level="senior")
        out["qa"] = out.get("qa", [])[: n]
        return out

    # RULES IMPLEMENTATION
    def _rules_cv_gap(self, job_desc: str, cv_text: str) -> Dict[str, Any]:
        job_skills = extract_skills(job_desc)
        cv_skills = extract_skills(cv_text)
        missing = sorted(job_skills - cv_skills)
        matched = sorted(job_skills & cv_skills)
        penalty = min(len(missing), 10) * 5
        score = max(0, 100 - penalty)
        plan = []
        for idx, skill in enumerate(missing):
            resources = SKILL_RESOURCES.get(skill, DEFAULT_RESOURCES)
            plan.append(
                {
                    "skill": skill,
                    "resources": resources,
                    "hours": 6 + (idx % 3) * 2,
                }
            )
        return {
            "missingSkills": missing,
            "matchedSkills": matched,
            "score": score,
            "microLearningPlan": plan,
        }

    def _rules_cover_letter(
        self, job_desc: str, cv_text: str, achievements: List[str], tone: str
    ) -> str:
        job_title = _extract_snippet(job_desc, ("poste", "rôle", "role", "title", "position")) or "le poste"
        company = _extract_snippet(job_desc, ("entreprise", "company", "organisation", "organization")) or "votre entreprise"
        skills = ", ".join(sorted(extract_skills(job_desc))) or "mes forces clés"
        tone_sentence = "J'adopte une approche fiable et professionnelle" if tone == "professional" else (
            "J'apporte énergie et enthousiasme au poste"
        )
        achievements_text = "".join(f"\n- {item}" for item in achievements if item)
        if achievements_text:
            achievements_text = f"\nMes faits marquants récents :{achievements_text}\n"
        intro = "Je vous écris pour postuler" if tone == "professional" else "Je suis enthousiaste à l'idée de postuler"
        return (
            f"{intro} au poste de {job_title} chez {company}.\n\n"
            f"Fort(e) d'une expérience autour de {skills}, je suis prêt(e) à contribuer dès le premier jour."
            f" {tone_sentence}.\n"
            f"{achievements_text}\n"
            "Merci pour votre attention. Je serais ravi(e) d'échanger sur la façon dont mon parcours s'aligne avec vos besoins.\n"
            "\nCordialement,\nVotre nom"
        )

    def _rules_interview(self, job_desc: str, skills: List[str], level: str) -> Dict[str, Any]:
        inferred_skills = sorted(extract_skills(job_desc) | {skill.lower() for skill in skills})
        level_map = {
            "junior": "Bases solides et envie d'apprendre",
            "intermediate": "Équilibre entre livraison pratique et collaboration",
            "senior": "Leadership, architecture, et impact métier",
        }
        rubric = []
        for skill in inferred_skills[:6]:
            rubric.append(
                {
                    "topic": skill,
                    "whatGoodLooksLike": f"Peut expliquer {skill} avec des exemples concrets et argumenter les compromis.",
                }
            )
        rubric.append(
            {
                "topic": "communication",
                "whatGoodLooksLike": "Réponses claires et structurées, questions de relance pertinentes, prise en compte des parties prenantes.",
            }
        )
        qa = []
        for skill in inferred_skills[:5]:
            qa.append(
                {
                    "question": f"Décrivez une situation où vous avez appliqué {skill} pour obtenir un résultat.",
                    "idealPoints": [
                        "Contexte du défi",
                        "Actions spécifiques réalisées",
                        "Résultats mesurables / apprentissages",
                    ],
                }
            )
        qa.append(
            {
                "question": "En quoi votre expérience s'aligne‑t‑elle avec les responsabilités du poste ?",
                "idealPoints": [
                    "Projets pertinents à mettre en avant",
                    "Compétences en adéquation avec la description",
                    level_map.get(level, level_map["junior"]),
                ],
            }
        )
        return {"qa": qa, "rubric": rubric}

    # LLM helper
    def _chat_completion(
        self, *, system: str, user: str, expect_markdown: bool = False
    ) -> Optional[Dict[str, Any]]:
        if self.mode != "llm" or not self.client:
            return None
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                temperature=0.2,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                max_tokens=800,
                timeout=20,
            )
            content = response.choices[0].message.content if response.choices else ""
            if expect_markdown:
                return {"markdown": content.strip()}
            return json.loads(content)
        except Exception as exc:  # pragma: no cover - fallback
            logger.warning("OpenAI call failed, falling back to RULES mode: %s", exc)
            return None


def _extract_snippet(text: Optional[str], keywords: Sequence[str]) -> str:
    if not text:
        return ""
    lower = text.lower()
    for keyword in keywords:
        idx = lower.find(keyword)
        if idx >= 0:
            start = max(0, idx - 20)
            end = min(len(text), idx + 60)
            snippet = text[start:end]
            # Attempt to capture word following the keyword
            match = re.search(rf"{re.escape(keyword)}\W+(?P<value>[\w\-& ]{{2,60}})", text[idx: end], re.IGNORECASE)
            if match:
                return match.group("value").strip()
            return snippet.strip()
    return ""
