# reference_database.py
#
# Normative values for NCS parameters, used for Z-score (SD from mean) calculation.
#
# Sources:
#   - AANEM reference values (Chen et al. 2016, Muscle Nerve 54:371-377)
#   - ESTEEM project guidelines (Tankisi et al. 2005, Clin Neurophysiol 116:1571-1580)
#   - Fuglsang-Frederiksen & Pugdahl 2011 (Clin Neurophysiol 122:440-455)
#   - Pediatric values: Valori_normativi_ENG_0-14_mesi.xlsx (Files folder)
#
# SD derivation method (adults):
#   SD = (Mean - LLN) / 2  for lower-bounded parameters (Amp, CV)
#   SD = (ULN - Mean) / 2  for upper-bounded parameters (DML, F-wave latency)
#
# F-wave persistence LLN (ESTEEM, p.2003-2029):
#   Upper extremity (median, ulnar): 50%
#   Tibial nerve:                    80%
#   Peroneal nerve:                  10%

# =============================================================================
# PEDIATRIC DATABASE (0–14 months)
# Source: Valori_normativi_ENG_0-14_mesi.xlsx
# Values given as ranges [min, max]; Mean = midpoint, SD = (max-min)/4
# =============================================================================

# Each entry: (cv_min, cv_max, amp_min, amp_max, lat_min, lat_max)
# amp in mV for motor, µV for sensory; lat = DML for motor, onset lat for sensory
_PEDIATRIC_MOTOR = {
    # nerve_key: {age_months_max: (cv_min, cv_max, amp_mV_min, amp_mV_max, dml_min, dml_max)}
    "medianus": {
        1:  (22, 30, 1.0, 3.0, 3.0, 4.5),
        3:  (25, 35, 2.0, 5.0, 2.5, 4.0),
        6:  (30, 40, 3.0, 6.0, 2.5, 3.5),
        9:  (35, 45, 4.0, 7.0, 2.3, 3.2),
        12: (38, 48, 5.0, 8.0, 2.2, 3.0),
        14: (40, 50, 5.0, 9.0, 2.0, 2.8),
    },
    "ulnaris": {
        1:  (22, 30, 1.0, 3.0, 3.0, 4.5),
        3:  (25, 35, 2.0, 5.0, 2.5, 4.0),
        6:  (30, 40, 3.0, 6.0, 2.5, 3.5),
        9:  (35, 45, 4.0, 7.0, 2.3, 3.2),
        12: (38, 48, 5.0, 8.0, 2.2, 3.0),
        14: (40, 50, 5.0, 9.0, 2.0, 2.8),
    },
    "tibialis": {
        1:  (20, 28, 1.0, 3.0, 3.5, 5.0),
        3:  (22, 32, 2.0, 4.0, 3.0, 4.5),
        6:  (28, 38, 3.0, 5.0, 3.0, 4.0),
        9:  (32, 42, 4.0, 6.0, 2.8, 3.8),
        12: (35, 45, 5.0, 7.0, 2.7, 3.5),
        14: (37, 47, 5.0, 8.0, 2.5, 3.3),
    },
    "peroneus": {
        1:  (20, 28, 0.5, 2.0, 3.5, 5.0),
        3:  (22, 32, 1.0, 3.0, 3.0, 4.5),
        6:  (28, 38, 2.0, 4.0, 3.0, 4.0),
        9:  (32, 42, 3.0, 5.0, 2.8, 3.8),
        12: (35, 45, 3.0, 6.0, 2.7, 3.5),
        14: (37, 47, 3.0, 6.0, 2.5, 3.3),
    },
}

_PEDIATRIC_SENSORY = {
    # nerve_key: {age_months_max: (cv_min, cv_max, amp_uV_min, amp_uV_max)}
    "medianus": {
        1:  (22, 30, 3,  10),
        3:  (25, 35, 5,  15),
        6:  (30, 40, 10, 20),
        9:  (35, 45, 12, 25),
        12: (38, 48, 15, 28),
        14: (40, 50, 15, 30),
    },
    "ulnaris": {
        1:  (22, 30, 3,  10),
        3:  (25, 35, 5,  15),
        6:  (30, 40, 10, 20),
        9:  (35, 45, 12, 25),
        12: (38, 48, 15, 28),
        14: (40, 50, 15, 30),
    },
    "suralis": {
        1:  (20, 28, 3,  8),
        3:  (25, 35, 5,  15),
        6:  (28, 38, 8,  18),
        9:  (32, 42, 10, 20),
        12: (35, 45, 12, 22),
        14: (37, 47, 12, 24),
    },
}


