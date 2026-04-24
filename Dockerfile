FROM nascent-registry.cn-zhangjiakou.cr.aliyuncs.com/ecrp/python:3.12.2

WORKDIR /app

# 安装依赖
COPY pyproject.toml ./
COPY src/ ./src/
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir .

COPY .env.example ./.env.example

# 数据目录
RUN mkdir -p data

# 非 root 用户运行
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

ENV DASHBOARD_HOST=0.0.0.0
ENV DASHBOARD_PORT=8000

EXPOSE ${DASHBOARD_PORT}

CMD ["sh", "-c", "xhs-crawler dashboard --host ${DASHBOARD_HOST} --port ${DASHBOARD_PORT}"]
