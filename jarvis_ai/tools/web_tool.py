import webbrowser
from jarvis_ai.core.safety import SafetyManager

class WebTool:
    def __init__(self, execution_mode='mock'):
        self.execution_mode = execution_mode
        self.safety = SafetyManager()
        
    def set_mode(self, mode):
        self.execution_mode = mode

    def open_url(self, url):
        """
        Visit a URL.
        """
        if self.execution_mode == 'real':
            # Use webbrowser for safe real execution
            if self.safety.ask_confirmation(f"Open URL '{url}' in browser"):
                webbrowser.open(url)
                return f"Opened {url} in system browser (REAL)."
            return "Action cancelled by user."

        # Mock implementation
        print(f"[WEB] Opening URL: {url}")
        return f"Opened {url} (MOCK)."

    def click(self, selector):
        """
        Click an element.
        """
        # Mock implementation
        print(f"[WEB] Clicking element: {selector}")
        return f"Clicked {selector} (MOCK)."

    def fill_form(self, selector, value):
        """
        Fill a form field.
        """
        # Mock implementation
        print(f"[WEB] Typing '{value}' into {selector}")
        return f"Filled {selector} with '{value}' (MOCK)."

    def search(self, query):
        """
        Perform a web search.
        """
        # Mock implementation
        print(f"[WEB] Searching for: {query}")
        return f"Search results for '{query}' (MOCK)."
