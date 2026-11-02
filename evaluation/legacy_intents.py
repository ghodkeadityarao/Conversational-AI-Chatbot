"""The quick-answer rules of the original app.py, copied unchanged in behaviour, so the new rules can be compared with them."""


def legacy_classify(user_message):
    """What the original chat route did with a message: ('name', extracted), ('time',), ('weather',) or ('model',)."""
    if "my name is" in user_message.lower():
        return ("name", user_message.split("my name is")[-1].strip())
    if "what time" in user_message.lower() or "current time" in user_message.lower():
        return ("time",)
    elif "weather" in user_message.lower():
        return ("weather",)
    return ("model",)
