"""Safety layer: crisis risk assessment, prompt-injection detection, output guard, reply templates.

Entry points:
    assessment.assess(message, history)   -> SafetyAssessment  (before any generation)
    output_guard.check(reply, ...)        -> GuardedReply      (after generation)
    templates.*                           -> server-side replies for safety-critical turns

Crisis contact details are shown by the frontend banner, not by this package.
"""