def _get_pediatric_norms(nerve_key, nerve_type, age_months):
    """
    Returns pediatric normative values for a given nerve and age in months.
    Returns None if no pediatric data is available for this nerve.
    """
    if nerve_type == "motor":
        db = _PEDIATRIC_MOTOR
    elif nerve_type == "sensory":
        db = _PEDIATRIC_SENSORY
    else:
        return None

    if nerve_key not in db:
        return None

    age_data = db[nerve_key]
    # Find the appropriate age bracket (use the smallest bracket >= age_months)
    for max_age in sorted(age_data.keys()):
        if age_months <= max_age:
            vals = age_data[max_age]
            break
    else:
        # Older than 14 months — use the 14-month values as approximation
        vals = age_data[max(age_data.keys())]

    if nerve_type == "motor":
        cv_min, cv_max, amp_min, amp_max, dml_min, dml_max = vals
        cv_mean = (cv_min + cv_max) / 2
        cv_sd   = (cv_max - cv_min) / 4   # range ≈ 4 SD
        amp_mean = (amp_min + amp_max) / 2
        amp_sd   = (amp_max - amp_min) / 4
        dml_mean = (dml_min + dml_max) / 2
        dml_sd   = (dml_max - dml_min) / 4
        return {
            "amp": amp_mean, "amp_sd": amp_sd,
            "cv":  cv_mean,  "cv_sd":  cv_sd,
            "dml": dml_mean, "dml_sd": dml_sd,
        }
    else:  # sensory
        cv_min, cv_max, amp_min, amp_max = vals
        cv_mean = (cv_min + cv_max) / 2
        cv_sd   = (cv_max - cv_min) / 4
        amp_mean = (amp_min + amp_max) / 2
        amp_sd   = (amp_max - amp_min) / 4
        return {
            "amp": amp_mean, "amp_sd": amp_sd,
            "cv":  cv_mean,  "cv_sd":  cv_sd,
            "dml": 0.0,      "dml_sd": 0.1,  # not used for sensory
        }


# =============================================================================
# EXAM VALIDATION — ESTEEM minimum nerve requirements
# =============================================================================

# Minimum nerves required for a valid ESTEEM-compliant PNP classification.
# Based on: ESTEEM Table 2 + "NUMERO MINIMO NERVI DA STUDIARE.docx"
#
# The ESTEEM criteria require at least:
#   - 1 sensory nerve (lower limb preferred: sural)
#   - 1 motor nerve (lower limb preferred: peroneal or tibial)
#   - 1 upper limb nerve (motor or sensory: median or ulnar)
# For a FULL study: at least 5 nerves (sural, median, ulnar, peroneal, tibial)

MINIMUM_NERVES = {
    "motor": {
        "required": ["peroneus", "tibialis"],          # at least one lower limb motor
        "recommended": ["medianus", "ulnaris"],        # at least one upper limb motor
    },
    "sensory": {
        "required": ["suralis"],                       # sural is the key lower limb sensory
        "recommended": ["medianus", "ulnaris"],        # upper limb sensory
    },
}

FULL_STUDY_NERVES = {
    "motor":   ["medianus", "ulnaris", "peroneus", "tibialis"],
    "sensory": ["medianus", "ulnaris", "suralis"],
    "fwave":   ["medianus", "ulnaris", "peroneus", "tibialis"],
}


