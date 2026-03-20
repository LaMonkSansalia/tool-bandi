"""Simple single-user auth middleware for Tool Bandi."""
import os

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import HTMLResponse, RedirectResponse

AUTH_USER = os.getenv("AUTH_USER", "")
AUTH_PASS = os.getenv("AUTH_PASS", "")

LOGIN_HTML = """<!DOCTYPE html>
<html lang="it">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Tool Bandi — Login</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;700&display=swap" rel="stylesheet">
  <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-slate-100 flex items-center justify-center min-h-screen" style="font-family:'DM Sans',sans-serif">
  <form method="post" class="bg-white p-8 rounded-xl shadow-lg w-96">
    <div class="flex items-center gap-3 mb-6">
      <div class="w-10 h-10 bg-blue-500 rounded-lg flex items-center justify-center">
        <span class="text-white font-bold">TB</span>
      </div>
      <h1 class="text-2xl font-bold text-slate-800">Tool Bandi</h1>
    </div>
    <input name="user" placeholder="Utente" autocomplete="username"
           class="w-full p-3 border border-gray-300 rounded-lg mb-4 text-sm" required>
    <input name="pass" type="password" placeholder="Password" autocomplete="current-password"
           class="w-full p-3 border border-gray-300 rounded-lg mb-6 text-sm" required>
    <button type="submit"
            class="w-full bg-blue-600 text-white p-3 rounded-lg font-medium hover:bg-blue-700 transition-colors">
      Accedi
    </button>
  </form>
</body>
</html>"""


class SimpleAuthMiddleware(BaseHTTPMiddleware):
    """Cookie-session auth. Disabled when AUTH_USER/AUTH_PASS are empty."""

    async def dispatch(self, request, call_next):
        # Auth disabled if env vars not set
        if not AUTH_USER or not AUTH_PASS:
            return await call_next(request)

        # Skip static files
        if request.url.path.startswith("/static"):
            return await call_next(request)

        # Already authenticated
        if request.session.get("authenticated"):
            return await call_next(request)

        # Login page
        if request.url.path == "/login":
            if request.method == "POST":
                form = await request.form()
                if form.get("user") == AUTH_USER and form.get("pass") == AUTH_PASS:
                    request.session["authenticated"] = True
                    return RedirectResponse("/", status_code=303)
                # Wrong credentials — show form again
            return HTMLResponse(LOGIN_HTML)

        # Not authenticated — redirect to login
        return RedirectResponse("/login", status_code=302)
