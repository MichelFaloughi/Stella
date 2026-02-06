"use client";

import { useState } from "react";

export default function Home() {
  const [messages, setMessages] = useState<string[]>([]);
  const [input, setInput] = useState("");

  async function sendMessage() {
    if (!input) return;
  
    const userMsg = input;
    setMessages(m => [...m, "You: " + userMsg]);
    setInput("");
  
    const res = await fetch(
      `${process.env.NEXT_PUBLIC_API_URL}/chat`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: userMsg }),
      }
    );
  
    const data = await res.json();
    setMessages(m => [...m, "Stella: " + data.reply]);
  }
  
  

  return (
    <main style={{ padding: 20 }}>
      <h1>Stella</h1>

      <div style={{ marginBottom: 20 }}>
        {messages.map((m, i) => (
          <div key={i}>{m}</div>
        ))}
      </div>

      <input
        value={input}
        onChange={(e) => setInput(e.target.value)}
        placeholder="Type a message"
      />
      <button onClick={sendMessage}>Send</button>
    </main>
  );
}
