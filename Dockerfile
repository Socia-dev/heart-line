# Heart Line in one container: builds the web app, generates the synthetic population,
# trains the model, and serves the API and the web app from one port.
FROM node:22-slim AS web
WORKDIR /app/web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

FROM python:3.13-slim
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY backend/ backend/
COPY --from=web /app/web/dist web/dist
WORKDIR /app/backend
# Synthetic data and the model are built into the image, so it starts ready.
RUN python -m heartline.generate && python -m heartline.train
ENV HEARTLINE_ORIGINS=*
EXPOSE 8010
CMD ["python", "-m", "uvicorn", "heartline.api:app", "--host", "0.0.0.0", "--port", "8010"]
