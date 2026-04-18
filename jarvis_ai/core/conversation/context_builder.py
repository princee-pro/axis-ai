class ContextBuilder:
    def __init__(self, brain):
        self.brain = brain

    def build_context(self, conversation_id, recent_messages, summary=None, long_term_memories=None):
        """
        Assemble the final context for the LLM.
        """
        context = []
        
        # 1. System Prompt (Core Identity)
        context.append({"role": "system", "content": "You are Jarvis AI, a strategic assistant. Use the provided context to answer. If unsure, ask for clarification. Do not execute high-risk actions without approval."})
        
        # 2. Long-term memories (Relevant History)
        if long_term_memories:
            mem_text = "\n".join([f"- {m['text']} (Source: {m['source']})" for m in long_term_memories])
            context.append({"role": "system", "content": f"Relevant background info:\n{mem_text}"})
            
        # 3. Summary (Compressed History)
        if summary:
            context.append({"role": "system", "content": f"Summary of earlier conversation: {summary['summary_text']}"})
            
        # 4. Recent turns
        for msg in recent_messages:
            context.append({"role": msg['role'], "content": msg['content']})
            
        return context
