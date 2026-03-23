"""OMOP concept ID mappings and clinical rule configurations.

OMOP Concept IDs are standard identifiers from the OHDSI vocabulary.
Using these ensures compatibility when the real OMOP pipeline connects.
"""

# ──────────────────────────────────────────────────────────────────────
# OMOP Concept ID Mappings (cardiac-relevant)
# ──────────────────────────────────────────────────────────────────────

CONCEPT_HEART_RATE = 3027018
CONCEPT_SYSTOLIC_BP = 3004249
CONCEPT_DIASTOLIC_BP = 3012888
CONCEPT_BODY_WEIGHT = 3025315
CONCEPT_SPO2 = 3016502
CONCEPT_TEMPERATURE = 3020891
CONCEPT_RESPIRATORY_RATE = 3024171
CONCEPT_BLOOD_GLUCOSE = 3004501
CONCEPT_BNP = 3022217
CONCEPT_TROPONIN = 3019550
CONCEPT_DAILY_STEPS = 40762499
CONCEPT_SLEEP_DURATION = 40762503

# Human-readable names for each concept
CONCEPT_NAMES = {
    CONCEPT_HEART_RATE: "Heart Rate",
    CONCEPT_SYSTOLIC_BP: "Systolic Blood Pressure",
    CONCEPT_DIASTOLIC_BP: "Diastolic Blood Pressure",
    CONCEPT_BODY_WEIGHT: "Body Weight",
    CONCEPT_SPO2: "Oxygen Saturation (SpO2)",
    CONCEPT_TEMPERATURE: "Temperature",
    CONCEPT_RESPIRATORY_RATE: "Respiratory Rate",
    CONCEPT_BLOOD_GLUCOSE: "Blood Glucose",
    CONCEPT_BNP: "BNP (B-type Natriuretic Peptide)",
    CONCEPT_TROPONIN: "Troponin",
    CONCEPT_DAILY_STEPS: "Daily Steps",
    CONCEPT_SLEEP_DURATION: "Sleep Duration",
}

# Units for each concept
CONCEPT_UNITS = {
    CONCEPT_HEART_RATE: "bpm",
    CONCEPT_SYSTOLIC_BP: "mmHg",
    CONCEPT_DIASTOLIC_BP: "mmHg",
    CONCEPT_BODY_WEIGHT: "lbs",
    CONCEPT_SPO2: "%",
    CONCEPT_TEMPERATURE: "°F",
    CONCEPT_RESPIRATORY_RATE: "/min",
    CONCEPT_BLOOD_GLUCOSE: "mg/dL",
    CONCEPT_BNP: "pg/mL",
    CONCEPT_TROPONIN: "ng/mL",
    CONCEPT_DAILY_STEPS: "steps",
    CONCEPT_SLEEP_DURATION: "hours",
}

# Valid concept IDs (for validation)
VALID_CONCEPT_IDS = set(CONCEPT_NAMES.keys())

# ──────────────────────────────────────────────────────────────────────
# Normal Ranges (cardiac post-surgical patients)
# ──────────────────────────────────────────────────────────────────────

NORMAL_RANGES = {
    CONCEPT_HEART_RATE: (60, 100),
    CONCEPT_SYSTOLIC_BP: (90, 140),
    CONCEPT_DIASTOLIC_BP: (60, 90),
    CONCEPT_SPO2: (95, 100),
    CONCEPT_TEMPERATURE: (97.0, 99.5),
    CONCEPT_RESPIRATORY_RATE: (12, 20),
    CONCEPT_BLOOD_GLUCOSE: (70, 140),
    CONCEPT_BNP: (0, 100),
    CONCEPT_TROPONIN: (0, 0.04),
}

# ──────────────────────────────────────────────────────────────────────
# Observation Sources
# ──────────────────────────────────────────────────────────────────────

SOURCE_WEARABLE = "wearable"
SOURCE_MANUAL = "manual"
SOURCE_EHR = "ehr"
SOURCE_PATIENT_REPORTED = "patient_reported"
SOURCE_CALCULATED = "calculated"

