# Conversational AI Chatbot

A Flask chat app. Simple questions (the time, the date, weather requests, your name) are answered instantly on the server; everything else goes to Google's Gemini model, and the reply streams into the page as it is written.

## What it has

- **Streaming chat page:** the reply appears word by word, with a typing indicator, safe Markdown (bold, italics, lists, links, code blocks), starter questions, Enter to send and Shift+Enter for a new line, a "New chat" button and a built-in help panel. Dark and light themes follow the device, and it works on phones.
- **A private conversation for every visitor:** each visitor gets a random id in an HTTP-only cookie and their own history and name, kept in server memory for two hours and never written to disk. (The original shared one conversation between everyone.)
- **Quick answers without the model:**
  - the time and date, in the visitor's own time zone, taken from the browser;
  - weather requests, answered honestly as "I don't have live weather data";
  - remembering a name from "My name is ...", "Call me ..." and similar, in any capitalisation, and answering "What's my name?";
  - questions that only mention these words ("What time did the Roman Empire fall?", "How do weather balloons work?") go to the model.
- **The current Gemini SDK:** the `google-genai` package, with the model chosen by a setting (`gemini-3.5-flash-lite` by default for quick answers, and if Google reports that a model name is not available to the key, the app tries `gemini-3.8-flash`, `gemini-3.6-flash` and two 2.5 models and keeps the first that works) and a system prompt that tells the model it cannot see the time or the weather.
- **Protection for the API key:**
  - a limit of 30 model questions per visitor session (new chat does not reset it);
  - 15 messages per minute per network address;
  - a shared daily budget of 1,000 model calls;
  - quick answers cost nothing against these limits, and a failed model call is not counted.
- **No silent waiting:** the server answers immediately, the page shows "Still thinking..." after 8 seconds, a model call that has not finished in 90 seconds is cancelled with a clear message, and an answer that stops part-way keeps the text already shown, and the model is asked for short hidden "thinking" so the first words arrive sooner. The server log records which model answered and how long the first words took.
- **Plain-language errors:** a busy model, a blocked request, a bad key or a missing model each get a clear message; raw error text from Google never reaches the page.
- **Safe by construction:** replies are escaped before display, the page loads no inline scripts or styles (enforced by a content security policy), message length and body size are capped, and no secret is kept in the repository.
- **Works without a key:** the quick answers still work and chat explains that the model is not set up.

## Configuration

Set as environment variables (or in a local `.env`, which git ignores; `.env.example` lists them):

| Variable | Meaning | Default |
|---|---|---|
| `GEMINI_API_KEY` | Google AI Studio key (`GOOGLE_API_KEY` also works) | none |
| `GEMINI_MODEL` | model name | `gemini-3.5-flash-lite` |
| `QUESTIONS_PER_SESSION`, `REQUESTS_PER_MINUTE`, `MODEL_CALLS_PER_DAY` | the limits above | 30, 15, 1000 |
| `MAX_INPUT_CHARS`, `MAX_HISTORY_MESSAGES`, `MAX_OUTPUT_TOKENS` | message length, remembered messages, reply length | 2000, 24, 1024 |
| `MODEL_TIMEOUT_SECONDS` | how long to wait for the model before giving up with a clear message | 90 |
| `TRUST_PROXY` | set to 1 behind a proxy so each visitor's own address is used for the rate limit | off |

## Results

The quick-answer rules were compared with the original ones on 105 hand-written messages with the correct handling known for each (no model calls, no API key). Output is in `evaluation/results/`.

| | Original | New |
|---|---|---|
| Messages handled correctly | 46 of 105 (43.8%) | 104 of 105 (99.0%) |
| Time requests | 8 of 14 | 14 of 14 |
| Date requests | 0 of 8 | 8 of 8 |
| Weather requests | 9 of 12 | 12 of 12 |
| Introductions ("My name is ...") with the right name | 2 of 14 | 14 of 14 |
| Introduction plus a question (name remembered, question answered) | 0 of 6 | 6 of 6 |
| Messages that should reach the model and did | 27 of 51 | 50 of 51 |
| Questions wrongly kept from the model | 24 | 1 |

The original matched words anywhere, so "What time did the Roman Empire fall?" returned the server's clock, every mention of "weather" got the same canned reply, "My name is Sam" with a capital M came back as "Nice to meet you, My name is Sam!", and a name followed by a question dropped the question. The one remaining miss is "what's the weather like on Mars".

## Limits

- **These numbers are in-sample.** The message set was written by the author of the new rules and the rules were tuned on messages of these kinds, so 99% is an upper bound, not a rate for real traffic.
- **The live model was not tested.** There was no API key during development: the Gemini calls were checked against the installed SDK's signatures and tested with a fake client, so the first real request is the first real test. Whether the default model, or any fallback, is available to a given key and its free-tier quota are not verified.
- Conversations and limits live in one process's memory: run a single worker process, and a restart clears them.
- The quick-answer rules understand English only, and the time uses the visitor's browser time zone (UTC if it is missing).
- The Markdown display is deliberately small (no tables or images).
- The model can be wrong; the page says so.

## Repository

| Path | Contents |
|---|---|
| `app.py` | Flask app: page, streaming chat route, new-chat route, limits and headers |
| `chatbot/intents.py` | Quick answers: time, date, weather, names |
| `chatbot/llm.py` | Gemini wrapper: streaming, system prompt, plain-language errors |
| `chatbot/sessions.py` | Per-visitor sessions and the rate and daily limits |
| `chatbot/config.py` | Settings from environment variables |
| `templates/`, `static/` | Chat page, styles and script |
| `evaluation/` | The labelled messages, the original rules, and the comparison with its results |
| `tests/` | 105 tests: quick answers, sessions and limits, the Gemini wrapper (with a fake client), and the app end to end |
