"""Small helper to analyze weighted averages for a set of subjects (matieres).

Functions expect a list of matieres like:
  [{"nom": "Math", "coefficient": 4, "grade": 12}, ...]

The analyzer computes:
 - current weighted average (considering provided grades)
 - for each target average (e.g. 10 and 13), the minimal grade required in each
   subject to reach that overall target assuming other grades stay the same.

This is intentionally simple and deterministic so it can be used as a fallback
when no ML model is available.
"""
from typing import List, Dict, Any


def weighted_average(matieres: List[Dict[str, Any]]) -> float:
    total_w = 0.0
    total_points = 0.0
    for m in matieres:
        coef = float(m.get('coefficient') or 0)
        grade = m.get('grade')
        if grade is None:
            continue
        try:
            g = float(grade)
        except Exception:
            continue
        total_w += coef
        total_points += g * coef
    if total_w == 0:
        return 0.0
    return total_points / total_w


def required_grade_for_target(matieres: List[Dict[str, Any]], target: float) -> List[Dict[str, Any]]:
    """For each matiere compute the minimal grade needed in that matiere to
    reach the overall target average, assuming all other grades stay the same.

    Returns a list of dicts mirroring matieres with an added key
    `required_for_target_{t}` for convenience (caller can rename).
    """
    # compute current weighted sum and total coef
    total_coef = 0.0
    weighted_sum = 0.0
    for m in matieres:
        coef = float(m.get('coefficient') or 0)
        total_coef += coef
        grade = m.get('grade')
        if grade is None:
            continue
        try:
            weighted_sum += float(grade) * coef
        except Exception:
            continue

    results = []
    for m in matieres:
        coef = float(m.get('coefficient') or 0)
        # sum of others = weighted_sum - this_grade*coef (if present)
        this_grade = m.get('grade')
        this_contrib = 0.0
        if this_grade is not None:
            try:
                this_contrib = float(this_grade) * coef
            except Exception:
                this_contrib = 0.0
        others_sum = weighted_sum - this_contrib
        # to reach target: (others_sum + required * coef) / total_coef >= target
        # required = (target * total_coef - others_sum) / coef
        required = None
        if coef > 0 and total_coef > 0:
            required = (target * total_coef - others_sum) / coef
        # Interpret required value and compute a clamped display value (0..20)
        if required is None:
            req_val = None
            clamped = None
            impossible = False
        else:
            try:
                req_val = float(required)
            except Exception:
                req_val = None
            # clamp to grading bounds for display; mark impossible if >20
            if req_val is None:
                clamped = None
                impossible = False
            else:
                clamped = max(0.0, min(20.0, req_val))
                impossible = (req_val > 20.0)
        res = dict(m)
        res['required_for_target'] = req_val
        res['required_for_target_clamped'] = None if clamped is None else round(clamped, 2)
        res['required_impossible'] = impossible
        results.append(res)
    return results


