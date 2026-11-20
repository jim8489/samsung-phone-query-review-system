# Ollama-backed RAG and LangChain multi-agent setup

This patch keeps the existing BM25 + SQL database retrieval pipeline. Ollama supplies the open-weight local language model used to formulate answers from the retrieved phone evidence. LangChain `create_agent` coordinates two specialist agents for the product-review endpoint.

## 1. Install and start Ollama on macOS

Install the Ollama macOS application from the official website: https://ollama.com/download/mac

Open the Ollama application, then in Terminal run:

```bash
ollama pull qwen2.5:3b
ollama list
```

The configured default is `qwen2.5:3b` (about 1.9 GB in the Ollama library). It is a compact model and is listed by Ollama among tool-capable models, which is important for the LangChain agents. The first download can take time depending on your connection.

## 2. Update the existing `.env`

Do not replace your `.env`. Add or update only these values:

```env
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:3b
AGENT_FRAMEWORK=langchain
```

`LLM_PROVIDER=auto` also attempts Ollama and falls back when it is unavailable; use `ollama` for a clear demonstration configuration. `LLM_PROVIDER=none` disables model generation.

Restart the existing Uvicorn process after changing `.env`; Pydantic settings are loaded when the process starts.

## 3. Check Ollama from the application

Open:

- `http://127.0.0.1:8000/api/llm`
- `http://127.0.0.1:8000/api/agents`

The LLM status should report `reachable: true` and `model_available: true`. The agents status should report framework `langchain` and `framework_dependencies_installed: true`.

## 4. Verify a real RAG response

From the project root, using the existing venv:

```bash
python scripts/verify_ollama_rag.py --query "What are the rear camera specifications of the Samsung Galaxy S23?"
```

A successful check must print `Generation mode: ollama_rag`, retrieved source URLs, the model's answer, and `[PASS]`. If it says `rag_fallback`, Ollama was not actually used; do not describe that run as an LLM demonstration.

Try these assessment queries from the UI or `POST /api/chat`:

- What are the camera specifications of the Samsung Galaxy S23?
- Which Samsung phone has the best battery life?
- How does the Galaxy S23 compare to the Galaxy S22 in terms of performance?
- What price observations are recorded for the Galaxy S23?

The chatbot uses BM25 to retrieve relevant SQL catalogue evidence before calling Ollama. It cites source labels and explains when no measured battery or price evidence exists.

## 5. Verify the framework-based multi-agent review

Call this from the project root after the service is running:

```bash
curl -sS -X POST http://127.0.0.1:8000/api/reviews/samsung-galaxy-s23 \
  -H 'Content-Type: application/json' \
  -d '{"include_limitations": true}'
```

When the LangChain and Ollama path succeeds, the response field `generation_mode` must be `langchain_multi_agent`. The Specification Retrieval Agent calls the existing BM25/SQL retrieval service and hands its evidence to the Product Review Agent. The second agent retrieves the complete phone record and produces a balanced review. If the framework/model is unavailable, the API remains available and falls back; the response mode makes that distinction explicit.

The project uses LangChain's `create_agent` API with `langchain-ollama` (`ChatOllama`). The dependency files are separate so you can add these packages to the existing venv without replacing the original project installation.
