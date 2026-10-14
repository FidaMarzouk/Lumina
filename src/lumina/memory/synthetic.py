"""Synthetic conversation episodes — for the demo account (seed_demo) and the pattern evaluations.

Every scenario has three paraphrased summaries, so a planted "same pattern, different words"
episode never matches by copy.  These are invented examples, not real user data.
"""

from __future__ import annotations

SCENARIOS: dict[str, dict] = {
    "work_deadline": {
        "macro": "anxiety & fear", "pain": ["work stress and burnout", "low self-worth and self-esteem"],
        "emotion": "fear",
        "summaries": [
            "You talked about a big deadline at work and the thought that you are not good enough for the job. "
            "It left you anxious, and you ended up working late into the night to compensate.",
            "A project due date was weighing on you, and a voice kept saying everyone would see you as a fraud. "
            "You felt tense and stayed up past midnight going over the work again.",
            "Work pressure came back as a deadline approached; you worried your manager would decide you aren't "
            "capable, felt on edge, and kept checking emails long after the day was over.",
        ],
        "elements": {"situation": "big deadline at work", "thoughts": ["I'm not good enough for this job"],
                     "feelings": ["anxious", "tense"], "behaviours": ["worked late into the night"]},
    },
    "sleep": {
        "macro": "life stressors", "pain": ["sleep problems and exhaustion"], "emotion": "sadness",
        "summaries": [
            "You described lying awake for hours, replaying the day, and feeling exhausted and flat the next "
            "morning. You've been scrolling on your phone in bed to pass the time.",
            "Sleep has been patchy; your mind races at night, and you feel drained during the day. Your phone "
            "usually ends up in your hand when you can't drift off.",
            "Nights have felt long and restless, with thoughts looping, and the tiredness is making everything "
            "harder. You often reach for your phone when sleep won't come.",
        ],
        "elements": {"situation": "can't fall asleep at night", "thoughts": ["tomorrow will be a disaster"],
                     "feelings": ["exhausted", "restless"], "behaviours": ["scrolled on my phone in bed"]},
    },
    "friend_conflict": {
        "macro": "social & relationships", "pain": ["relationship and family issues"], "emotion": "anger",
        "summaries": [
            "You talked about an argument with a close friend who cancelled plans again. You felt hurt and "
            "angry, thought they don't value you, and went quiet instead of saying how you felt.",
            "A friend let you down at the last minute, and it stung; you wondered whether you matter to them, "
            "and you pulled back rather than bringing it up.",
            "Plans with a friend fell through once more; you felt dismissed and frustrated, took it as a sign "
            "you're not a priority, and avoided replying to their messages.",
        ],
        "elements": {"situation": "friend cancelled plans again", "thoughts": ["they don't value me"],
                     "feelings": ["hurt", "angry"], "behaviours": ["went quiet and avoided them"]},
    },
    "loneliness": {
        "macro": "social & relationships", "pain": ["loneliness and social isolation"], "emotion": "sadness",
        "summaries": [
            "You shared that weekends feel empty since moving to a new city. You felt lonely, told yourself "
            "people are busy with their own lives, and stayed in most of the time.",
            "Since the move, free time has felt quiet and isolating; you assumed nobody would want to meet up "
            "and spent the weekend alone at home.",
            "You've been missing people since relocating; evenings feel lonely, you hesitate to reach out "
            "because you don't want to bother anyone, and you mostly keep to yourself.",
        ],
        "elements": {"situation": "empty weekends after moving", "thoughts": ["nobody wants to hear from me"],
                     "feelings": ["lonely", "sad"], "behaviours": ["stayed home alone"]},
    },
    "family_visit": {
        "macro": "social & relationships", "pain": ["relationship and family issues"], "emotion": "sadness",
        "summaries": [
            "A visit to your parents brought back old criticism about your choices. You felt small and "
            "frustrated, thought you can never please them, and left earlier than planned.",
            "Time with family turned tense when comments about your career came up; you felt judged, believed "
            "nothing you do is enough for them, and cut the visit short.",
            "Being home stirred up familiar remarks about how you live; you felt deflated and decided it was "
            "easier to leave early than to respond.",
        ],
        "elements": {"situation": "visiting my parents", "thoughts": ["I can never please them"],
                     "feelings": ["frustrated", "small"], "behaviours": ["left early"]},
    },
    "good_week": {
        "macro": "none", "pain": [], "emotion": "joy",
        "summaries": [
            "You shared a lighter week: a walk with a friend and finishing a small project felt good, and you "
            "noticed you had more energy.",
            "Things felt brighter this time; you got outside, saw someone you like, and felt more like "
            "yourself.",
            "A calmer stretch: some time in nature and a finished task gave you a sense of ease and a bit more "
            "energy.",
        ],
        "elements": {"situation": "a walk with a friend", "thoughts": ["I can do this"], "feelings": ["calm", "content"],
                     "behaviours": ["went for a walk"]},
    },
    "exam_pressure": {
        "macro": "life stressors", "pain": ["academic pressure and school stress"], "emotion": "fear",
        "summaries": [
            "Exams are coming up and you feel you're falling behind; you told yourself you'll fail, felt "
            "panicky, and kept putting off studying.",
            "Study pressure is building before the exams; the fear of failing makes it hard to start, and you've "
            "been avoiding your notes.",
            "With the exam date close, you feel overwhelmed and sure you'll do badly, and procrastination has "
            "taken over.",
        ],
        "elements": {"situation": "exams coming up", "thoughts": ["I'm going to fail"], "feelings": ["panicky"],
                     "behaviours": ["put off studying"]},
    },
}
