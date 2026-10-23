import os

from dotenv import load_dotenv
from langchain_core.rate_limiters import InMemoryRateLimiter
from langchain_groq import ChatGroq

load_dotenv()

# हर Groq कॉल इसी एक limiter से गुज़रती है: 1/सेकंड = हर सेकंड में एक कॉल।
# Groq का free tier बहुत ज़्यादा rate देता है, फिर भी limiter + retry 429 से बचाते हैं।
_limiter = InMemoryRateLimiter(
    requests_per_second=float(os.getenv("LLM_RPS", "1.0")),
    check_every_n_seconds=0.1,
    max_bucket_size=1,
)


def get_llm(temperature: float = 0.3):
    return ChatGroq(
        model=os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b"),
        groq_api_key=os.getenv("GROQ_API_KEY"),
        temperature=temperature,
        rate_limiter=_limiter,
    ).with_retry(
        retry_if_exception_type=(Exception,),
        wait_exponential_jitter=True,
        stop_after_attempt=6,
    )