def distribute_required_grades(matieres: List[Dict[str, Any]], target: float) -> Dict[str, Any]:
    """Suggest a distribution of grades across matieres to reach `target`.

    Strategy:
    - Compute total required points: target * total_coef.
    - Subtract contributions from known grades.
    - Distribute remaining required points across unknown-grade matieres proportionally
      to their coefficients, clamping each suggested grade to 0..20. If clamping
      causes shortfall, iteratively fill capped matieres and redistribute.
    Returns a dict with keys:
      - possible: bool
      - per_matiere: list of matieres with 'suggested_grade' and 'suggested_impossible'
    """
    # compute total coef and known contributions
    total_coef = 0.0
    known_sum = 0.0
    for m in matieres:
        coef = float(m.get('coefficient') or 0)
        total_coef += coef
        g = m.get('grade')
        if g is not None:
            try:
                known_sum += float(g) * coef
            except Exception:
                pass

    if total_coef <= 0:
        return {"possible": False, "per_matiere": []}

    target_points = float(target) * total_coef
    remaining = target_points - known_sum

    # prepare unknown matieres list
    unknowns = [m for m in matieres if m.get('grade') is None]
    per = [dict(m) for m in matieres]

    if remaining <= 0:
        # Already achieved; suggest 0 for unknowns
        for p in per:
            if p.get('grade') is None:
                p['suggested_grade'] = 0.0
                p['suggested_impossible'] = False
        return {"possible": True, "per_matiere": per}

    # Greedy distribution: prioritize subjects with highest coefficient.
    # For each unknown matiere, filling it gives `coef * grade` points. To reach
    # remaining points with minimal grade increases, allocate to highest-coef
    # unknowns first (fill towards 20), then proceed to next.
    suggestions = {}
    rem = remaining
    possible = True

    # sort unknowns by coefficient descending
    unknowns_sorted = sorted(unknowns, key=lambda x: float(x.get('coefficient') or 0), reverse=True)
    for m in unknowns_sorted:
        coef = float(m.get('coefficient') or 0)
        if coef <= 0:
            suggestions[id(m)] = None
            continue
        max_points = 20.0 * coef
        take = min(rem, max_points)
        if take <= 0:
            suggestions[id(m)] = 0.0
            continue
        # grade needed on this matiere = take / coef
        grade = take / coef
        # clamp just in case
        grade = max(0.0, min(20.0, grade))
        suggestions[id(m)] = round(grade, 2)
        rem -= take
        if rem <= 1e-6:
            rem = 0
            break

    if rem > 1e-6:
        # Even filling all to 20 doesn't meet the target
        possible = False

    # Build per list with suggested grades
    for p in per:
        if p.get('grade') is not None:
            p['suggested_grade'] = p.get('grade')
            p['suggested_impossible'] = False
        else:
            # find matching unknown by name+coef
            match = None
            for u in unknowns:
                if u.get('nom') == p.get('nom') and (u.get('coefficient') == p.get('coefficient')):
                    match = u
                    break
            val = suggestions.get(id(match)) if match is not None else None
            p['suggested_grade'] = None if val is None else val
            p['suggested_impossible'] = (not possible)

    return {"possible": possible, "per_matiere": per}


