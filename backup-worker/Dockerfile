FROM postgres:18.6
RUN apt-get update && apt-get install -y --no-install-recommends python3 ca-certificates \
    && rm -rf /var/lib/apt/lists/*
COPY worker.py /opt/traffic-backup/worker.py
ENTRYPOINT ["python3", "/opt/traffic-backup/worker.py"]
