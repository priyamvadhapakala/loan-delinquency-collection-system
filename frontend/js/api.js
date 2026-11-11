(function () {
  "use strict";

  const defaultBaseUrl = "http://127.0.0.1:5000/api";
  const requestedBaseUrl = new URLSearchParams(window.location.search).get("apiBase");
  let baseUrl = defaultBaseUrl;
  if (requestedBaseUrl) {
    try {
      const candidate = new URL(requestedBaseUrl);
      if (candidate.protocol === "http:" && candidate.hostname === "127.0.0.1") {
        baseUrl = candidate.href.replace(/\/$/, "");
      }
    } catch (error) {
      baseUrl = defaultBaseUrl;
    }
  }

  async function request(path, options) {
    let response;
    try {
      response = await fetch(`${baseUrl}${path}`, {
        ...options,
        headers: {
          ...(options?.body ? { "Content-Type": "application/json" } : {}),
          ...options?.headers
        }
      });
    } catch (error) {
      throw new Error(
        "Cannot reach the Flask API at http://127.0.0.1:5000. Start the backend and check the local connection."
      );
    }

    let payload;
    try {
      payload = await response.json();
    } catch (error) {
      throw new Error(`The API returned an unreadable response (HTTP ${response.status}).`);
    }

    if (!response.ok) {
      const message = payload?.error?.message || `The API request failed (HTTP ${response.status}).`;
      const apiError = new Error(message);
      apiError.status = response.status;
      apiError.code = payload?.error?.code || "request_failed";
      throw apiError;
    }

    return payload;
  }

  window.ApiClient = Object.freeze({
    baseUrl,
    get(path) {
      return request(path, { method: "GET" });
    },
    post(path, body) {
      return request(path, { method: "POST", body: JSON.stringify(body) });
    },
    patch(path, body) {
      return request(path, { method: "PATCH", body: JSON.stringify(body) });
    },
    put(path, body) {
      return request(path, { method: "PUT", body: JSON.stringify(body) });
    }
  });
})();
