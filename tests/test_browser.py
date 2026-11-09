"""Real Chromium virtual-authenticator evidence; no production authenticator access."""

import shutil
import os

from playwright.async_api import async_playwright


async def test_virtual_webauthn_registration_and_login(real_server, invitation):
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            executable_path=os.environ.get("CHROMIUM_EXECUTABLE") or shutil.which("chromium"),
            headless=True,
            args=["--no-sandbox"],
        )
        try:
            page = await browser.new_page()
            cdp = await page.context.new_cdp_session(page)
            await cdp.send("WebAuthn.enable")
            await cdp.send(
                "WebAuthn.addVirtualAuthenticator",
                {
                    "options": {
                        "protocol": "ctap2",
                        "transport": "internal",
                        "hasResidentKey": True,
                        "hasUserVerification": True,
                        "isUserVerified": True,
                        "automaticPresenceSimulation": True,
                    }
                },
            )
            requests = []
            page.on("request", lambda request: requests.append(request.url))
            await page.goto(real_server["url"] + "/enroll/")
            await page.locator("#invite").fill(invitation)
            await page.locator("#enroll").click()
            await page.get_by_text("Enrollment complete.", exact=False).wait_for(timeout=15000)
            assert await page.locator("#invite").input_value() == ""
            # A separate native WebAuthn login using the browser's actual authenticator API.
            identity = await page.evaluate("""async () => {
              const ws = new WebSocket(location.origin.replace(/^http/, 'ws') + '/ws');
              const pending = new Map(); let n = 0;
              await new Promise((resolve,reject) => {ws.onerror=reject; ws.onmessage=e => {const f=JSON.parse(e.data); if(f.method==='server')resolve(); if(f.id&&pending.has(f.id)){const p=pending.get(f.id);pending.delete(f.id);f.error?p.reject(Error('denied')):p.resolve(f.result);}}});
              const rpc = params => new Promise((resolve,reject) => {const id=String(++n);pending.set(id,{resolve,reject});ws.send(JSON.stringify({id,method:'auth',params}));});
              try {
                const begin = await rpc({scheme:'webauthn',action:'login',step:'begin'});
                const credential = await navigator.credentials.get({publicKey:PublicKeyCredential.parseRequestOptionsFromJSON(begin.public_key)});
                const result = await rpc({scheme:'webauthn',action:'login',step:'finish',challenge_id:begin.challenge_id,credential:credential.toJSON()});
                return result.you;
              } finally {ws.close();}
            }""")
            assert identity["user_id"]
            assert "bot" not in identity["roles"]
            assert all(u.startswith(real_server["url"] + "/") for u in requests)
        finally:
            await browser.close()


async def test_pinned_frontend_passkey_login_and_native_chat(real_server, invitation):
    # This test exercises the actual self-hosted Svelte client, not a mock renderer.
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            executable_path=os.environ.get("CHROMIUM_EXECUTABLE") or shutil.which("chromium"),
            headless=True,
            args=["--no-sandbox"],
        )
        try:
            page = await browser.new_page()
            cdp = await page.context.new_cdp_session(page)
            await cdp.send("WebAuthn.enable")
            await cdp.send(
                "WebAuthn.addVirtualAuthenticator",
                {
                    "options": {
                        "protocol": "ctap2",
                        "transport": "internal",
                        "hasResidentKey": True,
                        "hasUserVerification": True,
                        "isUserVerified": True,
                        "automaticPresenceSimulation": True,
                    }
                },
            )
            requests, sockets = [], []
            page.on("request", lambda r: requests.append(r.url))
            page.on("websocket", lambda s: sockets.append(s.url))
            await page.goto(real_server["url"] + "/enroll/")
            await page.locator("#invite").fill(invitation)
            await page.locator("#enroll").click()
            await page.get_by_text("Enrollment complete.", exact=False).wait_for(timeout=15000)
            await page.goto(real_server["url"] + "/")
            await page.get_by_test_id("passkey-login").click(timeout=15000)
            await page.get_by_test_id("message-input").wait_for(timeout=15000)
            await page.get_by_test_id("message-input").fill("native browser message")
            await page.get_by_test_id("message-input").press("Enter")
            await page.get_by_text("native browser message", exact=True).wait_for(timeout=10000)
            assert all(url.startswith(real_server["url"] + "/") for url in requests)
            assert all(url == real_server["ws"] for url in sockets)
        finally:
            await browser.close()
