from timer import start_timer, elapsed

PHASES = [
    {"name": "First Round: Uses for Object", "duration_sec": 120},
    {"name": "Keep Going: More Ideas for the Same Object", "duration_sec": 90},
    {"name": "Final Round: Uses for a Different Object", "duration_sec": 210},
]

CATEGORY_LIST = {
    "brick": [
        "Building/Construction",
        "Weapon/Defense",        
        "Landscaping/Gardening",
        "Decoration",
        "Exercise/Weight",
        "Furniture Support/Leveling",
        "Cooking/Heating",
        "Breaking/Smashing",
        "Pathway/Walkway",
        "Anchoring/Weighting Down",
        "Toy/Play",
        "Art Installation"
],
    "newspaper": [
        "Insect Control",
        "Art and Craft",
        "Cleaning",
        "Decorations",
        "Wrapping/Packaging",
        "Fire-related Use",
        "Pet-related Use",
        "Reading/Writing",
        "Games/Entertainment",
        "Clothing",
        "Sculpturing",
        "Dog Care"        
]
}

class SessionState:
    def __init__(self, objects, hints=True):
        self.objects = objects
        self.hints = hints  # whether to show hints during extension
        self.phase_index = 0
        self.started = False
        self.phase_start = None
        self.used_categories = set()
        self.trial_count = 0

    @property
    def current_phase(self):
        return PHASES[self.phase_index]

    @property
    def current_object(self):
        return self.objects[0] if self.phase_index < 2 else self.objects[1]

    def start_phase(self):
        self.phase_start = start_timer()
        self.used_categories = set()

    def next_phase(self):
        self.phase_index += 1

    def record_use(self, use_text):
        from llm_client import map_to_category
        category = map_to_category(use_text, self.current_object, str(CATEGORY_LIST))
        self.used_categories.add(category)
        self.trial_count += 1
        return {
            "trial": self.trial_count,
            "use_text": use_text,
            "category": category,
            "response_time_sec": elapsed(self.phase_start)
        }

    def get_hint(self):
        if not self.hints or self.phase_index != 1:
            return []
        remaining = list(set(CATEGORY_LIST[self.current_object]) - self.used_categories)
        return remaining[:3]  # up to three suggestions
