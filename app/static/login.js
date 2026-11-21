"use strict";

// Ausgelagert aus login.html, damit die Content-Security-Policy ohne 'unsafe-inline' fuer Skripte auskommt.
(function () {
  const qp = new URLSearchParams(location.search).get("lang");
  let lang = qp || localStorage.getItem("fox_lang") || (navigator.language || "de").slice(0, 2);
  if (!I18N[lang]) lang = "de";
  const tr = (k) => I18N[lang][k] || I18N.de[k] || k;
  document.documentElement.lang = lang;
  document.title = tr("login.title");
  document.querySelectorAll("[data-i18n]").forEach((el) => { el.textContent = tr(el.dataset.i18n); });
  document.querySelectorAll("[data-i18n-ph]").forEach((el) => { el.placeholder = tr(el.dataset.i18nPh); });
  document.getElementById("login-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const r = await fetch("/api/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        username: document.getElementById("login-user").value,
        password: document.getElementById("login-pass").value
      })
    });
    if (r.ok) {
      location.href = "/";
    } else {
      document.getElementById("login-err").textContent = tr(r.status === 429 ? "login.locked" : "login.fail");
    }
  });
})();
