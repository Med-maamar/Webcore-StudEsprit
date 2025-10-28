from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set

from django.conf import settings
from dotenv import load_dotenv

# Gemini uniquement (aucun OpenAI, aucun dictionnaire de compétences)

logger = logging.getLogger(__name__)


def _load_env_if_needed() -> None:
    """Recharge .env si nécessaire (sécurisé et idempotent)."""
    try:
        # Essayez de charger depuis le dossier du projet si non présent dans l'environnement
        base = getattr(settings, "BASE_DIR", None)
        if base:
            load_dotenv(os.path.join(str(base), ".env"))
    except Exception:
        # Pas bloquant
        pass


def _get_gemini_api_key() -> str:
    _load_env_if_needed()
    key = (
        os.getenv("GEMINI_API_KEY")
        or getattr(settings, "GEMINI_API_KEY", "")
        or os.getenv("GOOGLE_API_KEY")  # fallback courant côté Google
        or ""
    )
    return key.strip()


def _get_genai_client():
    try:
        import google.generativeai as genai  # type: ignore
    except Exception as exc:  # pragma: no cover
        logger.warning("Gemini SDK introuvable: %s", exc)
        return None
    key = _get_gemini_api_key()
    if not key:
        logger.warning("GEMINI_API_KEY manquant (ou GOOGLE_API_KEY)")
        return None
    try:
        # Masked log to confirm key is read (evite d'exposer la clé)
        mask = key[:6] + "..." + key[-3:] if len(key) > 12 else "***"
        logger.info("Gemini key detected: %s", mask)
        genai.configure(api_key=key)
        return genai
    except Exception as exc:  # pragma: no cover
        logger.warning("Configuration Gemini échouée: %s", exc)
        return None


DEFAULT_GEMINI_MODEL = "gemini-2.0-flash"


def _env_model_candidates() -> List[str]:
    """Return only the allowed model (gemini-2.0-flash), honoring .env if it matches.

    Produces both simple and "models/" prefixed forms for maximum SDK compatibility.
    """
    env_value = (
        os.getenv("GEMINI_MODEL")
        or getattr(settings, "GEMINI_MODEL", "")
        or ""
    ).strip()
    simple = env_value.replace("models/", "") if env_value else DEFAULT_GEMINI_MODEL
    if simple != DEFAULT_GEMINI_MODEL:
        logger.info("Ignoring GEMINI_MODEL '%s' (forcing %s)", env_value, DEFAULT_GEMINI_MODEL)
        simple = DEFAULT_GEMINI_MODEL
    return [simple, f"models/{simple}"]


def _pick_gemini_model(genai) -> Optional[str]:
    """Select only gemini-2.0-flash if available; otherwise, return it as fallback."""
    preferred = _env_model_candidates()
    try:
        models = list(genai.list_models())
        # Normalize names and keep only those that support text generation
        available = set()
        supports = {}
        for m in models:
            name = getattr(m, "name", "")
            if name.startswith("models/"):
                simple = name.split("/", 1)[1]
            else:
                simple = name
            methods = set(getattr(m, "supported_generation_methods", []) or [])
            supports[simple] = methods
            if "generateContent" in methods:
                available.add(simple)
        for cand in preferred:
            if cand in available:
                return cand
    except Exception:
        # If list_models fails, try known names directly in order
        pass
    # Fallback list
    return preferred[0]


def extract_skills(text: Optional[str]) -> Set[str]:
    """Extraction naïve sans dictionnaire: récupère les éléments après 'skills'/'compétences'.

    - Cherche une ligne mentionnant 'skills' ou 'compétences', puis découpe par virgule ou point-virgule.
    - Ne repose pas sur une liste de mots-clés statique.
    """
    if not text:
        return set()
    out: Set[str] = set()
    for line in text.splitlines():
        lower = line.lower()
        if "skills" in lower or "compétences" in lower or "competences" in lower:
            # découper après ':' si présent
            parts = line.split(":", 1)
            payload = parts[1] if len(parts) > 1 else parts[0]
            tokens = re.split(r"[,;•\-\u2022]\s*", payload)
            for t in tokens:
                norm = t.strip().strip("-•·*")
                if 2 <= len(norm) <= 40:
                    out.add(norm)
    return out


