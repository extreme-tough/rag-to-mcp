skills:
  - name: classify_complaint
    description: >
      Classify a single complaint record into one approved category, assign the
      correct urgency level, provide a one-sentence reason citing the
      description, and set NEEDS_REVIEW when the complaint is ambiguous or too
      vague.
    input: >
      One complaint row as a dictionary containing at least a description and
      any location fields available in the source dataset.
    output: >
      A dictionary with category, priority, reason, and flag, where category is
      restricted to Pothole, Flooding, Streetlight, Waste, Noise, Road Damage,
      Heritage Damage, Heat Hazard, Drain Blockage, or Other.
    error_handling: >
      If the description is vague, missing, or too short to determine a category
      confidently, return category: Other and flag: NEEDS_REVIEW. Never invent
      category names outside the approved list. If a severity keyword is present
      such as injury, child, school, hospital, ambulance, fire, hazard, fell, or
      collapse, set priority to Urgent. Always include a reason that cites
      specific words from the description to prevent missing justification,
      taxonomy drift, and false confidence.

  - name: batch_classify
    description: >
      Read a CSV file of city complaints, classify each valid row, write a
      results CSV, and continue processing even when some rows are malformed.
    input: >
      Path to an input CSV file containing complaint records.
    output: >
      Path to an output CSV file containing the classified rows with category,
      priority, reason, and flag fields.
    error_handling: >
      Skip malformed or incomplete rows, log the issue, and continue processing
      the remaining rows. For vague or ambiguous rows, emit category: Other and
      flag: NEEDS_REVIEW instead of guessing. Preserve the approved category
      enum, required reason text, and urgency triggers to avoid taxonomy drift,
      severity blindness, hallucinated subcategories, and false confidence.
