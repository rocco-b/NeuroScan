from reference_database import get_nerve_norms, validate_exam



# =============================================================================
# AUDIT / CONFIGURATION HELPERS
# =============================================================================

def _normalise_reference_overrides(reference_overrides):
    """Return a clean copy of GUI-provided reference overrides.

    The GUI stores generic modality-level values.  Built-in nerve-specific
    references remain the default; overrides are applied only when a custom
    preset is explicitly passed to analyze_data().  SD fields entered as
    coefficients of variation (0 < value < 1) are converted to absolute SD.
    """
    if not reference_overrides:
        return {}

    cleaned = {}
    aliases = {"fwave_persist_lln": "persist_lln"}
    for modality, values in reference_overrides.items():
        if modality not in ("motor", "sensory", "fwave") or not isinstance(values, dict):
            continue
        modality_values = {}
        for raw_key, raw_value in values.items():
            key = aliases.get(raw_key, raw_key)
            try:
                modality_values[key] = float(raw_value)
            except (TypeError, ValueError):
                continue

        # Convert relative SD/CV-style entries to absolute SD when possible.
        for sd_key, mean_key in (("amp_sd", "amp"), ("cv_sd", "cv"),
                                 ("dml_sd", "dml"), ("fmin_sd", "fmin")):
            if sd_key in modality_values and 0 < modality_values[sd_key] < 1 and mean_key in modality_values:
                modality_values[sd_key] = modality_values[sd_key] * modality_values[mean_key]

        cleaned[modality] = modality_values
    return cleaned


def _apply_reference_overrides(norms, nerve_type, reference_overrides):
    """Apply modality-level custom references to a norm dict when provided."""
    out = dict(norms)
    out.setdefault("_override_applied", False)
    overrides = _normalise_reference_overrides(reference_overrides).get(nerve_type, {})
    if not overrides:
        return out

    allowed = {
        "motor": {"amp", "amp_sd", "cv", "cv_sd", "dml", "dml_sd"},
        "sensory": {"amp", "amp_sd", "cv", "cv_sd", "dml", "dml_sd"},
        "fwave": {"fmin", "fmin_sd", "persist_lln"},
    }
    for key, value in overrides.items():
        if key in allowed.get(nerve_type, set()):
            if key.endswith("_sd") and value <= 0:
                continue
            out[key] = value
    out["_override_applied"] = True
    return out


def _safe_z(value, mean, sd):
    """Compute a z-score while guarding against malformed SD values."""
    try:
        if value is None or mean is None or sd is None or float(sd) <= 0:
            return None
        return (float(value) - float(mean)) / float(sd)
    except Exception:
        return None


def _build_evidence(nerve_type, nerve_name, diagnosis, observed, norms, z_scores, components=None, notes=None):
    """Structured audit trail attached to each nerve-level result."""
    return {
        "nerve_type": nerve_type,
        "nerve": nerve_name,
        "diagnosis": diagnosis,
        "observed": observed,
        "norms": dict(norms) if isinstance(norms, dict) else norms,
        "z_scores": z_scores,
        "components": components or {},
        "notes": notes or [],
        "reference_override_applied": bool(isinstance(norms, dict) and norms.get("_override_applied")),
    }


# =============================================================================
# CLASSIFICATION FUNCTIONS — Based on ESTEEM criteria (Tankisi et al. 2005,
# Clin Neurophysiol 116:1571-1580) and Fuglsang-Frederiksen & Pugdahl 2011.
#
# Key reference figures from the paper:
#   Fig. 1  — Sensory CV vs SNAP amplitude
#   Fig. 2  — Motor DML vs CMAP amplitude
#   Fig. 3  — Motor CV vs CMAP amplitude
#   Fig. 4  — F-wave latency vs F-wave frequency
#   Table 2 — PNP classification criteria
# =============================================================================


