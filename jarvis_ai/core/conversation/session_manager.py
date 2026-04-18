import json
from datetime import datetime
from jarvis_ai.core.conversation.dialogue_state import DialogueState
from jarvis_ai.core.conversation.context_builder import ContextBuilder

class SessionManager:
    def __init__(self, brain):
        self.brain = brain
        self.context_builder = ContextBuilder(brain)
        self.sessions = {} # conversation_id -> {state, buffer}

    def get_or_create_session(self, conversation_id):
        if conversation_id not in self.sessions:
            self.sessions[conversation_id] = {
                "state": DialogueState(),
                "buffer": []
            }
        return self.sessions[conversation_id]

    def add_message(self, conversation_id, role, content, actions=None, routing=None):
        session = self.get_or_create_session(conversation_id)
        message = {"role": role, "content": content}
        if isinstance(actions, list) and actions:
            message["actions"] = actions
        if isinstance(routing, dict) and routing:
            message["routing"] = routing
        session["buffer"].append(message)
        self.brain.memory_engine.add_message(
            conversation_id,
            role,
            content,
            actions=actions,
            routing=routing,
        )
        
        # Trigger summarization if threshold reached
        max_turns = int(self.brain.memory_engine.get_setting('memory_session_summarize_every_n_turns', 5))
        if len(session["buffer"]) >= max_turns * 2: # 2 messages per turn (user + assistant)
            self._summarize_session(conversation_id)

    def _summarize_session(self, conversation_id):
        session = self.sessions[conversation_id]
        messages = session["buffer"]
        
        # Simple simulated summarization or call LLM
        # Requirement: "/summarize_every_n_turns"
        prompt = f"Summarize the following chat history briefly:\n" + "\n".join([f"{m['role']}: {m['content']}" for m in messages])
        
        try:
            summary_text = self.brain.advisory.provider.generate(prompt, max_tokens=200)
            self.brain.memory_engine.set_summary(conversation_id, summary_text)
            # Clear buffer and keep only last 2 messages for immediate flow
            session["buffer"] = session["buffer"][-2:]
            self.brain.logger.log(f"[SESSION] Summarized conversation {conversation_id}", "INFO")
        except Exception as e:
            self.brain.logger.log(f"[SESSION] Summarization failed: {e}", "ERROR")

    def get_full_context(self, conversation_id, user_message):
        session = self.get_or_create_session(conversation_id)
        
        # Retrieve relative long term memories
        memories = self.brain.memory_engine.search_long_term_memory(user_message, limit=3)
        summary = self.brain.memory_engine.get_summary(conversation_id)
        
        return self.context_builder.build_context(
            conversation_id, 
            session["buffer"], 
            summary=summary, 
            long_term_memories=memories
        )
