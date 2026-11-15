"""All decisions about the false-start definition live HERE, in one place.

Change a value, re-run the pipeline, and every table and label is rebuilt consistently.
Write down what you chose and why - your instructor will ask.
"""

# ---- onset trigger (the rain that makes a farmer plant) ----
TRIGGER_MM = 20.0                 # accumulated rain needed ...
TRIGGER_DAYS = 3                  # ... over this many consecutive days
MIN_WET_DAYS_IN_TRIGGER = 2       # at least this many wet days inside those days
TRIGGER_WET_DAY_MM = 1.0          # a day with rain >= this is a "wet day"

# ---- false start (the dry spell that follows) ----
FOLLOW_DAYS = 30                  # monitor this many days after the trigger
DRY_SPELL_DAYS = 8                # this many consecutive dry days = false start
DRY_DAY_MM = 1.0                  # a day with rain < this is a "dry day"

# ---- which triggers become events ----
FIRST_TRIGGER_ONLY = True         # True: first trigger per window per year. False: every trigger.

# ---- onset search windows, per region: (name, "MM-DD" start, "MM-DD" end) ----
# FIRST GUESS taken from the CHIRPS monthly rainfall calendar. Review against the plots and
# the local agricultural calendar before you trust them.
ONSET_WINDOWS = {
    "Arsi":  [("belg", "02-15", "05-10"), ("meher", "05-25", "07-15")],
    "Bale":  [("main", "02-15", "05-15"), ("second", "08-15", "10-31")],
    "Jimma": [("main", "02-01", "04-30")],
}

# ---- time split ----
TRAIN_END_YEAR = 2015             # events up to this year = train, later years = test
FIRST_YEAR = 1981