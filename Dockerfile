# Imagem única do projeto (Marco 12, etapa B6): painel, API e rotina semanal usam o mesmo ambiente
# do requirements.txt. Os serviços estão no docker-compose.yml; os dados ficam fora da imagem.
FROM python:3.14-slim-bookworm

# O LightGBM precisa da biblioteca OpenMP, que a imagem slim não traz.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --root-user-action=ignore -r requirements.txt
COPY . .

ENV PYTHONUTF8=1 PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
RUN useradd --create-home radar && mkdir -p data/raw data/processed data/quarantine && chown -R radar /app
USER radar
