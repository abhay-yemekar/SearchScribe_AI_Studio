// frontend/lib/api.ts

const BASE_URL = "http://localhost:8000"; // backend Swagger is here

export async function signup(email: string, password: string) {
  const res = await fetch(`${BASE_URL}/auth/signup`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || "Signup failed");
  }

  return res.json();
}

export async function login(email: string, password: string) {
  const res = await fetch(`${BASE_URL}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || "Login failed");
  }

  return res.json();
}

export async function generateContent(query: string, token: string) {
  const res = await fetch(`${BASE_URL}/content/generate`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ query }),
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || "Generate failed");
  }

  return res.json();
}

export async function regenerateArticle(
  article: string,
  style_instruction: string,
  token: string
) {
  const res = await fetch(`${BASE_URL}/content/regenerate`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ article, style_instruction }),
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || "Regenerate failed");
  }

  return res.json();
}
