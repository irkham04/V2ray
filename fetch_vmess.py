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
FORCED_SERVER = "104.18.1.196"  # paksa semua server

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

    target_per_type = 5
    vmess_links, vless_links, trojan_links = [], [], []

    async for m in client.iter_messages(channel, limit=None, reverse=False):
        if not (m.message and KEYWORD.lower() in m.message.lower()):
            continue

        info = {}
        for line in m.message.splitlines():
            line = line.strip()
            if ':' in line:
                key, val = line.split(':', 1)
                info[key.strip().lower()] = val.strip()

        vpn_type = info.get("vpn", "").lower()
        id_field = info.get("id", "")
        country = info.get("country", "")
        org = info.get("org", "")
        mode = info.get("mode", "")

        # ---------------- VMESS ----------------
        if vpn_type == "vmess" and len(vmess_links) < target_per_type:
            id_uuid = info.get("uuid") or str(uuid.uuid4())
            port = str(info.get("port") or "443")
            aid_val = str(info.get("aid") or "0")
            tls_flag = info.get("tls", "").strip()
            tls_field = "tls" if tls_flag in ("1", "true", "yes") else ""
            host_hdr = info.get("host") or info.get("sni") or FORCED_SERVER
            path = ensure_slash(info.get("path", ""))
            ps_remark = f"{id_field} {country} {org} WS {mode} TLS".strip()
            ps_val = ps_remark if ps_remark.strip() else f"vmess-{id_uuid[:6]}"
            vmess_obj = {
                "v": "2",
                "ps": ps_val,
                "add": FORCED_SERVER,
                "port": port,
                "id": id_uuid,
                "aid": aid_val,
                "net": "ws",
                "type": "none",
                "host": host_hdr,
                "path": path,
                "tls": tls_field
            }
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
            if tls in ("1", "true", "yes"): params.append("security=tls")
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
            if tls in ("1", "true", "yes"): params.append("security=tls")
            if sni: params.append(f"sni={sni}")
            if mode: params.append(f"mode={mode}")
            param_str = "&".join(params)
            remark = f"{id_field} {country} {org} WS {mode} TLS"
            trojan_links.append(f"trojan://{password}@{FORCED_SERVER}:{port}?{param_str}#{url_encode_remark(remark)}")

        if len(vmess_links) >= target_per_type and len(vless_links) >= target_per_type and len(trojan_links) >= target_per_type:
            break

    all_links = vmess_links + vless_links + trojan_links

    pathlib.Path("results").mkdir(exist_ok=True)
    pathlib.Path("results/last_links.txt").write_text("\n".join(all_links))
    pathlib.Path("results/last_links.json").write_text(json.dumps(all_links, indent=2, ensure_ascii=False))

    print("Collected links:")
    for i, l in enumerate(all_links, 1):
        print(f"{i}. {l}")

    # ===================================================================
    #                     === CLASH OUTPUT START ===
    # ===================================================================
    clash_nodes = []

    # VMESS
    for l in vmess_links:
        data = json.loads(base64.b64decode(l.replace("vmess://", "")).decode())
        clash_nodes.append({
            "name": data["ps"],
            "type": "vmess",
            "server": data["add"],
            "port": int(data["port"]),
            "uuid": data["id"],
            "alterId": int(data.get("aid", 0)),
            "cipher": "auto",
            "network": "ws",
            "ws-opts": {
                "path": data.get("path", "/"),
                "headers": {"Host": data.get("host", "")}
            },
            "tls": (data.get("tls") == "tls")
        })

    # VLESS
    for l in vless_links:
        raw = l.replace("vless://", "")
        node, params = raw.split("@")[0], raw.split("@")[1]
        uuid_val = node
        server = params.split(":")[0]
        port = params.split(":")[1].split("?")[0]
        query = params.split("?")[1].split("#")[0]
        remark = urllib.parse.unquote(params.split("#")[-1])
        q = dict(p.split("=", 1) for p in query.split("&") if "=" in p)

        clash_nodes.append({
            "name": remark,
            "type": "vless",
            "server": server,
            "port": int(port),
            "uuid": uuid_val,
            "network": "ws",
            "tls": ("security" in q and q["security"] == "tls"),
            "ws-opts": {
                "path": q.get("path", "/"),
                "headers": {"Host": q.get("host", "")}
            },
            "client-fingerprint": "chrome"
        })

    # TROJAN
    for l in trojan_links:
        raw = l.replace("trojan://", "")
        password = raw.split("@")[0]
        server = raw.split("@")[1].split(":")[0]
        port = raw.split(":")[2].split("?")[0]
        query = raw.split("?")[1].split("#")[0]
        remark = urllib.parse.unquote(raw.split("#")[-1])
        q = dict(p.split("=", 1) for p in query.split("&") if "=" in p)

        clash_nodes.append({
            "name": remark,
            "type": "trojan",
            "server": server,
            "port": int(port),
            "password": password,
            "network": "ws",
            "tls": ("security" in q and q["security"] == "tls"),
            "ws-opts": {
                "path": q.get("path", "/"),
                "headers": {"Host": q.get("sni", "")}
            }
        })

    clash_yaml = {
        "port": 7890,
        "socks-port": 7891,
        "redir-port": 7892,
        "allow-lan": True,
        "mode": "rule",
        "log-level": "info",
        "proxies": clash_nodes,
        "proxy-groups": [
            {
                "name": "AUTO",
                "type": "url-test",
                "proxies": [n["name"] for n in clash_nodes],
                "url": "http://www.gstatic.com/generate_204",
                "interval": 300
            },
            {
                "name": "SELECT",
                "type": "select",
                "proxies": [n["name"] for n in clash_nodes]
            }
        ],
        "rules": [
            "MATCH,SELECT"
        ]
    }

    pathlib.Path("results/clash.yaml").write_text(
        json.dumps(clash_yaml, indent=2, ensure_ascii=False)
    )

    print("Generated: results/clash.yaml")

    # ===================================================================
    #                     === CLASH OUTPUT END ===
    # ===================================================================

    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
