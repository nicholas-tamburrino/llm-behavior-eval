"""Ways to get a reply. An adapter is any callable: adapter(history, user, seed) -> reply text.

`history` is a list of {"role": "user"|"assistant", "content": str} for earlier turns of the same case.
No third-party packages are needed; network adapters use the standard library.
"""
import json
import os
import urllib.request


class FixtureAdapter:
    """Replays saved replies from a JSONL file. Used for tests, demos, and re-checking old runs.

    Each line: {"id": "<case id>", "replies": ["...", "..."]}  (one reply per user turn).
    """

    def __init__(self, path):
        self.by_id = {}
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    row = json.loads(line)
                    self.by_id[row["id"]] = row["replies"]
        self.case_id = None
        self.turn = 0

    def start_case(self, case_id):
        if case_id not in self.by_id:
            raise KeyError(f"no fixture replies for case {case_id!r}")
        self.case_id, self.turn = case_id, 0

    def __call__(self, history, user, seed):
        replies = self.by_id[self.case_id]
        if self.turn >= len(replies):
            raise IndexError(f"fixture for {self.case_id!r} has fewer replies than the case has turns")
        reply = replies[self.turn]
        self.turn += 1
        return reply


def _post_json(url, payload, headers=None, timeout=180):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json", **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


class OllamaAdapter:
    """A local model served by Ollama (default http://localhost:11434)."""

    def __init__(self, model, system="", host=None, temperature=0.7):
        self.model, self.system, self.temperature = model, system, temperature
        self.host = (host or os.environ.get("OLLAMA_HOST") or "http://localhost:11434").rstrip("/")
        if not self.host.startswith("http"):
            self.host = "http://" + self.host

    def __call__(self, history, user, seed):
        msgs = ([{"role": "system", "content": self.system}] if self.system else []) + history + \
               [{"role": "user", "content": user}]
        body = _post_json(f"{self.host}/api/chat", {
            "model": self.model, "messages": msgs, "stream": False,
            "options": {"seed": seed, "temperature": self.temperature},
        })
        return body["message"]["content"].strip()


class OpenAICompatAdapter:
    """Any server with an OpenAI-style /chat/completions endpoint. The key is read from an env var."""

    def __init__(self, model, system="", base_url="https://api.openai.com/v1", api_key_env="OPENAI_API_KEY",
                 temperature=0.7):
        self.model, self.system, self.temperature = model, system, temperature
        self.base_url = base_url.rstrip("/")
        self.api_key = os.environ.get(api_key_env, "")
        if not self.api_key and "localhost" not in base_url and "127.0.0.1" not in base_url:
            raise RuntimeError(f"set the {api_key_env} environment variable")

    def __call__(self, history, user, seed):
        msgs = ([{"role": "system", "content": self.system}] if self.system else []) + history + \
               [{"role": "user", "content": user}]
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        body = _post_json(f"{self.base_url}/chat/completions", {
            "model": self.model, "messages": msgs, "temperature": self.temperature, "seed": seed,
        }, headers)
        return body["choices"][0]["message"]["content"].strip()
