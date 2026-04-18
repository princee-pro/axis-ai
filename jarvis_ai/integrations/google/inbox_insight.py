"""
Inbox Insight Module.
LLM-assisted email classification and suggested actions.
"""
import json

class InboxInsight:
    def __init__(self, brain):
        self.brain = brain

    def analyze_inbox(self, messages):
        """Analyze a list of messages and return insights."""
        if not messages:
            return {"summaries": [], "urgent_count": 0}

        # Prepare payload for LLM (bounded and sanitized)
        inbox_data = []
        for msg in messages:
            inbox_data.append({
                "id": msg['id'],
                "from": msg.get('from', 'Unknown'),
                "subject": msg.get('subject', 'No Subject'),
                "snippet": msg.get('snippet', '')[:200]
            })

        prompt = f"""
Analyze the following inbox messages and categorize them into: urgent, important, routine, newsletter, or spam-likely.
For each message, identify possible actions: "reply_needed", "calendar_implied", "none", or "follow_up".

Inbox Data (JSON):
{json.dumps(inbox_data, indent=2)}

Return ONLY a JSON object with this structure:
{{
  "summaries": [
    {{
      "id": "message_id",
      "category": "urgent|important|routine|newsletter|spam-likely",
      "action": "reply_needed|calendar_implied|none|follow_up",
      "reason": "short explanation"
    }}
  ],
  "urgent_count": number,
  "top_priority": "id of most urgent message or null"
}}
"""
        try:
            # Use Brain's LLM to classify
            response_text = self.brain.think(prompt)
            # Find JSON block in response
            if "{" in response_text and "}" in response_text:
                json_str = response_text[response_text.find("{"):response_text.rfind("}")+1]
                insight = json.loads(json_str)
                return insight
            else:
                return {"error": "Invalid LLM response format", "raw": response_text[:200]}
        except Exception as e:
            return {"error": str(e)}
