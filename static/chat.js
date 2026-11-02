/* Chat page: sends messages, reads the streamed reply, and shows it as safe Markdown (text is escaped before anything is added). */
(function () {
  const $ = (id) => document.getElementById(id);
  const chat = $("chat"), input = $("input"), send = $("send"), empty = $("empty"), left = $("left");
  let busy = false;

  /* ---------- safe Markdown ---------- */
  function escapeHtml(s) { return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;"); }

  function inline(s) {
    return s
      .replace(/`([^`\n]+)`/g, "<code>$1</code>")
      .replace(/\*\*([^*\n]+)\*\*/g, "<strong>$1</strong>")
      .replace(/(^|[^*])\*([^*\n]+)\*(?!\*)/g, "$1<em>$2</em>")
      .replace(/\[([^\]\n]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');
  }

  function render(markdown) {
    const blocks = [];
    let text = escapeHtml(markdown).replace(/```[a-zA-Z0-9_+-]*\n?([\s\S]*?)(```|$)/g, (_, code) => {
      blocks.push("<pre><code>" + code.replace(/\n$/, "") + "</code></pre>");
      return "\u0000" + (blocks.length - 1) + "\u0000";
    });
    const out = [];
    let list = null;                                         // "ul" or "ol" while inside a list
    const close = () => { if (list) { out.push("</" + list + ">"); list = null; } };
    for (const raw of text.split("\n")) {
      const line = raw.trimEnd();
      const bullet = line.match(/^\s*[-*]\s+(.*)$/), number = line.match(/^\s*\d+[.)]\s+(.*)$/);
      if (bullet || number) {
        const kind = bullet ? "ul" : "ol";
        if (list !== kind) { close(); out.push("<" + kind + ">"); list = kind; }
        out.push("<li>" + inline((bullet || number)[1]) + "</li>");
      } else if (/^\u0000\d+\u0000$/.test(line.trim())) {
        close(); out.push(line.trim());
      } else if (line.trim() === "") {
        close();
      } else {
        close();
        const heading = line.match(/^#{1,6}\s+(.*)$/);
        out.push("<p>" + (heading ? "<strong>" + inline(heading[1]) + "</strong>" : inline(line)) + "</p>");
      }
    }
    close();
    return out.join("").replace(/\u0000(\d+)\u0000/g, (_, i) => blocks[+i]);
  }

  /* ---------- messages ---------- */
  function addRow(role, content, asMarkdown) {
    empty.hidden = true;
    const row = document.createElement("div");
    row.className = "row " + (role === "error" ? "bot error" : role);
    const avatar = document.createElement("img");
    avatar.className = "avatar";
    avatar.alt = "";
    avatar.src = role === "user" ? "/static/user.png" : "/static/logo.png";
    const bubble = document.createElement("div");
    bubble.className = "bubble";
    if (asMarkdown) bubble.innerHTML = render(content); else bubble.textContent = content;
    row.append(avatar, bubble);
    chat.appendChild(row);
    chat.scrollTop = chat.scrollHeight;
    return bubble;
  }

  function setLeft(n) { left.textContent = typeof n === "number" ? n + " questions left" : ""; }

  function setBusy(state) { busy = state; send.disabled = state; input.disabled = state; if (!state) input.focus(); }

  async function ask(message) {
    if (busy || !message.trim()) return;
    addRow("user", message, false);
    input.value = ""; autosize();
    setBusy(true);
    const bubble = addRow("bot", "", false);
    bubble.innerHTML = '<span class="dots"><i></i><i></i><i></i></span>';
    let reply = "", failed = false;
    const controller = new AbortController();
    const giveUp = setTimeout(() => controller.abort(), 90000);
    const note = document.createElement("div");
    note.className = "slow";
    const slowTimer = setTimeout(() => { note.textContent = "Still thinking... this is taking longer than usual."; bubble.appendChild(note); }, 8000);
    try {
      const response = await fetch("/chat", {
        method: "POST", headers: { "Content-Type": "application/json" }, signal: controller.signal,
        body: JSON.stringify({ message, tz: Intl.DateTimeFormat().resolvedOptions().timeZone }),
      });
      if (!response.ok) {
        let data = {};
        try { data = await response.json(); } catch (e) { /* no JSON body */ }
        failed = true;
        bubble.parentElement.remove();
        addRow("error", data.error || "Something went wrong. Please try again.", false);
        if (typeof data.remaining === "number") setLeft(data.remaining);
      } else {
        const reader = response.body.getReader(), decoder = new TextDecoder();
        let buffer = "";
        for (;;) {
          const { value, done } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          let newline;
          while ((newline = buffer.indexOf("\n")) >= 0) {
            const item = JSON.parse(buffer.slice(0, newline)); buffer = buffer.slice(newline + 1);
            if (item.t) { clearTimeout(slowTimer); reply += item.t; bubble.innerHTML = render(reply); chat.scrollTop = chat.scrollHeight; }
            if (item.error) { failed = true; bubble.parentElement.remove(); addRow("error", item.error, false); }
            if (typeof item.remaining === "number") setLeft(item.remaining);
          }
        }
        if (!failed && !reply) { bubble.parentElement.remove(); addRow("error", "I didn't get an answer. Please try again.", false); }
      }
    } catch (e) {
      bubble.parentElement.remove();
      addRow("error", e.name === "AbortError" ? "That took too long, so I stopped waiting. Please try again." : "Could not reach the server. Check your connection and try again.", false);
    } finally {
      clearTimeout(giveUp); clearTimeout(slowTimer);
      setBusy(false);
    }
  }

  function autosize() { input.style.height = "auto"; input.style.height = Math.min(input.scrollHeight, 160) + "px"; }

  $("composer").addEventListener("submit", (e) => { e.preventDefault(); ask(input.value); });
  input.addEventListener("input", autosize);
  input.addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); ask(input.value); } });
  document.querySelectorAll(".starter").forEach((b) => b.addEventListener("click", () => ask(b.textContent)));
  $("help-btn").addEventListener("click", () => { $("help").hidden = !$("help").hidden; });
  $("new-btn").addEventListener("click", async () => {
    if (busy) return;
    try { const r = await fetch("/reset", { method: "POST" }); const d = await r.json(); setLeft(d.remaining); } catch (e) { /* keep the page usable */ }
    chat.querySelectorAll(".row").forEach((n) => n.remove());
    empty.hidden = false;
    input.focus();
  });
  setLeft(parseInt(document.body.dataset.limit, 10));
  input.focus();
})();