def classify_motor_cv(sd_amp, sd_cv):
    """
    Classifies a motor nerve segment using CMAP amplitude and conduction velocity.
    Reference: ESTEEM Fig. 3 (Tankisi et al. 2005).

    CRITICAL RULE (from paper, p.1575):
      "For demyelination the decrease in CMAP amplitude is not to exceed 5 SD.
       Motor nerve segments with severely decreased CMAP amplitude due to only
       a few remaining motor units are interpreted as neuropathic."

    Zones (SD from mean of controls):
      Normal:                  CV > -2.0 SD  AND  Amp > -2.0 SD
      Axonal loss:             Amp <= -2.5 SD  AND  CV <= -2.5 SD (not severely slow)
      Neuropathic (grey zone): everything else not meeting demyelinating criteria
      Probable demyelinating:  CV between -4.5 and -5.5 SD  AND  Amp > -5.0 SD
      Definite demyelinating:  CV <= -5.5 SD  AND  Amp > -5.0 SD
    """
    # --- Demyelinating checks (highest priority, but capped by amplitude) ---
    # If CMAP is too low (< -5 SD), we cannot reliably infer demyelination.
    amp_allows_demyelination = sd_amp > -5.0

    if sd_cv <= -5.5:
        if amp_allows_demyelination:
            return "Re/demyelinating (Definite)"
        else:
            return "Neuropathic"  # Severe amp drop + severe CV drop → neuropathic

    if -5.5 < sd_cv <= -4.5:
        if amp_allows_demyelination:
            return "Re/demyelinating (Probable)"
        else:
            return "Neuropathic"

    # --- Normal zone ---
    if sd_cv > -2.0 and sd_amp > -2.0:
        return "Normal"

    # --- Axonal loss: amplitude reduced AND velocity only mildly affected ---
    # Per ESTEEM Table 2: "CMAP amp >= 2.5 SD decreased AND CV <= 2.5 SD decreased"
    if sd_amp <= -2.5 and sd_cv >= -2.5:
        return "Axonal loss"

    # --- Neuropathic: abnormality present but criteria for above not met ---
    return "Neuropathic"


def classify_sensory_cv(sd_amp, sd_cv):
    """
    Classifies a sensory nerve segment using SNAP amplitude and conduction velocity.
    Reference: ESTEEM Fig. 1 (Tankisi et al. 2005).

    Zones (SD from mean of controls):
      Normal:                  CV > -2.0 SD  AND  Amp > -2.0 SD
      Axonal loss:             Amp <= -2.5 SD  AND  CV <= -2.5 SD (mildly reduced)
      Neuropathic (grey zone): moderate CV reduction with amplitude reduction
      Probable demyelinating:  CV between -4.5 and -5.5 SD
      Definite demyelinating:  CV <= -5.5 SD

    Note: For sensory nerves, the paper states "segments with a severely decreased
    CV are considered demyelinated, regardless of the SNAP amplitude" (p.1574).
    The amplitude cap for demyelination is therefore NOT applied to sensory nerves.
    """
    # --- Demyelinating checks (no amplitude cap for sensory nerves) ---
    if sd_cv <= -5.5:
        return "Re/demyelinating (Definite)"

    if -5.5 < sd_cv <= -4.5:
        return "Re/demyelinating (Probable)"

    # --- Normal zone ---
    if sd_cv > -2.0 and sd_amp > -2.0:
        return "Normal"

    # --- Axonal loss: SNAP amplitude reduced AND CV only mildly affected ---
    # Per ESTEEM Table 2: "SNAP amp >= 2.5 SD decreased AND sensory CV <= 2.5 SD decreased"
    if sd_amp <= -2.5 and sd_cv >= -2.5:
        return "Axonal loss"

    # --- Neuropathic ---
    return "Neuropathic"


def classify_motor_latency(sd_amp, sd_dml):
    """
    Classifies a motor nerve segment using CMAP amplitude and distal motor latency.
    Reference: ESTEEM Fig. 2 (Tankisi et al. 2005).

    Same amplitude cap rule applies: if CMAP < -5 SD, classify as Neuropathic
    even if DML is very prolonged.

    Zones:
      Normal:                  DML < +2.0 SD  AND  Amp > -2.0 SD
      Axonal loss:             Amp <= -2.5 SD  AND  DML <= +2.5 SD
      Neuropathic:             grey zone
      Probable demyelinating:  DML between +6.0 and +8.0 SD  AND  Amp > -5.0 SD
      Definite demyelinating:  DML >= +8.0 SD  AND  Amp > -5.0 SD
    """
    amp_allows_demyelination = sd_amp > -5.0

    if sd_dml >= 8.0:
        if amp_allows_demyelination:
            return "Re/demyelinating (Definite)"
        else:
            return "Neuropathic"

    if 6.0 <= sd_dml < 8.0:
        if amp_allows_demyelination:
            return "Re/demyelinating (Probable)"
        else:
            return "Neuropathic"

    # --- Normal zone ---
    if sd_dml < 2.0 and sd_amp > -2.0:
        return "Normal"

    # --- Axonal loss: amplitude reduced AND DML only mildly prolonged ---
    # Per ESTEEM Table 2: "CMAP amp >= 2.5 SD decreased AND DML <= 2.5 SD increased"
    if sd_amp <= -2.5 and sd_dml <= 2.5:
        return "Axonal loss"

    # --- Neuropathic ---
    return "Neuropathic"