def distribute_by_coefficient_tiers(matieres: List[Dict[str, Any]], target: float) -> Dict[str, Any]:
    """Distribute required grades using coefficient-tier buckets defined by the user:

    - Highest-coefficient subjects: allowed grade range 5..9
    - Middle-coefficient subjects: allowed grade range 10..15
    - Lowest-coefficient subjects: allowed grade range 15..20

    The function starts each unknown subject at the tier minimum, computes the
    resulting weighted sum and increases grades (within each subject's max)
    prioritizing subjects with the lowest coefficient first (they have the
    highest upper bound here), until the overall target is met or all caps are
    reached.
    """
    # compute total coef and known contributions
    total_coef = 0.0
    known_sum = 0.0
    for m in matieres:
        coef = float(m.get('coefficient') or 0)
        total_coef += coef
        g = m.get('grade')
        if g is not None:
            try:
                known_sum += float(g) * coef
            except Exception:
                pass

    if total_coef <= 0:
        return {"possible": False, "per_matiere": []}

    target_points = float(target) * total_coef
    # Prepare per-matiere working list
    n = len(matieres)
    # sort by coefficient descending to determine tiers
    sorted_idx = sorted(range(n), key=lambda i: float(matieres[i].get('coefficient') or 0), reverse=True)

    # partition into three tiers (top, middle, bottom)
    top_count = (n + 2) // 3  # roughly ceil(n/3)
    mid_count = (n + 1) // 3
    # bottom_count = n - top_count - mid_count

    # decide tier ranges based on target
    # For target == 13, use: top=(10..15), mid=(10..15), bottom=(15..20)
    # Otherwise default to: top=(5..9), mid=(10..15), bottom=(15..20)
    try:
        targ = float(target)
    except Exception:
        targ = None

    if targ is not None and abs(targ - 13.0) < 1e-6:
        top_range = (10.0, 15.0)
        mid_range = (10.0, 15.0)
        # per request: cap the low-coefficient tier max to 18 for target 13
        bottom_range = (15.0, 18.0)
    elif targ is not None and abs(targ - 10.0) < 1e-6:
        # special rule for target 10: cap low-coef max to 18
        top_range = (5.0, 9.0)
        mid_range = (10.0, 15.0)
        bottom_range = (15.0, 18.0)
    else:
        top_range = (5.0, 9.0)
        mid_range = (10.0, 15.0)
        bottom_range = (15.0, 20.0)
    
    # assign min/max per matiere
    bounds = []  # list of (min, max)
    tier_map = {}
    for rank, idx in enumerate(sorted_idx):
        if rank < top_count:
            # cap top tier maximum to 18 as requested
            mn, mx = top_range
            mx = min(mx, 18.0)
            tier_map[idx] = (mn, mx)
        elif rank < top_count + mid_count:
            tier_map[idx] = mid_range
        else:
            tier_map[idx] = bottom_range

    # build initial suggestions: known grades stay, unknowns set to tier min
    per = [dict(m) for m in matieres]
    current_points = 0.0
    for i, p in enumerate(per):
        coef = float(p.get('coefficient') or 0)
        g = p.get('grade')
        mn, mx = tier_map.get(i, (10.0, 15.0))
        if g is not None:
            try:
                current_points += float(g) * coef
                p['suggested_grade'] = float(g)
                p['suggested_impossible'] = False
            except Exception:
                p['suggested_grade'] = None
                p['suggested_impossible'] = False
        else:
            # start at tier minimum
            p['suggested_grade'] = mn
            p['suggested_impossible'] = False
            current_points += mn * coef

    deficit = target_points - current_points
    if deficit <= 1e-6:
        # target already met with minimums
        return {"possible": True, "per_matiere": [
            {**p, 'suggested_grade': None if p.get('suggested_grade') is None else round(p['suggested_grade'], 2)}
            for p in per
        ]}

    # list of unknown indexes (those we initialized from tier mins)
    unknowns = [i for i, m in enumerate(matieres) if m.get('grade') is None]

    # prioritize increasing subjects with lowest coefficient first (they have the highest upper bound per user request)
    unknowns_sorted = sorted(unknowns, key=lambda i: float(matieres[i].get('coefficient') or 0))

    rem = deficit
    for i in unknowns_sorted:
        coef = float(matieres[i].get('coefficient') or 0)
        if coef <= 0:
            continue
        mn, mx = tier_map.get(i, (10.0, 15.0))
        current_g = per[i].get('suggested_grade') or mn
        # max additional points this matiere can contribute (grade increase * coef)
        max_additional_points = (mx - current_g) * coef
        if max_additional_points <= 0:
            continue
        take = min(rem, max_additional_points)
        grade_increase = take / coef
        per[i]['suggested_grade'] = round(current_g + grade_increase, 2)
        rem -= take
        if rem <= 1e-6:
            rem = 0
            break

    possible = (rem <= 1e-6)

    # finalize: clamp suggested grades and mark impossible if needed
    for i, p in enumerate(per):
        if p.get('suggested_grade') is None:
            continue
        # ensure within 0..20
        p['suggested_grade'] = max(0.0, min(20.0, float(p['suggested_grade'])))
        p['suggested_impossible'] = (not possible)

    return {"possible": possible, "per_matiere": per}


def analyze(matieres: List[Dict[str, Any]], targets: List[float] = [10.0, 13.0, 16.0]) -> Dict[str, Any]:
    """Run analysis and return a summary dict.

    Output shape:
    {
      "current_average": 12.3,
      "targets": {
         "10": {"per_matiere": [...], "achieved": True/False},
         "13": {...}
      }
    }
    """
    cur = weighted_average(matieres)
    out = {"current_average": round(cur, 2), "targets": {}}
    for t in targets:
        per = required_grade_for_target(matieres, float(t))
        # compute whether current average already meets target
        achieved = cur >= float(t)
        # round required values for readability
        for p in per:
            rf = p.get('required_for_target')
            p['required_for_target'] = None if rf is None else round(rf, 2)
        # compute a suggested distribution that tries to reach the target
        # Use coefficient-tier distribution per user preference (high-coef -> low range, low-coef -> high range)
        try:
            dist = distribute_by_coefficient_tiers(matieres, float(t))
        except Exception:
            # fallback to the original greedy distributor in case of an error
            dist = distribute_required_grades(matieres, float(t))
        out['targets'][str(int(t))] = {"per_matiere": per, "achieved": achieved, "suggestion": dist}
    return out
