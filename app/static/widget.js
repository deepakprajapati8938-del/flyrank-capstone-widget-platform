(function () {
    "use strict";

    // 1. Identify current script and extract widget id
    var currentScript = document.currentScript || (function () {
        var scripts = document.getElementsByTagName("script");
        return scripts[scripts.length - 1];
    })();

    if (!currentScript) return;

    var scriptUrl = new URL(currentScript.src, window.location.href);
    var widgetId = scriptUrl.searchParams.get("id");
    if (!widgetId) {
        console.error("[FlyRank Widget] Missing required 'id' query parameter.");
        return;
    }

    var apiBase = scriptUrl.origin;

    // 2. Fetch Widget Configuration
    fetch(apiBase + "/widgets/" + encodeURIComponent(widgetId) + "/config")
        .then(function (res) {
            if (!res.ok) throw new Error("Widget configuration not found");
            return res.json();
        })
        .then(function (config) {
            renderWidget(config, apiBase);
        })
        .catch(function (err) {
            console.error("[FlyRank Widget] Failed to load config:", err);
        });

    // 3. Render Widget Form
    function renderWidget(config, apiBase) {
        var mountPoint = document.getElementById("flyrank-widget-root");
        if (!mountPoint) {
            mountPoint = document.createElement("div");
            mountPoint.id = "flyrank-widget-root";
            document.body.appendChild(mountPoint);
        }

        var wrapper = document.createElement("div");
        wrapper.className = "flyrank-widget-card";
        wrapper.innerHTML = [
            '<style>',
            '.flyrank-widget-card { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 24px; box-shadow: 0 10px 25px -5px rgba(0,0,0,0.1); max-width: 420px; margin: 20px auto; color: #1e293b; }',
            '.flyrank-widget-card h3 { margin: 0 0 8px 0; font-size: 1.25rem; font-weight: 700; color: #0f172a; }',
            '.flyrank-widget-card p { margin: 0 0 16px 0; font-size: 0.9rem; color: #64748b; line-height: 1.4; }',
            '.flyrank-input-group { margin-bottom: 14px; text-align: left; }',
            '.flyrank-input-group label { display: block; font-size: 0.8rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; color: #475569; margin-bottom: 4px; }',
            '.flyrank-input-group input, .flyrank-input-group textarea { width: 100%; box-sizing: border-box; padding: 10px 12px; border: 1px solid #cbd5e1; border-radius: 6px; font-size: 0.95rem; outline: none; transition: border-color 0.2s; }',
            '.flyrank-input-group input:focus, .flyrank-input-group textarea:focus { border-color: #3b82f6; ring: 2px #93c5fd; }',
            '.flyrank-btn { width: 100%; background: #2563eb; color: #ffffff; border: none; padding: 12px; font-size: 0.95rem; font-weight: 600; border-radius: 6px; cursor: pointer; transition: background 0.2s; }',
            '.flyrank-btn:hover { background: #1d4ed8; }',
            '.flyrank-btn:disabled { background: #94a3b8; cursor: not-allowed; }',
            '.flyrank-msg { margin-top: 12px; font-size: 0.85rem; border-radius: 6px; padding: 10px; display: none; }',
            '.flyrank-msg.success { background: #dcfce7; color: #166534; display: block; }',
            '.flyrank-msg.error { background: #fee2e2; color: #991b1b; display: block; }',
            '</style>',
            '<h3>' + escapeHtml(config.title) + '</h3>',
            '<p>' + escapeHtml(config.description) + '</p>',
            '<form id="flyrank-lead-form">',
            '  <div class="flyrank-input-group">',
            '    <label>Your Name</label>',
            '    <input type="text" name="name" placeholder="Jane Doe" required />',
            '  </div>',
            '  <div class="flyrank-input-group">',
            '    <label>Work Email</label>',
            '    <input type="email" name="email" placeholder="jane@example.com" required />',
            '  </div>',
            '  <div class="flyrank-input-group">',
            '    <label>Message / Details</label>',
            '    <textarea name="message" rows="3" placeholder="Tell us about your project..."></textarea>',
            '  </div>',
            '  <!-- HONEYPOT SPAM TRAP (Invisible to humans, caught by bots) -->',
            '  <input type="text" name="hp_company_field" style="display:none!important;position:absolute;left:-9999px" tabindex="-1" autocomplete="off" />',
            '  <button type="submit" class="flyrank-btn" id="flyrank-submit-btn">' + escapeHtml(config.button_text || "Submit") + '</button>',
            '  <div class="flyrank-msg" id="flyrank-form-msg"></div>',
            '</form>'
        ].join('\n');

        mountPoint.appendChild(wrapper);

        var form = wrapper.querySelector("#flyrank-lead-form");
        var msgBox = wrapper.querySelector("#flyrank-form-msg");
        var submitBtn = wrapper.querySelector("#flyrank-submit-btn");

        form.addEventListener("submit", function (e) {
            e.preventDefault();
            msgBox.className = "flyrank-msg";
            submitBtn.disabled = true;
            submitBtn.textContent = "Submitting...";

            var payload = {
                widget_id: config.id,
                name: form.name.value.trim(),
                email: form.email.value.trim(),
                message: form.message.value.trim(),
                hp_company_field: form.hp_company_field.value.trim()
            };

            fetch(apiBase + "/submissions", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "Accept": "application/json"
                },
                body: JSON.stringify(payload)
            })
            .then(function (res) {
                if (!res.ok) {
                    return res.json().then(function (err) {
                        throw new Error(err.detail && err.detail.message ? err.detail.message : "Submission rejected");
                    });
                }
                return res.json();
            })
            .then(function (data) {
                msgBox.className = "flyrank-msg success";
                msgBox.textContent = "Thank you! Your submission has been received.";
                form.reset();
                submitBtn.disabled = false;
                submitBtn.textContent = config.button_text || "Submit";
            })
            .catch(function (err) {
                msgBox.className = "flyrank-msg error";
                msgBox.textContent = err.message || "An error occurred. Please try again.";
                submitBtn.disabled = false;
                submitBtn.textContent = config.button_text || "Submit";
            });
        });
    }

    function escapeHtml(str) {
        if (!str) return "";
        return String(str)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }
})();
