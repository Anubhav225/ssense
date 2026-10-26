import asyncio
import hmac
import hashlib
import time
import json
import httpx

API_URL = "http://localhost:8000/v1/chat/stream"
SECRET_KEY = b"enEabpIITGIbuqoeWbgJoCA2GsbSUsmHsCJDG4Eka-3k8yMaIkjmL1aZK3AXlSBZ"

QUESTIONS = [
    {
        "domain": "zomato.com",
        "url": "https://www.zomato.com/policies/privacy/",
        "question": "Does Zomato share my data with third parties for marketing?",
        "expected_concept": "third-party sharing"
    },
    {
        "domain": "paytm.com",
        "url": "https://paytm.com/privacy-policy",
        "question": "How long does Paytm retain my transaction data after account deletion?",
        "expected_concept": "data retention"
    },
    {
        "domain": "redbus.in",
        "url": "https://www.redbus.in/info/privacypolicy",
        "question": "What happens if I refuse consent to cookies?",
        "expected_concept": "cookie consent"
    },
    {
        "domain": "swiggy.com",
        "url": "https://www.swiggy.com/privacy-policy",
        "question": "Are my payment details stored locally or tokenized?",
        "expected_concept": "payment security"
    }
]

async def eval_chat(client, item, idx):
    payload = {
        "domain": item["domain"],
        "userPrompt": item["question"]
    }
    
    timestamp = str(int(time.time() * 1000))
    nonce = f"chat-eval-{idx}-{timestamp}"
    
    msg = f"POST:/v1/chat/stream:{timestamp}:{nonce}".encode('utf-8')
    signature = hmac.new(SECRET_KEY, msg, hashlib.sha256).hexdigest()
    
    headers = {
        "Content-Type": "application/json",
        "X-Ssense-API-Key": "CYnzcaH4_CISSO_RlsH_K2s83xLEGAIMzKysD30UY2w",
        "X-Ssense-Signature": signature,
        "X-Ssense-Timestamp": timestamp,
        "X-Ssense-Nonce": nonce
    }
    
    start = time.time()
    try:
        response = await client.post(API_URL, json=payload, headers=headers, timeout=300.0)
        latency = time.time() - start
        if response.status_code == 200:
            full_text = ""
            for line in response.text.splitlines():
                if line.startswith("data: "):
                    try:
                        chunk = json.loads(line[6:])
                        if "t" in chunk:
                            full_text += chunk["t"]
                    except:
                        pass
            return {
                "domain": item["domain"], 
                "latency": latency, 
                "response": full_text.strip(),
                "status": "success"
            }
        else:
            return {"domain": item["domain"], "latency": latency, "status": f"error: {response.status_code} {response.text}"}
    except Exception as e:
        return {"domain": item["domain"], "latency": time.time() - start, "status": f"failed: {str(e)}"}

async def main():
    print("🚀 Starting Chatbot RAG Evaluation against SLM Server...")
    start_time = time.time()
    
    results = []
    async with httpx.AsyncClient() as client:
        for idx, item in enumerate(QUESTIONS):
            print(f"[{idx+1}/{len(QUESTIONS)}] Asking {item['domain']}: '{item['question']}'")
            res = await eval_chat(client, item, idx)
            results.append(res)
    
    print("-" * 100)
    print(f"{'Domain':<15} | {'Latency (s)':<12} | {'Response Snippet':<50} | {'Status'}")
    print("-" * 100)
    
    for r in results:
        resp_snippet = r.get('response', '')[:47] + '...' if len(r.get('response', '')) > 50 else r.get('response', '')
        # Escape newlines
        resp_snippet = resp_snippet.replace('\n', ' ')
        print(f"{r['domain']:<15} | {r['latency']:<12.2f} | {resp_snippet:<50} | {r['status']}")

if __name__ == "__main__":
    asyncio.run(main())
