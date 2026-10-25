/* Thin client for the JSON API. */

/**
 * POST `body` as JSON. Resolves with the parsed response, or throws an Error whose
 * `message` is safe to show and whose `fields` maps input names to validation messages.
 */
export async function post(path, body) {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  let data = null;
  try {
    data = await response.json();
  } catch (_) {
    /* the error body was not JSON */
  }
  if (!response.ok) {
    const error = new Error((data && data.error) || `Request failed (${response.status}).`);
    error.fields = (data && data.fields) || {};
    throw error;
  }
  return data;
}
