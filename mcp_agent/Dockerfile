FROM python:3.13-slim
WORKDIR /service

COPY requirements.txt /service/requirements.txt
RUN pip install --no-cache-dir -r /service/requirements.txt

RUN mkdir -p /service/mcp_agent && \
    adduser --disabled-password --gecos "" myuser
 
COPY . /service/mcp_agent/

RUN chown -R myuser:myuser /service

USER myuser
ENV PYTHONPATH="/service"
ENV PORT=8000
EXPOSE 8000
ENV PATH="/home/myuser/.local/bin:$PATH"
ENV MCP_SERVER_URL http://localhost:9000
CMD ["uvicorn", "mcp_agent.main:app", "--host", "0.0.0.0", "--port", "8000"]