FROM debian:trixie-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    libreoffice-writer libreoffice-java-common \
    default-jre-headless fonts-noto-cjk fonts-liberation python3 \
    && rm -rf /var/lib/apt/lists/*
RUN useradd --uid 10001 --create-home converter
ADD --checksum=sha256:cbea23bc37861361bbc534bc0675e5bc67b36f712072490f82a9bf410d7c04d8 https://github.com/ebandal/H2Orestart/releases/download/v0.7.14/H2Orestart.oxt /opt/H2Orestart.oxt
RUN unopkg add --shared --suppress-license /opt/H2Orestart.oxt
COPY convert.py /opt/convert.py
USER 10001:10001
ENTRYPOINT ["python3", "/opt/convert.py"]