def classify_fwave(sd_fmin, persistence_val, persistence_lln):
    """
    Classifies an F-wave study using minimum F-wave latency and F-wave frequency.
    Reference: ESTEEM Fig. 4 (Tankisi et al. 2005).

    CRITICAL RULE (from paper, p.1993-1999):
      "To infer demyelination recording of at least 2 F-waves/20 stimuli are required."
      This means persistence must be > 0 (i.e., at least some F-waves present)
      to classify as demyelinating.

    Zones:
      Normal:                  F-lat <= +2.0 SD  AND  persistence >= LLN
      Neuropathic:             F-lat 2.0-7.0 SD  OR  persistence < LLN
      Probable demyelinating:  F-lat +7.0 to +8.0 SD  AND  persistence >= 2/20 (10%)
      Definite demyelinating:  F-lat >= +8.0 SD  AND  persistence >= 2/20 (10%)

    F-wave frequency LLN (from paper, p.2003-2029):
      Upper extremity (median, ulnar): 50%
      Tibial nerve: 80%
      Peroneal nerve: 10%
      (These are set per-nerve in reference_database.py)
    """
    # Minimum persistence to infer demyelination: at least 2/20 stimuli = 10%
    MIN_PERSISTENCE_FOR_DEMYELINATION = 10.0

    # --- Demyelinating checks (require minimum persistence) ---
    if sd_fmin >= 8.0:
        if persistence_val >= MIN_PERSISTENCE_FOR_DEMYELINATION:
            return "Re/demyelinating (Definite)"
        else:
            # Absent/very rare F-waves with prolonged latency → Neuropathic
            return "Neuropathic"

    if sd_fmin >= 7.0:
        if persistence_val >= MIN_PERSISTENCE_FOR_DEMYELINATION:
            return "Re/demyelinating (Probable)"
        else:
            return "Neuropathic"

    # --- Persistence check (below LLN = Neuropathic) ---
    if persistence_val < persistence_lln:
        return "Neuropathic"

    # --- Normal: latency within 2 SD and persistence normal ---
    if sd_fmin < 2.0:
        return "Normal"

    # --- Neuropathic: latency between 2.0 and 7.0 SD with normal persistence ---
    return "Neuropathic"


# =============================================================================
# PATIENT-LEVEL PNP CLASSIFICATION — ESTEEM Table 2
# =============================================================================

