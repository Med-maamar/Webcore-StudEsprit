"""
Simple study plan generator.

This module provides a small deterministic algorithm to distribute study hours
across subjects (matières) based on their coefficient (importance), while
avoiding time slots marked as unavailable.

It is intentionally small and dependency-free so it can be used from a Flask
microservice or imported directly by Django views.
"""
from typing import List, Dict, Any, Optional
import math

WEEK_DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

def _normalize_coeffs(matieres: List[Dict[str, Any]]) -> List[float]:
    coeffs = []
    for m in matieres:
        try:
            coeffs.append(float(m.get('coefficient') or 1.0))
        except Exception:
            coeffs.append(1.0)
    total = sum(coeffs) or 1.0
    return [c / total for c in coeffs]

def generate_plan(matieres: List[Dict[str, Any]],
                  unavailable: Optional[Dict[str, List[int]]] = None,
                  total_hours_per_week: int = 20,
                  hours_range: List[int] = list(range(8, 21))) -> Dict[str, Any]:
    """
    Generate a weekly plan.

    - matieres: list of dicts with at least 'nom' and optional 'coefficient'
    - unavailable: mapping day->list of hour integers to avoid (0-23), days are keys like 'Mon'
    - total_hours_per_week: total study hours to allocate across subjects
    - hours_range: list of hour integers considered for scheduling each day

    Returns a dict with a 'slots' mapping day->list of (hour, subject_index) and
    a 'summary' with allocated hours per subject.
    """
    if unavailable is None:
        unavailable = {}

    n_mat = max(1, len(matieres))
    shares = _normalize_coeffs(matieres)

    # compute desired hours per subject (rounded)
    desired = [max(1, int(round(s * total_hours_per_week))) for s in shares]
    # adjust to match total_hours_per_week
    diff = total_hours_per_week - sum(desired)
    i = 0
    while diff != 0:
        if diff > 0:
            desired[i % n_mat] += 1
            diff -= 1
        else:
            idx = i % n_mat
            if desired[idx] > 1:
                desired[idx] -= 1
                diff += 1
        i += 1

    # build empty schedule skeleton
    slots = {d: [] for d in WEEK_DAYS}
    # flatten available slots (day, hour)
    available = []
    for d in WEEK_DAYS:
        for h in hours_range:
            if d in unavailable and h in unavailable[d]:
                continue
            available.append((d, h))

    # allocate slots round-robin weighted by desired counts
    # create a list of subject indices repeated by desired hours
    allocation_queue = []
    for idx, cnt in enumerate(desired):
        allocation_queue.extend([idx] * cnt)

    # greedily assign earliest available slots
    for i, subj_idx in enumerate(allocation_queue):
        if i >= len(available):
            break
        d, h = available[i]
        slots[d].append({"hour": h, "matiere_idx": subj_idx})

    # prepare colored level for each matiere based on coefficient magnitude
    colors = []
    for s in shares:
        if s >= 0.6:
            colors.append('bg-red-600')
        elif s >= 0.3:
            colors.append('bg-amber-500')
        else:
            colors.append('bg-green-500')

    summary = []
    for idx, m in enumerate(matieres):
        summary.append({
            "nom": m.get('nom') or f"Matière {idx+1}",
            "hours": desired[idx],
            "color": colors[idx],
            "coefficient": m.get('coefficient')
        })

    return {"slots": slots, "summary": summary, "hours_range": hours_range, "week_days": WEEK_DAYS}
