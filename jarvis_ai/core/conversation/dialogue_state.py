class DialogueState:
    def __init__(self):
        self.turn_count = 0
        self.last_user_intent = None
        self.last_action = None
        self.confidence_score = 1.0 # Default high confidence

    def update(self, intent=None, action=None, confidence=None):
        self.turn_count += 1
        if intent: self.last_user_intent = intent
        if action: self.last_action = action
        if confidence is not None: self.confidence_score = confidence

    def to_dict(self):
        return {
            "turn_count": self.turn_count,
            "last_user_intent": self.last_user_intent,
            "last_action": self.last_action,
            "confidence_score": self.confidence_score
        }