SOURCE_CHOICES = [
    (SOURCE_WEARABLE, "Wearable Device"),
    (SOURCE_MANUAL, "Manual Entry"),
    (SOURCE_EHR, "EHR/OMOP"),
    (SOURCE_PATIENT_REPORTED, "Patient Reported"),
    (SOURCE_CALCULATED, "Calculated"),
]

# ──────────────────────────────────────────────────────────────────────
# Quality Indicators
# ──────────────────────────────────────────────────────────────────────

QUALITY_VERIFIED = "verified"
QUALITY_ESTIMATED = "estimated"
QUALITY_SELF_REPORTED = "self_reported"

QUALITY_CHOICES = [
    (QUALITY_VERIFIED, "Verified"),
    (QUALITY_ESTIMATED, "Estimated"),
    (QUALITY_SELF_REPORTED, "Self-Reported"),
]

# ──────────────────────────────────────────────────────────────────────
# Alert Configuration
# ──────────────────────────────────────────────────────────────────────

ALERT_TYPE_THRESHOLD = "threshold"
ALERT_TYPE_TREND = "trend"
ALERT_TYPE_MISSING_DATA = "missing_data"
ALERT_TYPE_COMBINATION = "combination"

ALERT_TYPE_CHOICES = [
    (ALERT_TYPE_THRESHOLD, "Threshold"),
    (ALERT_TYPE_TREND, "Trend"),
    (ALERT_TYPE_MISSING_DATA, "Missing Data"),
    (ALERT_TYPE_COMBINATION, "Combination"),
]

SEVERITY_INFO = "info"
SEVERITY_YELLOW = "yellow"
SEVERITY_ORANGE = "orange"
SEVERITY_RED = "red"

SEVERITY_CHOICES = [
    (SEVERITY_INFO, "Info"),
    (SEVERITY_YELLOW, "Yellow - Needs Attention"),
    (SEVERITY_ORANGE, "Orange - Escalated"),
    (SEVERITY_RED, "Red - Critical"),
]

ALERT_STATUS_ACTIVE = "active"
ALERT_STATUS_ACKNOWLEDGED = "acknowledged"
ALERT_STATUS_RESOLVED = "resolved"
ALERT_STATUS_DISMISSED = "dismissed"

ALERT_STATUS_CHOICES = [
    (ALERT_STATUS_ACTIVE, "Active"),
    (ALERT_STATUS_ACKNOWLEDGED, "Acknowledged"),
    (ALERT_STATUS_RESOLVED, "Resolved"),
    (ALERT_STATUS_DISMISSED, "Dismissed"),
]

# ──────────────────────────────────────────────────────────────────────
# Trajectory
# ──────────────────────────────────────────────────────────────────────

TRAJECTORY_IMPROVING = "improving"
TRAJECTORY_STABLE = "stable"
TRAJECTORY_CONCERNING = "concerning"
TRAJECTORY_DETERIORATING = "deteriorating"

TRAJECTORY_CHOICES = [
    (TRAJECTORY_IMPROVING, "Improving"),
    (TRAJECTORY_STABLE, "Stable"),
    (TRAJECTORY_CONCERNING, "Concerning"),
    (TRAJECTORY_DETERIORATING, "Deteriorating"),
]

# Triage color mapping from alert severity
SEVERITY_TO_TRIAGE = {
    SEVERITY_RED: "red",
    SEVERITY_ORANGE: "orange",
    SEVERITY_YELLOW: "yellow",
    SEVERITY_INFO: "green",
}

# ──────────────────────────────────────────────────────────────────────
# Vitals used for sparklines and trend charts
# ──────────────────────────────────────────────────────────────────────

SPARKLINE_VITALS = [
    CONCEPT_HEART_RATE,
    CONCEPT_BODY_WEIGHT,
    CONCEPT_SYSTOLIC_BP,
    CONCEPT_SPO2,
]

CHART_VITALS = [
    CONCEPT_HEART_RATE,
    CONCEPT_SYSTOLIC_BP,
    CONCEPT_DIASTOLIC_BP,
    CONCEPT_BODY_WEIGHT,
    CONCEPT_SPO2,
    CONCEPT_TEMPERATURE,
]
