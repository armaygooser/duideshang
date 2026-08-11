import asyncio
import json
import os
from collections.abc import AsyncIterator
from contextlib import suppress

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from .models import AnalysisResult, AnalyzeRequest, ProviderChoice, ProviderStatus, QuoteInput, QuoteResult, RefineRequest, RefineResult
from .pricing import calculate_quote
from .providers import ProviderManager
from .demo_provider import analyze as demo_analyze

app = FastAPI(title="对得上 DuiDeShang API", version="0.1.0")
origins = [
    x.strip()
    for x in os.getenv(
        "CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
    ).split(",")
]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
provider_manager = ProviderManager()


@app.get("/health")
def health() -> dict:
    return {"status": "ok", **provider_manager.status().model_dump()}


@app.get("/api/provider", response_model=ProviderStatus)
def provider_status(provider: ProviderChoice | None = None) -> ProviderStatus:
    return provider_manager.status(provider)


@app.post("/api/analyze", response_model=AnalysisResult)
async def analyze_requirement(request: AnalyzeRequest) -> AnalysisResult:
    return await provider_manager.analyze(request.text, preferred=request.provider)


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@app.post("/api/analyze/stream")
async def analyze_requirement_stream(request: AnalyzeRequest) -> StreamingResponse:
    async def stream() -> AsyncIterator[str]:
        queue: asyncio.Queue[dict[str, str]] = asyncio.Queue()

        async def report(event: dict[str, str]) -> None:
            await queue.put(event)

        preliminary = demo_analyze(request.text)
        yield _sse("started", {"stage": "reading", "label": "已读取客户原话"})
        yield _sse("preliminary", {"stage": "preliminary", "label": "本地初步扫描完成", "summary": {
            "explicit_count": len(preliminary.explicit_requirements),
            "ambiguity_count": len(preliminary.ambiguities),
            "missing_count": len(preliminary.missing_requirements),
        }})
        task = asyncio.create_task(provider_manager.analyze(request.text, report, request.provider))
        try:
            while not task.done() or not queue.empty():
                if not queue.empty():
                    yield _sse("progress", queue.get_nowait())
                    continue
                next_event = asyncio.create_task(queue.get())
                done, _ = await asyncio.wait({task, next_event}, return_when=asyncio.FIRST_COMPLETED)
                if next_event in done:
                    yield _sse("progress", next_event.result())
                else:
                    next_event.cancel()
                    with suppress(asyncio.CancelledError):
                        await next_event
            result = await task
            yield _sse("completed", {"stage": "completed", "label": "需求分析完成"})
            yield _sse("result", result.model_dump(mode="json"))
        except asyncio.CancelledError:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
            raise
        except Exception:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
            yield _sse("error", {"message": "需求分析暂时无法完成"})

    return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.post("/api/refine", response_model=RefineResult)
async def refine_requirement(request: RefineRequest) -> RefineResult:
    return await provider_manager.refine(request)


@app.post("/api/quote", response_model=QuoteResult)
def create_quote(request: QuoteInput) -> QuoteResult:
    return calculate_quote(request)
