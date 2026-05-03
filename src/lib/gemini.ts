const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export async function sendChatMessage(
  text: string,
  history: Array<{ role: string; parts: Array<{ text: string }> }>
): Promise<{ text: string }> {
  try {
    const res = await fetch(`${API_BASE}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text, history }),
    });
    if (!res.ok) return { text: "Connection error. Please try again." };
    return await res.json();
  } catch {
    return { text: "Connection error. Please try again." };
  }
}
