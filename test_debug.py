import sys
sys.path.insert(0, ".")
from tests.test_chip_history import ChipHistoryServerTests
test = ChipHistoryServerTests()
test.setUp()
try:
    print("Sending POST /chat")
    res = test._request("POST", "/chat", {
        "conversation_id": "test-conv-123",
        "message": "show my blocked goals",
    })
    print("CHAT RESPONSE:", res)
    detail = test._request("GET", "/conversations/test-conv-123")
    print("GET DETAIL:", detail)
finally:
    test.tearDown()
