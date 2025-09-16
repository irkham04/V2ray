import os, json, base64, asyncio, pathlib, urllib.parse, uuid
from telethon import TelegramClient

SESSION_FILE = "tg_session.session"

if "TG_SESSION_B64" in os.environ:
    with open(SESSION_FILE, "wb") as f:
        f.write(base64.b64decode(os.environ["TG_SESSION_B64"]))

API_ID = int(os.environ["TELEGRAM_API_ID"])
API_HASH = os.environ["TELEGRAM_API_HASH"]

CHANNEL_USERNAME = "foolvpn"
KEYWORD = "Free Public Proxy"
FORCED_SERVER = "quiz.vidio.com"  # tetap dipaksa

def url_encode_remark(s):
    return urllib.parse.quote(s)

def ensure_slash(path):
    if not path:
        return ""
    return path if path.startswith("/") else "/" + path

async def main():
    client = TelegramClient(SESSION_FILE, API_ID, API_HASH)
    await client.start()
    channel = await client.get_entity(CHANNEL_USERNAME)

    # contoh: ambil 5 per tipe (ubah sesuai yang kamu butuhkan)
    target_per_type = 5
    vmess_links, vless_links, trojan_links = [], [], []

    async for m in client.iter_messages(channel, limit=None, reverse=False):
        if not (m.message and KEYWORD.lower() in m.message.lower()):
            continue

        # parse message fields
        info = {}
        for line in m.message.splitlines():
            line = line.strip()
            if ':' in line:
                key, val = line.split(':', 1)
                info[key.strip().lower()] = val.strip()

        vpn_type = info.get("vpn", "").lower()

        # ---------------- VMESS ----------------
        if vpn_type == "vmess" and len(vmess_links) < target_per_type:
            # fields from message
            id_uuid = info.get("uuid") or str(uuid.uuid4())
            port = str(info.get("port") or "443")
            aid_val = str(info.get("aid") or "0")
            tls_flag = info.get("tls", "").strip()
            tls_field = "tls" if tls_flag in ("1", "true", "yes") else ""
            # host header: prefer host, then sni, then forced server
            host_hdr = info.get("host") or info.get("sni") or FORCED_SERVER
            path = ensure_slash(info.get("path", ""))
            ps = info.get("id") or f"vmess-{id_uuid[:6]}"
            # Build vmess JSON with string values where expected
            vmess_obj = {
                "v": "2",
                "ps": ps,
                "add": FORCED_SERVER,         # forced server
                "port": port,
                "id": id_uuid,
                "aid": aid_val,
                "net": "ws",
                "type": "none",
                "host": host_hdr,
                "path": path,
                "tls": tls_field
            }
            # encode
            b64 = base64.b64encode(json.dumps(vmess_obj, ensure_ascii=False).encode()).decode()
            vmess_links.append(f"vmess://{b64}")

        # ---------------- VLESS ----------------
        elif vpn_type == "vless" and len(vless_links) < target_per_type:
            port = info.get("port", "443")
            uuid_val = info.get("uuid") or str(uuid.uuid4())
            path = ensure_slash(info.get("path", ""))
            host = info.get("host", "")
            tls = info.get("tls", "")
            sni = info.get("sni", "")
            mode = info.get("mode", "")
            org = info.get("org", "")
            country = info.get("country", "")
            id_field = info.get("id", "")
            params = ["net=ws", "type=ws"]
            if path: params.append(f"path={path}")
            if host: params.append(f"host={host}")
            if tls in ("1","true","yes"): params.append("security=tls")
            if sni: params.append(f"sni={sni}")
            if mode: params.append(f"mode={mode}")
            param_str = "&".join(params)
            remark = f"{id_field} {country} {org} WS {mode} TLS"
            vless_links.append(f"vless://{uuid_val}@{FORCED_SERVER}:{port}?{param_str}#{url_encode_remark(remark)}")

        # ---------------- Trojan ----------------
        elif vpn_type == "trojan" and len(trojan_links) < target_per_type:
            password = info.get("password") or "pass123"
            port = info.get("port") or "443"
            path = ensure_slash(info.get("path", ""))
            tls = info.get("tls", "")
            sni = info.get("sni", "")
            mode = info.get("mode", "")
            org = info.get("org", "")
            country = info.get("country", "")
            id_field = info.get("id", "")
            params = ["type=ws"]
            if path: params.append(f"path={urllib.parse.quote(path)}")
            if tls in ("1","true","yes"): params.append("security=tls")
            if sni: params.append(f"sni={sni}")
            if mode: params.append(f"mode={mode}")
            param_str = "&".join(params)
            remark = f"{id_field} {country} {org} WS {mode} TLS"
            trojan_links.append(f"trojan://{password}@{FORCED_SERVER}:{port}?{param_str}#{url_encode_remark(remark)}")

        # stop early if all collected
        if len(vmess_links) >= target_per_type and len(vless_links) >= target_per_type and len(trojan_links) >= target_per_type:
            break

    all_links = vmess_links + vless_links + trojan_links

    # save & print
    pathlib.Path("results").mkdir(exist_ok=True)
    pathlib.Path("results/last_links.txt").write_text("\n".join(all_links))
    pathlib.Path("results/last_links.json").write_text(json.dumps(all_links, indent=2, ensure_ascii=False))

    print("Collected links:")
    for i, l in enumerate(all_links, 1):
        print(f"{i}. {l}")

    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
