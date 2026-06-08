FROM python:3.12-slim

WORKDIR /app

# 系统依赖（pandas/numpy 编译需要 gcc）
RUN apt-get update && apt-get install -y --no-install-recommends gcc \
    && rm -rf /var/lib/apt/lists/*

# 先装依赖（利用 Docker 层缓存，requirements 不变时跳过此步）
COPY requirements-prod.txt .
RUN pip install --no-cache-dir -r requirements-prod.txt

# 仅复制生产代码，排除测试/文档/视频/数据文件
COPY app.py config.py ./
COPY data/ data/
COPY ai/ ai/
COPY skills/ skills/
COPY routes/ routes/
COPY templates/ templates/
COPY static/css/ static/css/
COPY static/js/ static/js/
COPY static/favicon.png static/

RUN mkdir -p datasets

EXPOSE 5000

ENV PYTHONUNBUFFERED=1
ENV FLASK_DEBUG=false

CMD ["gunicorn", "-w", "2", "-b", "0.0.0.0:5000", "--timeout", "120", "app:create_app()"]
