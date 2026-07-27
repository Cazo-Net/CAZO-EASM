import asyncio
import httpx
import re

async def test():
    target = "digitalocean.com"
    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
        # Test crt.sh with longer timeout
        try:
            r = await client.get(f"https://crt.sh/?q=%25.{target}&output=json")
            data = r.json()
            names = set()
            for entry in data:
                for name in entry.get("name_value", "").split("\n"):
                    names.add(name.strip())
            print(f"crt.sh: {len(names)} subdomains")
            for n in sorted(names)[:15]:
                print(f"  {n}")
        except Exception as e:
            print(f"crt.sh: ERROR - {type(e).__name__}: {e}")

        # Test rapiddns - parse HTML
        try:
            r = await client.get(f"https://rapiddns.io/subdomain/{target}?full=1")
            subs = re.findall(r"<td>([a-zA-Z0-9._-]+\." + re.escape(target) + r")</td>", r.text)
            print(f"rapiddns: {len(subs)} subdomains")
            for s in subs[:10]:
                print(f"  {s}")
        except Exception as e:
            print(f"rapiddns: ERROR - {type(e).__name__}: {e}")

        # Test hackertarget
        try:
            r = await client.get(f"https://api.hackertarget.com/hostsearch/?q={target}")
            lines = [l for l in r.text.strip().split("\n") if l and "," in l]
            print(f"hackertarget: {len(lines)} subdomains")
            for l in lines[:5]:
                print(f"  {l}")
            if not lines:
                print(f"  response: {r.text[:200]}")
        except Exception as e:
            print(f"hackertarget: ERROR - {type(e).__name__}: {e}")

        # Test urlscan
        try:
            r = await client.get(f"https://urlscan.io/api/v1/search/?q=domain:{target}")
            data = r.json()
            print(f"urlscan: {data.get('total', 0)} results")
            for page in data.get("results", [])[:5]:
                print(f"  {page.get('page', {}).get('domain', 'unknown')}")
        except Exception as e:
            print(f"urlscan: ERROR - {type(e).__name__}: {e}")

asyncio.run(test())
