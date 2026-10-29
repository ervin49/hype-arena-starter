# The batch run: reads /universe/universe.csv and lexicon.json, writes /output/output.csv.
# Offline, as user 10001, on a read-only root (contracts/README.md). Check it with scripts/check.sh.
FROM python:3.12.10-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOME=/tmp \
    XDG_CACHE_HOME=/tmp/.cache

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# What the run reads: the code and its models, the schemas, the practice data, the claim backtest.
COPY arena/ arena/
COPY contracts/claimed_value.schema.json contracts/entry.schema.json contracts/
COPY data/ data/
COPY reports/claims_calibration.json reports/
RUN python -m compileall -q arena

USER 10001
CMD ["python", "-m", "arena.runner"]
