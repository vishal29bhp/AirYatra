# AirYatra API and scheduler worker (one image; Container Apps picks the command).
#   api:    uvicorn server:app  (default CMD)
#   worker: python worker.py    (set by Terraform as the worker command)
# Build from the backend folder:  docker build -t airyatra-api backend

FROM python:3.11-slim AS deps
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /build
COPY requirements.txt .
# emergentintegrations is only on Emergent's private index and is not used on Azure
# (LLM_PROVIDER=azure_openai, STRIPE_PROVIDER=stripe, STORAGE_PROVIDER=azure_blob).
RUN grep -v '^emergentintegrations' requirements.txt > requirements.image.txt \
 && pip install --prefix=/install --only-binary=:all: -r requirements.image.txt

FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    WEB_CONCURRENCY=2 \
    UPLOAD_ROOT=/tmp/airyatra
RUN groupadd --system --gid 10001 airyatra \
 && useradd --system --uid 10001 --gid airyatra --no-create-home --shell /usr/sbin/nologin airyatra
COPY --from=deps /install /usr/local
WORKDIR /app/backend
# Code is owned by root and read-only for the app user.
COPY --chown=root:root . .
USER 10001:10001
EXPOSE 8001
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8001/health', timeout=4).status == 200 else 1)"
# uvicorn reads the worker count from WEB_CONCURRENCY. No --proxy-headers: the client IP comes
# only from Front Door headers verified in front_door.py.
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8001"]