def validate_exam(motor_data, sensory_data, fwave_data):
    """
    Validates whether the studied nerves meet ESTEEM minimum requirements.

    Returns a dict:
        'is_valid': bool — True if minimum criteria are met
        'warnings': list of str — warnings about missing recommended nerves
        'errors':   list of str — errors about missing required nerves
        'coverage': dict — which full-study nerves are present/absent
    """
    warnings = []
    errors = []

    def nerve_keys_present(data_list):
        """Extract normalized nerve keys from a list of nerve dicts."""
        keys = set()
        for row in data_list:
            name = row.get("Nerve", "").lower()
            for key in ["medianus", "median", "ulnaris", "ulnar", "peroneus",
                        "fibularis", "peroneal", "tibialis", "tibial",
                        "suralis", "sural", "radialis", "radial",
                        "femoralis", "femoral", "ischiadicus", "sciatic"]:
                if key in name:
                    # Normalize aliases
                    if key in ("median",):    keys.add("medianus")
                    elif key in ("ulnar",):   keys.add("ulnaris")
                    elif key in ("fibularis", "peroneal"): keys.add("peroneus")
                    elif key in ("tibial",):  keys.add("tibialis")
                    elif key in ("sural",):   keys.add("suralis")
                    elif key in ("radial",):  keys.add("radialis")
                    elif key in ("femoral",): keys.add("femoralis")
                    elif key in ("sciatic",): keys.add("ischiadicus")
                    else:                     keys.add(key)
        return keys

    motor_present   = nerve_keys_present(motor_data)
    sensory_present = nerve_keys_present(sensory_data)
    fwave_present   = nerve_keys_present(fwave_data)

    # --- Check minimum motor ---
    lower_motor_present = motor_present & {"peroneus", "tibialis"}
    if not lower_motor_present:
        errors.append(
            "No lower limb motor nerve studied (Peroneal or Tibial required). "
            "PNP classification may be unreliable."
        )

    upper_motor_present = motor_present & {"medianus", "ulnaris"}
    if not upper_motor_present:
        warnings.append(
            "No upper limb motor nerve studied (Median or Ulnar recommended). "
            "Consider adding at least one for complete assessment."
        )

    # --- Check minimum sensory ---
    if "suralis" not in sensory_present:
        errors.append(
            "Sural nerve not studied. It is the key lower limb sensory nerve "
            "and required for reliable axonal PNP classification."
        )

    upper_sensory_present = sensory_present & {"medianus", "ulnaris"}
    if not upper_sensory_present:
        warnings.append(
            "No upper limb sensory nerve studied (Median or Ulnar recommended)."
        )

    # --- Check if any data at all ---
    if not motor_data and not sensory_data:
        errors.append("No nerve data available. Please load or enter nerve data.")

    # --- Coverage report (for full study) ---
    coverage = {
        "motor":   {n: (n in motor_present)   for n in FULL_STUDY_NERVES["motor"]},
        "sensory": {n: (n in sensory_present)  for n in FULL_STUDY_NERVES["sensory"]},
        "fwave":   {n: (n in fwave_present)    for n in FULL_STUDY_NERVES["fwave"]},
    }

    is_valid = len(errors) == 0
    return {
        "is_valid": is_valid,
        "warnings": warnings,
        "errors":   errors,
        "coverage": coverage,
    }


# =============================================================================
# MAIN NORM LOOKUP — ADULT
# =============================================================================