def classify_pnp(motor_results, sensory_results, fwave_results):
    """
    Classifies the overall polyneuropathy pattern at the patient level.
    Reference: ESTEEM Table 2 (Tankisi et al. 2005, p.1576).

    Criteria for DEMYELINATING PNP (requires at least one of):
      (a) Definite demyelination in >= 2 segments from DIFFERENT nerves
      (b) 1 definite + 2 probable demyelinated segments from different nerves
      (c) Probable demyelination in >= 4 segments from different nerves

    Criteria for AXONAL PNP (requires):
      (a) >= 2 sensory nerve segments with axonal loss from different nerves, OR
          >= 2 motor nerve segments with axonal loss from different nerves, OR
          1 sensory + 1 motor with axonal loss
      (b) Affection in at least 2 extremities (simplified: >= 2 different nerves)

    Criteria for MIXED PNP:
      Both demyelinating AND axonal criteria fulfilled (in different nerves).

    Returns a dict with:
      'pattern': one of 'Normal', 'Demyelinating', 'Axonal', 'Mixed',
                 'Neuropathic', 'Unclassified', 'N/A (Insufficient Data)'
      'details': human-readable explanation
    """

    def is_definite_demyelinating(diag):
        return "Definite" in diag

    def is_probable_demyelinating(diag):
        return "Probable" in diag

    def is_demyelinating(diag):
        return "Re/demyelinating" in diag

    def is_axonal(diag):
        return diag == "Axonal loss"

    def is_normal(diag):
        return diag == "Normal"

    # Collect all valid nerve results (exclude missing/error)
    all_results = []
    for r in motor_results:
        if r['diagnosis'] not in ("Missing data", "Analysis Error", "N/A"):
            all_results.append(('motor', r['nerve'], r['diagnosis']))
    for r in sensory_results:
        if r['diagnosis'] not in ("Missing data", "Analysis Error", "N/A"):
            all_results.append(('sensory', r['nerve'], r['diagnosis']))
    for r in fwave_results:
        if r['diagnosis'] not in ("Missing data", "Analysis Error", "N/A"):
            all_results.append(('fwave', r['nerve'], r['diagnosis']))

    if not all_results:
        return {'pattern': 'N/A (Insufficient Data)', 'details': 'No valid nerve data available.'}

    # --- Count demyelinating findings ---
    definite_demyel_nerves = set()
    probable_demyel_nerves = set()
    axonal_motor_nerves = set()
    axonal_sensory_nerves = set()
    all_diagnoses = []

    for ntype, nerve, diag in all_results:
        all_diagnoses.append(diag)
        if is_definite_demyelinating(diag):
            definite_demyel_nerves.add(nerve)
        elif is_probable_demyelinating(diag):
            probable_demyel_nerves.add(nerve)
        if is_axonal(diag):
            if ntype == 'motor':
                axonal_motor_nerves.add(nerve)
            elif ntype == 'sensory':
                axonal_sensory_nerves.add(nerve)

    n_definite = len(definite_demyel_nerves)
    n_probable = len(probable_demyel_nerves)
    n_axonal_motor = len(axonal_motor_nerves)
    n_axonal_sensory = len(axonal_sensory_nerves)

    # --- Apply ESTEEM Table 2 criteria ---

    # Demyelinating criteria
    demyelinating_met = (
        n_definite >= 2 or
        (n_definite >= 1 and n_probable >= 2) or
        n_probable >= 4
    )

    # Axonal criteria
    axonal_met = (
        n_axonal_sensory >= 2 or
        n_axonal_motor >= 2 or
        (n_axonal_sensory >= 1 and n_axonal_motor >= 1)
    )

    # --- Determine pattern ---
    if demyelinating_met and axonal_met:
        # Check that the nerves are not identical (ESTEEM rule 3 for Mixed)
        demyel_nerves = definite_demyel_nerves | probable_demyel_nerves
        axonal_nerves = axonal_motor_nerves | axonal_sensory_nerves
        if demyel_nerves != axonal_nerves:
            pattern = 'Mixed'
            details = (f"Mixed PNP: {n_definite} definite + {n_probable} probable demyelinating nerves; "
                       f"{n_axonal_motor} motor + {n_axonal_sensory} sensory axonal nerves.")
        else:
            pattern = 'Demyelinating'
            details = f"Demyelinating PNP: {n_definite} definite, {n_probable} probable demyelinating nerves."
    elif demyelinating_met:
        pattern = 'Demyelinating'
        details = (f"Demyelinating PNP: {n_definite} definite, {n_probable} probable "
                   f"demyelinating nerves across different nerves.")
    elif axonal_met:
        pattern = 'Axonal'
        details = (f"Axonal PNP: {n_axonal_motor} motor + {n_axonal_sensory} sensory "
                   f"nerves with axonal loss.")
    else:
        # No demyelinating or axonal PNP criteria met.
        # Determine whether the exam is essentially normal or just unclassifiable.
        #
        # "Normal" = no nerve has a pathological standalone diagnosis
        # (i.e. no Axonal loss, no Re/demyelinating, no isolated Neuropathic).
        # Split diagnoses like "CV: Normal | DML: Neuropathic" count as borderline.
        #
        # "Unclassified" = some borderline/neuropathic findings exist but not enough
        # to meet ESTEEM PNP criteria (this is the expected result for mild/early cases).

        def has_pathological_finding(diag):
            """Returns True if the diagnosis string contains any non-Normal finding."""
            return (is_axonal(diag) or
                    is_demyelinating(diag) or
                    diag == "Neuropathic" or
                    # Split diagnosis: at least one side is pathological
                    ("|" in diag and any(
                        p.strip().split(": ", 1)[-1] not in ("Normal", "Missing data")
                        for p in diag.split("|")
                    )))

        any_pathological = any(has_pathological_finding(d) for d in all_diagnoses)

        if not any_pathological:
            pattern = 'Normal'
            details = 'All studied nerves are within normal limits.'
        else:
            pattern = 'Unclassified'
            details = (f"Borderline/neuropathic findings present but PNP criteria not met. "
                       f"Definite demyelinating: {n_definite}, Probable: {n_probable}, "
                       f"Axonal motor: {n_axonal_motor}, Axonal sensory: {n_axonal_sensory}.")

    return {'pattern': pattern, 'details': details}


