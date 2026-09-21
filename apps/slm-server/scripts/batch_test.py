import asyncio
from policy_fetcher import fetch_policy

URLS = [
    ("Google", "https://policies.google.com/privacy"),
    ("Google Redirect", "https://www.google.com/policies/privacy/"),
    ("Apple", "https://www.apple.com/legal/privacy/en-ww/"),
    ("Wikimedia", "https://foundation.wikimedia.org/wiki/Special:MyLanguage/Policy:Privacy_policy"),
    ("GitHub", "https://docs.github.com/en/site-policy/privacy-policies/github-general-privacy-statement"),
    ("Vercel", "https://vercel.com/legal/privacy-policy"),
    ("Stripe", "https://stripe.com/privacy"),
    ("Cloudflare", "https://www.cloudflare.com/privacypolicy/"),
    ("Spotify", "https://www.spotify.com/us/legal/privacy-policy/"),
    ("OpenAI", "https://openai.com/policies/privacy-policy/"),
    ("Substack", "https://substack.com/privacy"),
    ("Reddit", "https://www.reddit.com/policies/privacy-policy"),
]

async def main():
    print(f"{'SITE':<16} | {'OK':<5} | {'CHARS':<7} | {'TIME(ms)':<8} | {'NOTES'}")
    print("-" * 65)
    for name, url in URLS:
        try:
            res = await fetch_policy(url, force=True)
            note = res.error if not res.ok else f"Sample: {res.text[:40].strip()}..."
            print(f"{name:<16} | {str(res.ok):<5} | {res.char_count:<7} | {res.fetch_ms:<8} | {note}")
        except Exception as e:
            print(f"{name:<16} | ERROR | 0       | 0        | Exception: {e}")

if __name__ == "__main__":
    asyncio.run(main())