def get_nerve_norms(nerve_name, nerve_type, age, height, pediatric_mode=False, age_months=None):
    """
    Returns normative values (mean and SD) for a given nerve, type, age, height.

    Parameters:
        nerve_name (str):    Name of the nerve
        nerve_type (str):    'motor', 'sensory', or 'fwave'
        age (float):         Patient age in years (used in adult mode)
        height (float):      Patient height in cm
        pediatric_mode (bool): If True, use pediatric norms
        age_months (float):  Patient age in months (used in pediatric mode)

    Returns:
        dict with keys depending on nerve_type
    """
    name = nerve_name.lower()

    # --- Safety fallback defaults ---
    norms = {
        "amp": 5.0,    "amp_sd": 1.5,
        "cv":  50.0,   "cv_sd":  5.0,
        "dml": 4.0,    "dml_sd": 0.5,
        "fmin": 30.0,  "fmin_sd": 3.0,
        "persist_lln": 20.0
    }

    # -------------------------------------------------------------------------
    # PEDIATRIC MODE
    # -------------------------------------------------------------------------
    if pediatric_mode and age_months is not None:
        # Determine nerve key
        ped_key = None
        for key in ["medianus", "ulnaris", "tibialis", "peroneus", "suralis"]:
            if key in name or (key == "peroneus" and ("fibularis" in name or "peroneal" in name)):
                ped_key = key
                break

        if ped_key is not None:
            ped_norms = _get_pediatric_norms(ped_key, nerve_type, age_months)
            if ped_norms is not None:
                norms.update(ped_norms)
                return norms

        # Pediatric F-wave: no specific data, use scaled adult values
        if nerve_type == "fwave":
            # Neonatal F-waves are much shorter (shorter limbs)
            # Approximate: ULN ~15ms for arm, ~20ms for leg at birth, scaling with age
            scale = min(1.0, age_months / 14.0)  # 0 at birth → 1 at 14 months
            if "tibialis" in name or "peroneus" in name or "fibularis" in name:
                uln_f = 20.0 + scale * 30.0  # 20ms at birth → 50ms at 14 months
                norms["persist_lln"] = 80.0 if "tibialis" in name else 10.0
            else:
                uln_f = 15.0 + scale * 13.0  # 15ms at birth → 28ms at 14 months
                norms["persist_lln"] = 50.0
            norms["fmin"]    = uln_f - 2.0
            norms["fmin_sd"] = 1.5
        return norms

    # -------------------------------------------------------------------------
    # ADULT MODE
    # -------------------------------------------------------------------------

    # =========================================================================
    # MOTOR NERVES — AANEM Table 4 (Chen et al. 2016)
    # =========================================================================
    if nerve_type == "motor":

        # --- MEDIAN MOTOR (APB) ---
        if "medianus" in name or "median" in name:
            norms["amp"]    = 10.0
            norms["amp_sd"] = (10.0 - 4.1) / 2.0   # LLN 4.1 mV
            norms["cv"]     = 58.0
            norms["cv_sd"]  = (58.0 - 49.0) / 2.0  # LLN 49 m/s
            uln_dml = 4.4 if age < 60 else 4.7
            norms["dml"]    = 3.5
            norms["dml_sd"] = (uln_dml - 3.5) / 2.0

        # --- ULNAR MOTOR (ADM) ---
        elif "ulnaris" in name or "ulnar" in name:
            norms["amp"]    = 12.0
            norms["amp_sd"] = (12.0 - 7.9) / 2.0
            if "elbow" in name and "below" not in name:
                norms["cv"]    = 55.0
                norms["cv_sd"] = (55.0 - 43.0) / 2.0  # across elbow LLN 43
            else:
                norms["cv"]    = 60.0
                norms["cv_sd"] = (60.0 - 52.0) / 2.0  # below elbow LLN 52
            norms["dml"]    = 2.8
            norms["dml_sd"] = (3.7 - 2.8) / 2.0       # ULN 3.7

        # --- RADIAL MOTOR (EIP / EDC) ---
        # AANEM: Amp LLN ~3 mV; CV LLN ~50 m/s; DML ULN ~3.0 ms
        elif "radialis" in name or "radial" in name:
            norms["amp"]    = 7.0
            norms["amp_sd"] = (7.0 - 3.0) / 2.0
            norms["cv"]     = 58.0
            norms["cv_sd"]  = (58.0 - 50.0) / 2.0
            norms["dml"]    = 2.2
            norms["dml_sd"] = (3.0 - 2.2) / 2.0

        # --- CIRCUMFLEX / AXILLARY MOTOR (Deltoid) ---
        # Limited normative data; conservative estimates
        elif "circumflexus" in name or "axillaris" in name or "axillary" in name:
            norms["amp"]    = 8.0
            norms["amp_sd"] = (8.0 - 3.0) / 2.0
            norms["cv"]     = 55.0
            norms["cv_sd"]  = (55.0 - 45.0) / 2.0
            norms["dml"]    = 3.5
            norms["dml_sd"] = (5.0 - 3.5) / 2.0

        # --- MUSCULOCUTANEOUS MOTOR (Biceps) ---
        elif "musculocutaneus" in name or "musculocutaneous" in name:
            norms["amp"]    = 8.0
            norms["amp_sd"] = (8.0 - 3.0) / 2.0
            norms["cv"]     = 55.0
            norms["cv_sd"]  = (55.0 - 45.0) / 2.0
            norms["dml"]    = 3.5
            norms["dml_sd"] = (5.5 - 3.5) / 2.0

        # --- ANTERIOR INTEROSSEOUS MOTOR (FPL / FDP) ---
        elif "interosseus anterior" in name or "anterior interosseous" in name:
            norms["amp"]    = 5.0
            norms["amp_sd"] = (5.0 - 2.0) / 2.0
            norms["cv"]     = 55.0
            norms["cv_sd"]  = (55.0 - 45.0) / 2.0
            norms["dml"]    = 4.0
            norms["dml_sd"] = (5.5 - 4.0) / 2.0

        # --- POSTERIOR INTEROSSEOUS MOTOR (EDC) ---
        elif "interosseus posterior" in name or "posterior interosseous" in name:
            norms["amp"]    = 5.0
            norms["amp_sd"] = (5.0 - 2.0) / 2.0
            norms["cv"]     = 55.0
            norms["cv_sd"]  = (55.0 - 45.0) / 2.0
            norms["dml"]    = 4.5
            norms["dml_sd"] = (6.0 - 4.5) / 2.0

        # --- PERONEAL / FIBULAR MOTOR (EDB) ---
        elif "peroneus" in name or "fibularis" in name or "peroneal" in name:
            if age < 40:
                lln_amp = 2.6
            elif age < 60:
                lln_amp = 2.0
            else:
                lln_amp = 1.1
            norms["amp"]    = 5.0
            norms["amp_sd"] = (norms["amp"] - lln_amp) / 2.0
            is_tall = height >= 170
            if age < 40:
                lln_cv = 37.0 if is_tall else 43.0
            else:
                lln_cv = 36.0 if is_tall else 39.0
            norms["cv"]    = 48.0
            norms["cv_sd"] = (48.0 - lln_cv) / 2.0
            norms["dml"]    = 4.5
            norms["dml_sd"] = (6.5 - 4.5) / 2.0

        # --- TIBIAL MOTOR (AH) ---
        elif "tibialis" in name or "tibial" in name:
            norms["amp"]    = 10.0
            norms["amp_sd"] = (10.0 - 4.4) / 2.0
            if height < 160:
                lln_cv = 44.0
            elif height < 170:
                lln_cv = 42.0
            else:
                lln_cv = 37.0
            norms["cv"]    = 48.0
            norms["cv_sd"] = (48.0 - lln_cv) / 2.0
            norms["dml"]    = 4.5
            norms["dml_sd"] = (6.1 - 4.5) / 2.0

        # --- FEMORAL MOTOR (Quadriceps / Vastus medialis) ---
        # AANEM: Amp LLN ~3 mV; DML ULN ~7 ms; CV not routinely measured
        elif "femoralis" in name or "femoral" in name:
            norms["amp"]    = 8.0
            norms["amp_sd"] = (8.0 - 3.0) / 2.0
            norms["cv"]     = 55.0
            norms["cv_sd"]  = (55.0 - 45.0) / 2.0
            norms["dml"]    = 5.0
            norms["dml_sd"] = (7.0 - 5.0) / 2.0

        # --- SCIATIC MOTOR (Biceps femoris) ---
        elif "ischiadicus" in name or "sciatic" in name:
            norms["amp"]    = 8.0
            norms["amp_sd"] = (8.0 - 3.0) / 2.0
            norms["cv"]     = 48.0
            norms["cv_sd"]  = (48.0 - 38.0) / 2.0
            norms["dml"]    = 5.0
            norms["dml_sd"] = (7.0 - 5.0) / 2.0

        # --- GLUTEUS INFERIOR / SUPERIOR ---
        elif "gluteus" in name or "gluteo" in name:
            norms["amp"]    = 6.0
            norms["amp_sd"] = (6.0 - 2.0) / 2.0
            norms["cv"]     = 50.0
            norms["cv_sd"]  = (50.0 - 40.0) / 2.0
            norms["dml"]    = 5.5
            norms["dml_sd"] = (7.5 - 5.5) / 2.0

    # =========================================================================
    # SENSORY NERVES — AANEM Table 3 (Chen et al. 2016)
    # =========================================================================
    elif nerve_type == "sensory":

        # --- MEDIAN SENSORY (Digit II/III antidromic) ---
        if "medianus" in name or "median" in name:
            lln_amp = 19.0 if age < 50 else 10.0
            norms["amp"]    = 40.0
            norms["amp_sd"] = (40.0 - lln_amp) / 2.0
            norms["cv"]     = 56.0
            norms["cv_sd"]  = (56.0 - 43.0) / 2.0
            norms["dml"]    = 3.2
            norms["dml_sd"] = (3.7 - 3.2) / 2.0   # ULN ~3.7 ms (onset lat)

        # --- ULNAR SENSORY (Digit V antidromic) ---
        elif "ulnaris" in name or "ulnar" in name:
            lln_amp = 14.0 if age < 50 else 8.0
            norms["amp"]    = 35.0
            norms["amp_sd"] = (35.0 - lln_amp) / 2.0
            norms["cv"]     = 55.0
            norms["cv_sd"]  = (55.0 - 45.0) / 2.0
            norms["dml"]    = 3.0
            norms["dml_sd"] = (3.5 - 3.0) / 2.0

        # --- SURAL SENSORY ---
        elif "suralis" in name or "sural" in name:
            norms["amp"]    = 15.0
            norms["amp_sd"] = (15.0 - 4.0) / 2.0
            norms["cv"]     = 50.0
            norms["cv_sd"]  = (50.0 - 40.0) / 2.0
            norms["dml"]    = 3.5
            norms["dml_sd"] = (4.4 - 3.5) / 2.0

        # --- RADIAL SENSORY (Superficial radial / anatomical snuffbox) ---
        elif "radialis" in name or "radial" in name:
            norms["amp"]    = 25.0
            norms["amp_sd"] = (25.0 - 11.0) / 2.0
            norms["cv"]     = 58.0
            norms["cv_sd"]  = (58.0 - 50.0) / 2.0
            norms["dml"]    = 2.5
            norms["dml_sd"] = (3.0 - 2.5) / 2.0

        # --- SUPERFICIAL PERONEAL SENSORY (Dorsum of foot) ---
        elif "peroneus" in name or "fibularis" in name or "peroneal" in name:
            norms["amp"]    = 10.0
            norms["amp_sd"] = (10.0 - 3.0) / 2.0
            norms["cv"]     = 48.0
            norms["cv_sd"]  = (48.0 - 38.0) / 2.0
            norms["dml"]    = 3.5
            norms["dml_sd"] = (4.5 - 3.5) / 2.0

        # --- SAPHENOUS SENSORY ---
        elif "saphenus" in name or "saphenous" in name:
            norms["amp"]    = 10.0
            norms["amp_sd"] = (10.0 - 3.0) / 2.0
            norms["cv"]     = 50.0
            norms["cv_sd"]  = (50.0 - 40.0) / 2.0
            norms["dml"]    = 3.5
            norms["dml_sd"] = (4.5 - 3.5) / 2.0

        # --- MEDIAL CUTANEOUS NERVE OF FOREARM ---
        elif "cutaneus antebrachii medialis" in name or "medial forearm" in name:
            norms["amp"]    = 10.0
            norms["amp_sd"] = (10.0 - 3.0) / 2.0
            norms["cv"]     = 55.0
            norms["cv_sd"]  = (55.0 - 45.0) / 2.0
            norms["dml"]    = 2.5
            norms["dml_sd"] = (3.2 - 2.5) / 2.0

        # --- LATERAL CUTANEOUS NERVE OF FOREARM ---
        elif "cutaneus antebrachii lateralis" in name or "lateral forearm" in name:
            norms["amp"]    = 12.0
            norms["amp_sd"] = (12.0 - 4.0) / 2.0
            norms["cv"]     = 55.0
            norms["cv_sd"]  = (55.0 - 45.0) / 2.0
            norms["dml"]    = 2.5
            norms["dml_sd"] = (3.2 - 2.5) / 2.0

        # --- LATERAL CUTANEOUS NERVE OF THIGH ---
        elif "cutaneus femoris lateralis" in name or "lateral thigh" in name:
            norms["amp"]    = 8.0
            norms["amp_sd"] = (8.0 - 2.0) / 2.0
            norms["cv"]     = 48.0
            norms["cv_sd"]  = (48.0 - 38.0) / 2.0
            norms["dml"]    = 3.5
            norms["dml_sd"] = (5.0 - 3.5) / 2.0

        # --- MEDIAL CUTANEOUS NERVE OF ARM ---
        elif "cutaneus brachii medialis" in name:
            norms["amp"]    = 8.0
            norms["amp_sd"] = (8.0 - 2.0) / 2.0
            norms["cv"]     = 52.0
            norms["cv_sd"]  = (52.0 - 42.0) / 2.0
            norms["dml"]    = 2.5
            norms["dml_sd"] = (3.5 - 2.5) / 2.0

        # --- LATERAL CUTANEOUS NERVE OF ARM ---
        elif "cutaneus brachii lateralis" in name:
            norms["amp"]    = 8.0
            norms["amp_sd"] = (8.0 - 2.0) / 2.0
            norms["cv"]     = 52.0
            norms["cv_sd"]  = (52.0 - 42.0) / 2.0
            norms["dml"]    = 2.5
            norms["dml_sd"] = (3.5 - 2.5) / 2.0

        # --- ILIOINGUINAL / ILIOHYPOGASTRIC / GENITOFEMORAL ---
        elif any(k in name for k in ["ilioinguinalis", "iliohypogastricus", "genitofemoralis"]):
            norms["amp"]    = 6.0
            norms["amp_sd"] = (6.0 - 2.0) / 2.0
            norms["cv"]     = 45.0
            norms["cv_sd"]  = (45.0 - 35.0) / 2.0
            norms["dml"]    = 4.0
            norms["dml_sd"] = (6.0 - 4.0) / 2.0

    # =========================================================================
    # F-WAVE — ESTEEM Fig. 4 + height-based regression
    # =========================================================================
    elif nerve_type == "fwave":

        if "tibialis" in name or "tibial" in name:
            base_uln = 56.0
            if height > 170:
                base_uln += (height - 170) * 0.5
            elif height < 160:
                base_uln -= (160 - height) * 0.4
            norms["fmin"]        = base_uln - 4.0
            norms["fmin_sd"]     = 2.0
            norms["persist_lln"] = 80.0

        elif "peroneus" in name or "fibularis" in name or "peroneal" in name:
            base_uln = 54.0
            if height > 170:
                base_uln += (height - 170) * 0.5
            elif height < 160:
                base_uln -= (160 - height) * 0.4
            norms["fmin"]        = base_uln - 4.0
            norms["fmin_sd"]     = 2.0
            norms["persist_lln"] = 10.0

        elif "medianus" in name or "median" in name:
            base_uln = 30.0
            if height > 170:
                base_uln += (height - 170) * 0.2
            elif height < 160:
                base_uln -= (160 - height) * 0.15
            norms["fmin"]        = base_uln - 3.0
            norms["fmin_sd"]     = 1.5
            norms["persist_lln"] = 50.0

        elif "ulnaris" in name or "ulnar" in name:
            base_uln = 31.0
            if height > 170:
                base_uln += (height - 170) * 0.2
            elif height < 160:
                base_uln -= (160 - height) * 0.15
            norms["fmin"]        = base_uln - 3.0
            norms["fmin_sd"]     = 1.5
            norms["persist_lln"] = 50.0

        else:
            base_uln = 32.0
            if height > 170:
                base_uln += (height - 170) * 0.2
            norms["fmin"]        = base_uln - 3.0
            norms["fmin_sd"]     = 2.0
            norms["persist_lln"] = 20.0

    return norms