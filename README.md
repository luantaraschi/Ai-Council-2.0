> ## Sobre este repositório
>
> Este é um **fork de estudo** do [llm-council](https://github.com/karpathy/llm-council),
> de **Andrej Karpathy**. Todo o README a partir de "# LLM Council" é o texto original
> dele — inclusive os trechos em primeira pessoa, que são a voz do autor original e não a minha.
>
> **O que eu acrescentei sobre o original:**
>
> | Arquivo | O que faz |
> |---|---|
> | `docker-compose.yml`, `backend/Dockerfile`, `frontend/Dockerfile`, `frontend/nginx.conf` | Containerização completa da stack |
> | `backend/requirements.txt` | Dependências fixadas |
> | `backend/llm_client.py` | Camada de abstração sobre o cliente de LLM |
> | `backend/supabase_storage.py` | Persistência em Supabase no lugar do armazenamento local |
>
> O projeto original **não declara licença**, o que significa que todos os direitos
> permanecem com o autor. Por isso este repositório também não declara licença própria:
> ele existe como registro de estudo, não como software redistribuível.

---

# LLM Council

Local multi-LLM consensus application built as an architectural study fork of Andrej Karpathy's `llm-council`.

## What this repository adds to the original

- **Docker Containerization:** Full multi-container setup via `docker-compose.yml`, `backend/Dockerfile`, `frontend/Dockerfile`, and `frontend/nginx.conf`.
- **Pinned Dependencies:** Locked Python environment requirements (`backend/requirements.txt`).
- **LLM Client Abstraction:** Extensible model client layer (`backend/llm_client.py`).
- **Supabase Persistence:** Database storage adapter (`backend/supabase_storage.py`) replacing local storage.

## How it works

The application queries multiple LLMs in parallel via OpenRouter:

1. **Stage 1 (First Opinions):** Collects individual responses from participating LLMs.
2. **Stage 2 (Peer Review):** Anonymizes responses and prompts each model to evaluate and rank peer outputs.
3. **Stage 3 (Final Synthesis):** A designated Chairman model synthesizes the peer-reviewed responses into a final answer.

## Local setup

Requirements: Docker Desktop and an OpenRouter API Key.

1. Configure `.env` in the root directory:

```bash
OPENROUTER_API_KEY=sk-or-v1-...
```

2. Run with Docker Compose:

```bash
docker compose up -d
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

## State

Study repository focused on containerization and persistence layer refactoring. Live API integration requires an active OpenRouter API key with available credits.

## License

The original repository does not declare an open source license. Consequently, all rights remain with the original author, and this study repository does not declare a license.
