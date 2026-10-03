const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000"
).replace(/\/$/, "");

const friendlyMessages = {
  400: "Please check the information and try again.",
  401: "Your session has expired. Please sign in again.",
  403: "You do not have permission to do that.",
  404: "That item could not be found.",
  422: "Some information is invalid. Please review the form.",
  500: "Something went wrong. Please try again shortly."
};

export class ApiError extends Error {
  constructor(message, status = 0) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export async function apiRequest(path, { token, method = "GET", body, signal } = {}) {
  const headers = { Accept: "application/json" };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (token) headers.Authorization = `Bearer ${token}`;

  let response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      signal
    });
  } catch (error) {
    if (error.name === "AbortError") throw error;
    throw new ApiError("Unable to connect to the server.");
  }

  if (response.status === 204) return null;
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = typeof data.detail === "string" ? data.detail : "";
    const message = response.status === 401
      ? friendlyMessages[401]
      : response.status >= 500
        ? friendlyMessages[500]
      : detail || friendlyMessages[response.status] || "The request could not be completed.";
    throw new ApiError(message, response.status);
  }
  return data;
}

export function emitNotificationsChanged() {
  window.dispatchEvent(new Event("smart-market:notifications-changed"));
}

export { API_BASE_URL };
