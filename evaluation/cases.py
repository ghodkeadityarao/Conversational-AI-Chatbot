"""Messages with the correct handling, written by hand: what a good chatbot should do with each one.

Expected values: 'time', 'date', 'weather' (answer locally), 'name:<Name>' (greet and remember that name),
'name+model:<Name>' (remember the name, then answer the rest of the message), 'model' (send to the language model).
The set is small and was written by the author of the new rules, so it shows the kinds of mistakes, not a population rate.
"""
CASES = [
    # asking for the time
    *[(m, "time") for m in ["What time is it?", "what's the current time", "Tell me the time", "time please", "what is the time now",
                            "Hey, what time is it right now?", "Could you tell me what time it is", "current time", "What time is it",
                            "do you know what time it is", "what's the time", "WHAT TIME IS IT!!", "the time please", "exact time now"]],
    # mentions time but is a different question
    *[(m, "model") for m in ["What time did the Roman Empire fall?", "What time does the movie start?", "Explain time dilation",
                             "What's the best time to visit Japan?", "How much time does it take to learn Python?",
                             "What is the current time zone in Brazil?", "Is it time to buy a house?", "What time is it in Tokyo?",
                             "At what time did World War 2 end?", "What time complexity does binary search have?", "Do you know what time it is in London?",
                             "Write a story about time travel", "what's the current time signature of this song", "Help me manage my time better"]],
    # asking for the date
    *[(m, "date") for m in ["What day is it today?", "what's the date today", "today's date", "What is the date?", "what day is it",
                            "Tell me today's date", "what's today's date", "What day is today?"]],
    # asking about the weather right now
    *[(m, "weather") for m in ["what's the weather today", "weather in Paris", "Is it going to rain tomorrow?", "How's the weather outside",
                               "weather", "what is the temperature right now", "Will it snow this weekend?", "what's the weather like",
                               "weather forecast for tomorrow", "check the weather in Mumbai", "how is the weather here", "tell me the weather tonight"]],
    # weather as a topic
    *[(m, "model") for m in ["What causes rain?", "Explain the weather cycle", "write a poem about the weather", "how do weather balloons work",
                             "weather vs climate: what's the difference?", "what's a good weather app to build in flask", "What temperature does water boil at?",
                             "What was the weather like during the Battle of Waterloo?", "Why is weather hard to predict?", "Explain how a weather forecast model works",
                             "what is the weather api in python", "Describe the climate of Brazil", "Recommend a book about weather history",
                             "what's the weather like on Mars"]],
    # introducing yourself
    *[(m, f"name:{n}") for m, n in [("My name is Sam", "Sam"), ("my name is sam", "Sam"), ("MY NAME IS ADITYA", "ADITYA"), ("my name is aditya rao.", "Aditya Rao"),
                                    ("Hi, my name's Priya!", "Priya"), ("Call me Alex", "Alex"), ("You can call me dr strange", "Dr Strange"),
                                    ("My name is Mary-Jane O'Neil", "Mary-Jane O'Neil"), ("hello, my name is Wei", "Wei"), ("my name is Inigo Montoya", "Inigo Montoya"),
                                    ("My name is Sam!", "Sam"), ("i'm called Zoe", "Zoe"), ("My name is Rahul.", "Rahul"), ("my name is lee", "Lee")]],
    # looks like an introduction but is not
    *[(m, "model") for m in ["My name is not important", "Why do people say my name is in interviews?", "my name is", "my name is 12345",
                             "call me when you can", "Call me maybe lyrics", "What does 'my name is' mean in Spanish?"]],
    # an introduction followed by a real question
    *[(m, f"name+model:{n}") for m, n in [("My name is Sam. What's the capital of France?", "Sam"), ("my name is Priya, can you explain recursion?", "Priya"),
                                          ("Hi, my name is Alex and I need help with Python", "Alex"), ("My name is Rahul. Tell me a joke", "Rahul"),
                                          ("my name is Zoe, what's 12 times 12?", "Zoe"), ("My name is Wei. Summarise the French Revolution", "Wei")]],
    # ordinary questions that must reach the model untouched
    *[(m, "model") for m in ["Tell me a joke", "What is the capital of France?", "Explain recursion simply", "Write a haiku about autumn", "How do I reverse a list in Python?",
                             "Give me three tips to study better", "Translate 'good morning' into Spanish", "Who wrote Pride and Prejudice?", "What is 15% of 240?",
                             "Suggest a name for my dog", "What's the difference between TCP and UDP?", "Summarise the plot of Hamlet", "Hello there", "Thanks!",
                             "How many days are there in a leap year?", "Is Python or JavaScript better for beginners?"]],
]
