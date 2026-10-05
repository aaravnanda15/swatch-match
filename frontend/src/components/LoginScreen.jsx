import { useState } from "react";
import { login } from "../api.js";
import { Logo } from "./Icon.jsx";

export default function LoginScreen() {
  const [passcode, setPasscode] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await login(passcode);
      window.location.reload(); // start fresh, now with the login cookie
    } catch (err) {
      setError(err.message);
      setBusy(false);
    }
  }

  return (
    <div className="weave fixed inset-0 z-50 flex items-center justify-center p-4">
      <form
        onSubmit={submit}
        className="w-full max-w-sm rounded-2xl border border-line bg-card p-6 shadow-[0_8px_30px_rgb(35_29_24/0.08)]"
      >
        <Logo className="h-10 w-10" />
        <h1 className="mt-3 font-display text-2xl font-semibold tracking-tight">Swatch Match</h1>
        <p className="mt-1 text-sm text-muted">Enter the shop's staff passcode to continue.</p>
        <input
          type="password"
          autoFocus
          autoComplete="current-password"
          value={passcode}
          onChange={(e) => setPasscode(e.target.value)}
          aria-label="Staff passcode"
          placeholder="Passcode"
          className="mt-4 w-full rounded-xl border border-line bg-paper/40 px-3 py-3 text-[15px] focus:border-indigo focus:bg-card focus:outline-none"
        />
        {error && <p className="mt-2 text-sm text-madder">{error}</p>}
        <button
          type="submit"
          disabled={busy || !passcode}
          className="mt-4 w-full rounded-xl bg-madder py-3 text-sm font-semibold text-white hover:bg-madder-dark disabled:opacity-50"
        >
          {busy ? "Checking…" : "Open"}
        </button>
      </form>
    </div>
  );
}