def analyze_data(motor_data, sensory_data, fwave_data, patient_age, patient_height,
                 pediatric_mode=False, age_months=None, reference_overrides=None):
    """
    Main analysis function. Accepts patient age and height for norm lookup.
    In pediatric mode, age_months is used instead of patient_age for norm lookup.
    reference_overrides can contain optional modality-level custom normative
    values coming from the GUI settings dialog.  Built-in nerve-specific
    references are used when no explicit custom override is supplied.
    Returns a dict with 'motor', 'sensory', 'fwave' result lists,
    plus a 'pnp_classification' entry with the patient-level PNP pattern.
    """
    results = {"motor": [], "sensory": [], "fwave": []}

    print(f"--- ANALYSIS START (Age: {patient_age}, Height: {patient_height}, "
          f"Pediatric: {pediatric_mode}, Age months: {age_months}) ---")

    # Helper function per distinguere valori mancanti vs zero assoluto
    def _parse_val(val_str):
        if val_str is None: return "missing", None
        s = str(val_str).strip()
        if not s or s in ['--', 'NC']: return "missing", None
        try:
            val = float(s)
            if val == 0.0: return "zero", 0.0
            return "valid", val
        except ValueError:
            return "missing", None

    # --- MOTOR ANALYSIS ---
    for row in motor_data:
        nerve_name = row.get('Nerve', 'Unknown')
        norms = get_nerve_norms(nerve_name, "motor", patient_age, patient_height,
                                pediatric_mode=pediatric_mode, age_months=age_months)
        norms = _apply_reference_overrides(norms, "motor", reference_overrides)

        amp_status, cv_status, dml_status = "missing", "missing", "missing"
        amp_val = cv_val = dml_val = None
        sd_amp_val = None
        sd_cv_val = None
        sd_dml_val = None
        cv_is_null = False
        dml_is_null = False
        diag_cv = "N/A"
        diag_dml = "N/A"
        diagnosis = "Analysis Error"

        try:
            amp_status, amp_val = _parse_val(row.get('Amp'))
            cv_status, cv_val = _parse_val(row.get('CV'))
            dml_status, dml_val = _parse_val(row.get('DML'))

            # Sezione corretta per il Fix 1
            if amp_status == "zero" or cv_status == "zero" or dml_status == "zero":
                diagnosis = "Axonal loss"
                diag_cv = "Axonal loss"
                diag_dml = "Axonal loss"
                if amp_status != "missing": sd_amp_val = _safe_z(amp_val, norms.get('amp'), norms.get('amp_sd'))
                if cv_status != "missing": sd_cv_val = _safe_z(cv_val, norms.get('cv'), norms.get('cv_sd'))
                if dml_status != "missing": sd_dml_val = _safe_z(dml_val, norms.get('dml'), norms.get('dml_sd'))
            elif amp_status == "missing":
                diagnosis = "Missing data"
                diag_cv, diag_dml = "Missing data", "Missing data"
            else:
                sd_amp_val = _safe_z(amp_val, norms.get('amp'), norms.get('amp_sd'))

                # CV Analysis
                if cv_status == "missing":
                    cv_is_null = True
                    diag_cv = "Missing data"
                else:
                    sd_cv_val = _safe_z(cv_val, norms.get('cv'), norms.get('cv_sd'))
                    diag_cv = classify_motor_cv(sd_amp_val, sd_cv_val) if sd_amp_val is not None and sd_cv_val is not None else "Analysis Error"

                # DML Analysis
                if dml_status == "missing":
                    dml_is_null = True
                    diag_dml = "Missing data"
                else:
                    sd_dml_val = _safe_z(dml_val, norms.get('dml'), norms.get('dml_sd'))
                    diag_dml = classify_motor_latency(sd_amp_val, sd_dml_val) if sd_amp_val is not None and sd_dml_val is not None else "Analysis Error"

                # Combine CV and DML diagnoses
                if diag_cv == "Missing data" and diag_dml == "Missing data":
                    diagnosis = "Missing data"
                elif diag_cv == "Missing data":
                    diagnosis = diag_dml
                elif diag_dml == "Missing data":
                    diagnosis = diag_cv
                elif diag_cv == diag_dml:
                    diagnosis = diag_cv
                else:
                    severity_order = [
                        "Normal", "Axonal loss", "Neuropathic",
                        "Re/demyelinating (Probable)", "Re/demyelinating (Definite)"
                    ]
                    idx_cv = severity_order.index(diag_cv) if diag_cv in severity_order else 2
                    idx_dml = severity_order.index(diag_dml) if diag_dml in severity_order else 2
                    if idx_cv == idx_dml:
                        diagnosis = diag_cv
                    else:
                        diagnosis = f"CV: {diag_cv} | DML: {diag_dml}"

        except Exception as e:
            print(f"Error analyzing motor {nerve_name}: {e}")

        motor_result = {
            "nerve": nerve_name, "diagnosis": diagnosis,
            "diag_cv": diag_cv, "diag_dml": diag_dml,
            "cv_null": cv_is_null, "dml_null": dml_is_null,
            "sd_amp": sd_amp_val, "sd_cv": sd_cv_val, "sd_dml": sd_dml_val,
            "lln_used": norms,
            "raw_amp": amp_val if amp_status != "missing" else None
        }
        motor_result["evidence"] = _build_evidence(
            "motor", nerve_name, diagnosis,
            observed={"Amp": amp_val, "CV": cv_val, "DML": dml_val},
            norms=norms,
            z_scores={"Amp": sd_amp_val, "CV": sd_cv_val, "DML": sd_dml_val},
            components={"CV": diag_cv, "DML": diag_dml},
            notes=["Custom reference preset applied"] if norms.get("_override_applied") else []
        )
        results['motor'].append(motor_result)

    # --- CONDUCTION BLOCK (CB) CHECK ---
    # Identifica il blocco di conduzione (calo >40%) confrontando i segmenti dello stesso nervo
    nerve_bases = ["medianus", "ulnaris", "peroneus", "tibialis"]
    for base in nerve_bases:
        distal_nerves = [n for n in results['motor'] if base in n['nerve'].lower() and any(k in n['nerve'].lower() for k in ["wrist", "ankle"])]
        proximal_nerves = [n for n in results['motor'] if base in n['nerve'].lower() and any(k in n['nerve'].lower() for k in ["elbow", "knee", "underarm", "upper arm"])]

        for dist in distal_nerves:
            for prox in proximal_nerves:
                amp_d = dist.get('raw_amp')
                amp_p = prox.get('raw_amp')
                
                # Se abbiamo i valori e l'ampiezza distale non è zero
                if amp_d is not None and amp_p is not None and amp_d > 0:
                    drop_percent = ((amp_d - amp_p) / amp_d) * 100
                    if drop_percent > 40.0:
                        # Marca come patologico sia il distale (CBD) che il prossimale (CBP)
                        cb_diag = f"Re/demyelinating (Definite) - CB >40%"
                        dist['diagnosis'] = cb_diag
                        prox['diagnosis'] = cb_diag
                        for item in (dist, prox):
                            if isinstance(item.get("evidence"), dict):
                                item["evidence"]["diagnosis"] = cb_diag
                                item["evidence"].setdefault("notes", []).append(
                                    f"Conduction block criterion met: proximal/distal CMAP amplitude drop {drop_percent:.1f}%"
                                )

    # --- SENSORY ANALYSIS ---
    for row in sensory_data:
        nerve_name = row.get('Nerve', 'Unknown')
        norms = get_nerve_norms(nerve_name, "sensory", patient_age, patient_height,
                                pediatric_mode=pediatric_mode, age_months=age_months)
        norms = _apply_reference_overrides(norms, "sensory", reference_overrides)

        amp_status, cv_status, dml_status = "missing", "missing", "missing"
        amp_val = cv_val = dml_val = None
        sd_amp_val, sd_cv_val, sd_dml_val = None, None, None
        cv_is_null = False
        diagnosis = "Analysis Error"

        try:
            amp_status, amp_val = _parse_val(row.get('Amp'))
            cv_status, cv_val = _parse_val(row.get('CV'))
            dml_status, dml_val = _parse_val(row.get('DML', ''))

            if amp_status == "zero" or cv_status == "zero":
                diagnosis = "Axonal loss"
                if amp_status != "missing": sd_amp_val = _safe_z(amp_val, norms.get('amp'), norms.get('amp_sd'))
                if cv_status != "missing": sd_cv_val = _safe_z(cv_val, norms.get('cv'), norms.get('cv_sd'))
            elif amp_status == "missing":
                diagnosis = "Missing data"
            elif cv_status == "missing":
                cv_is_null = True
                sd_amp_val = _safe_z(amp_val, norms.get('amp'), norms.get('amp_sd'))
                if sd_amp_val is not None and sd_amp_val <= -2.5:
                    diagnosis = "Neuropathic"
                else:
                    diagnosis = "Missing data (CV)"
            else:
                sd_amp_val = _safe_z(amp_val, norms.get('amp'), norms.get('amp_sd'))
                sd_cv_val = _safe_z(cv_val, norms.get('cv'), norms.get('cv_sd'))

                if dml_status == "valid" or dml_status == "zero":
                    sd_dml_val = _safe_z(dml_val, norms.get('dml'), norms.get('dml_sd'))

                diagnosis = classify_sensory_cv(sd_amp_val, sd_cv_val) if sd_amp_val is not None and sd_cv_val is not None else "Analysis Error"

        except Exception as e:
            print(f"Error analyzing sensory {nerve_name}: {e}")

        sensory_result = {
            "nerve": nerve_name, "diagnosis": diagnosis,
            "cv_null": cv_is_null,
            "sd_amp": sd_amp_val, "sd_cv": sd_cv_val, "sd_dml": sd_dml_val,
            "lln_used": norms,
        }
        sensory_result["evidence"] = _build_evidence(
            "sensory", nerve_name, diagnosis,
            observed={"Amp": amp_val, "CV": cv_val, "DML": dml_val},
            norms=norms,
            z_scores={"Amp": sd_amp_val, "CV": sd_cv_val, "DML": sd_dml_val},
            components={"CV": diagnosis},
            notes=["Custom reference preset applied"] if norms.get("_override_applied") else []
        )
        results['sensory'].append(sensory_result)

    # --- F-WAVE ANALYSIS ---
    for row in fwave_data:
        nerve_name = row.get('Nerve', 'Unknown')
        norms = get_nerve_norms(nerve_name, "fwave", patient_age, patient_height,
                                pediatric_mode=pediatric_mode, age_months=age_months)
        norms = _apply_reference_overrides(norms, "fwave", reference_overrides)

        fmin_status, persist_status = "missing", "missing"
        fmin_val = persist_val = None
        sd_fmin_val, persistence_val = None, None
        diagnosis = "Analysis Error"

        try:
            fmin_status, fmin_val = _parse_val(row.get('Fmin'))
            persist_status, persist_val = _parse_val(row.get('Persist'))

            if fmin_status == "missing":
                diagnosis = "Missing data"
            elif persist_status == "missing":
                # F-wave assente / non indicata
                sd_fmin_val = _safe_z(fmin_val, norms.get('fmin'), norms.get('fmin_sd')) if fmin_status != "missing" else None
                persistence_val = 0.0
                if sd_fmin_val is not None:
                    diagnosis = classify_fwave(sd_fmin_val, persistence_val, norms['persist_lln'])
                else:
                    diagnosis = "Missing data"
            else:
                sd_fmin_val = _safe_z(fmin_val, norms.get('fmin'), norms.get('fmin_sd'))
                diagnosis = classify_fwave(sd_fmin_val, persist_val, norms['persist_lln']) if sd_fmin_val is not None else "Analysis Error"
                persistence_val = persist_val

        except Exception as e:
            print(f"Error analyzing F-Wave {nerve_name}: {e}")

        fwave_result = {
            "nerve": nerve_name, "diagnosis": diagnosis,
            "sd_fmin": sd_fmin_val, "persist": persistence_val,
            "lln": norms['persist_lln'],
            "lln_used": norms,
        }
        fwave_result["evidence"] = _build_evidence(
            "fwave", nerve_name, diagnosis,
            observed={"Fmin": fmin_val, "Persist": persistence_val},
            norms=norms,
            z_scores={"Fmin": sd_fmin_val},
            components={"F-wave": diagnosis},
            notes=["Custom reference preset applied"] if norms.get("_override_applied") else []
        )
        results['fwave'].append(fwave_result)

    # --- PATIENT-LEVEL PNP CLASSIFICATION ---
    results['pnp_classification'] = classify_pnp(
        results['motor'], results['sensory'], results['fwave']
    )

    return results