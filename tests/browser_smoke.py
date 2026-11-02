"""Ensaio real de interface/HTTP. Inferência explicitamente simulada; sem GPU/pesos."""
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
from playwright.sync_api import sync_playwright


def test_browser_profile_approval_download_and_scene_controls(tmp_path):
    root = Path(__file__).parents[1]
    voice, video, image = (tmp_path/n for n in ("voice.wav", "base.mp4", "scene.png"))
    def ffmpeg(*args):
        subprocess.run(["ffmpeg", "-y", "-v", "error", *map(str, args)], check=True)
    ffmpeg("-f","lavfi","-i","sine=duration=8",voice)
    ffmpeg("-f","lavfi","-i","color=c=blue:s=64x64:r=25:d=10","-c:v","libx264",video)
    ffmpeg("-i",video,"-frames:v","1",image)
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0)); port = sock.getsockname()[1]
    env={**os.environ,"STUDIO_DATA":str(tmp_path/"data"),"STUDIO_MODELS":str(tmp_path/"models"),
         "STUDIO_UPSTREAMS":str(tmp_path/"upstreams"),"STUDIO_TTS":"mock","STUDIO_LIPSYNC":"mock",
         "STUDIO_NORMALIZE":"1","STUDIO_ACCESS_TOKEN":"browser-smoke-session","CUDA_VISIBLE_DEVICES":"-1"}
    url=f"http://127.0.0.1:{port}"
    with (tmp_path/"server.log").open("w") as log:
        server=subprocess.Popen([sys.executable,"-m","uvicorn","studio.api:app","--host","127.0.0.1",
                                 "--port",str(port)],cwd=root,env=env,stdout=log,stderr=log)
        try:
            with httpx.Client(trust_env=False) as client:
                for _ in range(100):
                    try:
                        if client.get(url).status_code==200: break
                    except httpx.TransportError: pass
                    if server.poll() is not None: raise AssertionError((tmp_path/"server.log").read_text())
                    time.sleep(.1)
                else: raise AssertionError("Servidor não iniciou")
            with sync_playwright() as playwright:
                browser=playwright.chromium.launch(args=["--no-sandbox"])
                page=browser.new_page();errors=[];page.on("pageerror",lambda err:errors.append(str(err)))
                page.goto(url)
                page.locator("summary").click()
                page.locator("#token").fill("browser-smoke-session");page.locator("#connect").click()
                page.wait_for_function("document.querySelector('#cap').textContent.includes('simulação')")
                page.wait_for_function("document.querySelector('#mode option[value=avatar]').disabled")
                page.locator("#name").fill("teste")
                page.locator("#voice").set_input_files(voice);page.locator("#video").set_input_files(video)
                page.locator("#seconds").fill("5");page.locator("#consent").check();page.locator("#create").click()
                page.wait_for_function("document.querySelector('#profile_status').textContent.includes('Perfil criado')")
                page.wait_for_function("document.querySelector('#profile').value==='teste'")
                # Override only the capability response to exercise controls; no GPU request is submitted.
                def capabilities(route):
                    data={"simulation":True,"video":"infinitetalk","tts":"mock","lipsync":"mock",
                          "generative_resources":{name:{"ok":True,"reasons":[]} for name in ("infinitetalk","wan-animate")}}
                    route.fulfill(json=data)
                page.route("**/capabilities",capabilities)
                page.locator("#refresh").click()
                page.wait_for_function("!document.querySelector('#mode option[value=avatar]').disabled")
                page.locator("#mode").select_option("avatar")
                assert page.locator("#continuity_label").is_visible()
                page.locator("#continuity").check();page.locator("#scene_image").set_input_files(image)
                page.wait_for_function("document.querySelector('#scene_preview').naturalWidth===64")
                page.locator("#mode").select_option("motion")
                assert page.locator("#motion_label").is_visible() and not page.locator("#direction_label").is_visible()
                page.locator("#mode").select_option("dub")
                assert not page.locator("#continuity_label").is_visible()
                page.locator("#text").fill("Esta fala demonstra a aprovação antes do vídeo.")
                page.locator("#generate").click()
                page.locator("#approve").wait_for(state="visible",timeout=30000)
                assert not page.locator("#out").is_visible()
                page.locator("#approve").click()
                page.locator("#download").wait_for(state="visible",timeout=30000)
                assert "simulação" in page.locator("#quality").inner_text().lower()
                with page.expect_download() as result: page.locator("#download").click()
                assert Path(result.value.path()).stat().st_size>0
                page.locator("#performance").wait_for(state="visible")
                with page.expect_download() as result: page.locator("#performance").click()
                report=json.loads(Path(result.value.path()).read_text())
                assert report["state"]=="completed" and report["metadata"]["settings"]["tts"]=="mock"
                assert not errors, errors
                browser.close()
        finally:
            server.terminate()
            try: server.wait(timeout=10)
            except subprocess.TimeoutExpired: server.kill();server.wait()