@dataclass
class CareerAIService:
    """Service d'IA carrière — génération via Gemini uniquement."""

    @classmethod
    def create(cls) -> "CareerAIService":
        return cls()

    # PUBLIC API
    def analyze_cv_gap(self, job_desc: str, cv_text: str = "", cv_url: str = "") -> Dict[str, Any]:
        """Version minimale sans dictionnaire: comparaison de tokens.

        Conserve la forme de sortie attendue, mais ne dépend d'aucune ressource statique.
        """
        def _tokens(s: str) -> Set[str]:
            return {t.lower() for t in re.findall(r"[A-Za-zÀ-ÿ0-9_+.#-]{2,}", s or "")}

        job = _tokens(job_desc)
        cv = _tokens(cv_text)
        matched = sorted((job & cv))
        missing = sorted((job - cv))[:30]
        score = max(0, 100 - min(len(missing), 10) * 5)
        return {
            "missingSkills": missing,
            "matchedSkills": matched,
            "score": score,
            "microLearningPlan": [],
        }

    def generate_cover_letter(
        self, job_desc: str, cv_text: str = "", achievements: Optional[List[str]] = None, tone: str = "professional"
    ) -> Dict[str, Any]:
        payload = {
            "jobDesc": job_desc,
            "cvText": cv_text,
            "achievements": achievements or [],
            "tone": tone,
        }
        # UNIQUEMENT GEMINI
        try:
            _genai = _get_genai_client()
            if _genai is None:
                raise RuntimeError("GEMINI_API_KEY manquant ou SDK indisponible")
            picked = _pick_gemini_model(_genai)
            tried = []
            # try only gemini-2.0-flash (simple + models/ prefix)
            candidates = [c for c in {picked, *_env_model_candidates()} if c]
            prompt = (
                "Rédige en français une lettre de motivation concise et professionnelle en Markdown pour un(e) étudiant(e).\n"
                f"Description de poste:\n{job_desc}\n---\n"
                f"Ton: {tone}.\n"
                "N'invente pas d'informations personnelles; reste générique si nécessaire."
            )
            last_exc: Optional[Exception] = None
            for model_name in candidates:
                if model_name in tried:
                    continue
                tried.append(model_name)
                try:
                    model = _genai.GenerativeModel(model_name)
                    resp = model.generate_content(prompt)
                    if hasattr(resp, 'text') and resp.text:
                        logger.info("Gemini cover letter using model: %s", model_name)
                        return {"markdown": resp.text}
                except Exception as e:
                    last_exc = e
                    continue
            if last_exc:
                raise last_exc
            raise RuntimeError("Réponse vide de Gemini")
        except Exception as exc:
            logger.warning("Gemini cover letter error: %s", exc)
            return {"markdown": "(Génération indisponible — configurez GEMINI_API_KEY et réessayez)"}

    def generate_interview_prep(
        self, job_desc: str, skills: Optional[List[str]] = None, level: str = "junior"
    ) -> Dict[str, Any]:
        # Uniformiser: utiliser Gemini via generate_hard_interview uniquement
        return self.generate_hard_interview(job_desc, skills or [], n=10)

    def generate_hard_interview(self, job_desc: str, skills: Optional[List[str]] = None, n: int = 10) -> Dict[str, Any]:
        # Gemini requis
        if True:
            try:
                _genai = _get_genai_client()
                if _genai is None:
                    raise RuntimeError("GEMINI_API_KEY manquant ou SDK indisponible")
                picked = _pick_gemini_model(_genai)
                tried = []
                # try only gemini-2.0-flash (simple + models/ prefix)
                candidates = [c for c in {picked, *_env_model_candidates()} if c]
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
                text = ""
                last_exc: Optional[Exception] = None
                for model_name in candidates:
                    if model_name in tried:
                        continue
                    tried.append(model_name)
                    try:
                        model = _genai.GenerativeModel(model_name)
                        resp = model.generate_content(prompt, generation_config={"temperature": 0.9})
                        text = getattr(resp, "text", "") or ""
                        if text:
                            logger.info("Gemini interview prep using model: %s", model_name)
                            break
                    except Exception as e:
                        last_exc = e
                        continue
                # Some models return markdown fenced JSON; try to extract
                extracted = text
                if "{" in text and "}" in text:
                    start = text.find("{")
                    end = text.rfind("}")
                    if start >= 0 and end > start:
                        extracted = text[start : end + 1]
                if not extracted and last_exc:
                    raise last_exc
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
        # Pas de fallback si Gemini indisponible
        return {}


def _extract_snippet(text: Optional[str], keywords: List[str]) -> str:
    if not text:
        return ""
    lower = text.lower()
    for keyword in keywords:
        idx = lower.find(keyword)
        if idx >= 0:
            start = max(0, idx - 20)
            end = min(len(text), idx + 60)
            snippet = text[start:end]
            return snippet.strip()
    return ""
