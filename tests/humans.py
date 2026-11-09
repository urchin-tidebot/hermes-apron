"""Disposable browser-authenticated human fixture. Never prints returned credentials."""

import json
import asyncio
import shutil
import os
import subprocess
import uuid

from playwright.async_api import async_playwright
import websockets


class Wire:
    def __init__(self, ws):
        self.ws = ws
        self.n = 0

    async def call(self, method, params):
        self.n += 1
        request_id = str(self.n)
        await self.ws.send(json.dumps({"id": request_id, "method": method, "params": params}))
        while True:
            frame = json.loads(await self.ws.recv())
            if frame.get("id") == request_id:
                assert "result" in frame, "real human RPC refused"
                return frame["result"]


async def enrolled_human(server, credentials=None):
    if credentials is None:
        output = server["root"] / ("invite-" + uuid.uuid4().hex)
        await asyncio.to_thread(
            subprocess.run,
            [
                server["binary"],
                "invite",
                "--state-dir",
                str(server["state"]),
                "--output",
                str(output),
            ],
            check=True,
        )
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            executable_path=os.environ.get("CHROMIUM_EXECUTABLE") or shutil.which("chromium"),
            args=["--no-sandbox"],
        )
        try:
            page = await browser.new_page()
            cdp = await page.context.new_cdp_session(page)
            await cdp.send("WebAuthn.enable")
            authenticator = await cdp.send(
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
            if credentials is not None:
                for credential in credentials:
                    await cdp.send(
                        "WebAuthn.addCredential",
                        {
                            "authenticatorId": authenticator["authenticatorId"],
                            "credential": credential,
                        },
                    )
                await page.goto(server["url"] + "/enroll/")
            else:
                await page.goto(server["url"] + "/enroll/")
                await page.locator("#invite").fill(output.read_text(encoding="utf-8").strip())
                await page.locator("#enroll").click()
                await page.get_by_text("Enrollment complete.", exact=False).wait_for(timeout=15000)
            result = await page.evaluate("""async () => {
              const ws=new WebSocket(location.origin.replace(/^http/,'ws')+'/ws');let n=0;const pending=new Map();
              await new Promise((resolve,reject)=>{ws.onerror=reject;ws.onmessage=e=>{const f=JSON.parse(e.data);if(f.method==='server')resolve();if(f.id&&pending.has(f.id)){const p=pending.get(f.id);pending.delete(f.id);f.error?p.reject(Error('denied')):p.resolve(f.result);}}});
              const rpc=params=>new Promise((resolve,reject)=>{const id=String(++n);pending.set(id,{resolve,reject});ws.send(JSON.stringify({id,method:'auth',params}));});
              try{const o=await rpc({scheme:'webauthn',action:'login',step:'begin'});const c=await navigator.credentials.get({publicKey:PublicKeyCredential.parseRequestOptionsFromJSON(o.public_key)});return await rpc({scheme:'webauthn',action:'login',step:'finish',challenge_id:o.challenge_id,credential:c.toJSON()});}finally{ws.close();}
            }""")
            credentials = (
                await cdp.send(
                    "WebAuthn.getCredentials", {"authenticatorId": authenticator["authenticatorId"]}
                )
            )["credentials"]
        finally:
            await browser.close()
    ws = await websockets.connect(server["ws"], origin=server["url"], proxy=None)
    await ws.recv()
    human = Wire(ws)
    await human.call("auth", {"scheme": "token", "token": result["token"]})
    human.credentials = credentials
    return human, result["you"]["user_id"]
