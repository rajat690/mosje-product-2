/* MoSJE Product 2 – Scholarship Discovery Companion embed snippet.
 *
 * Drop into any web page:
 *   <script src="https://<p2-service>.onrender.com/companion/embed.js" defer></script>
 * Optional attributes on the <script> tag:
 *   data-session="s_..." data-token="..."   resume a session your server created with POST /v1/chat/sessions
 *   data-lang="hi"                          start in Hindi (public sessions)
 *   data-label="Find scholarships"          button text
 *   data-open="true"                        open the panel on page load
 *   data-src / data-om / data-r / data-ref  entry-source attribution (see INTEGRATION_SPEC.md section 7)
 * Attribution params already in the host page URL (src, om, r, ref, utm_*) are passed through automatically.
 * JS API: window.MosjeP2Companion.open() / .close() / .toggle()
 */
(function () {
  var me = document.currentScript || (function () { var s = document.getElementsByTagName("script"); return s[s.length - 1]; })();
  var base = me.src.replace(/\/companion\/embed\.js.*$/, "");
  var d = me.dataset || {};
  var q = [];
  if (d.session) q.push("session=" + encodeURIComponent(d.session));
  if (d.token) q.push("token=" + encodeURIComponent(d.token));
  if (d.lang) q.push("lang=" + encodeURIComponent(d.lang));
  var page = new URLSearchParams(window.location.search);
  ["src", "om", "r", "ref", "utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term"].forEach(function (k) {
    var v = d[k] || page.get(k);
    if (v) q.push(k + "=" + encodeURIComponent(v));
  });
  var url = base + "/companion" + (q.length ? "?" + q.join("&") : "");

  var btn = document.createElement("button");
  btn.type = "button";
  btn.textContent = "🎓 " + (d.label || "Find scholarships");
  btn.setAttribute("aria-label", "Open scholarship discovery chat");
  btn.style.cssText = "position:fixed;right:18px;bottom:18px;z-index:2147483000;background:#0b5394;color:#fff;border:0;border-radius:24px;padding:12px 16px;font:600 14px system-ui,Arial,sans-serif;box-shadow:0 4px 14px #0003;cursor:pointer";

  var panel = document.createElement("div");
  panel.style.cssText = "position:fixed;right:18px;bottom:76px;z-index:2147483000;width:min(380px,calc(100vw - 24px));height:min(600px,calc(100vh - 100px));border-radius:14px;overflow:hidden;box-shadow:0 8px 30px #0004;background:#fff;display:none";
  var frame = null;

  function open() {
    if (!frame) {
      frame = document.createElement("iframe");
      frame.src = url; frame.title = "Scholarship Discovery Companion";
      frame.style.cssText = "width:100%;height:100%;border:0";
      frame.allow = "clipboard-write";
      panel.appendChild(frame);
    }
    panel.style.display = "block";
  }
  function close() { panel.style.display = "none"; }
  function toggle() { panel.style.display === "block" ? close() : open(); }
  btn.onclick = toggle;

  function mount() { document.body.appendChild(panel); document.body.appendChild(btn); if (d.open === "true") open(); }
  if (document.body) mount(); else document.addEventListener("DOMContentLoaded", mount);
  window.MosjeP2Companion = { open: open, close: close, toggle: toggle, url: url };
})();
