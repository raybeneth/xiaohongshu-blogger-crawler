FROM python:3.12-slim

WORKDIR /app

# 安装依赖（利用层缓存，先复制依赖声明文件）
COPY pyproject.toml ./
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir .

# 复制源码
COPY src/ ./src/
COPY .env.example ./.env.example

# 数据目录
RUN mkdir -p data

# 非 root 用户运行
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

CMD ["xhs-crawler", "serve", "--host", "0.0.0.0", "--port", "8000"]
