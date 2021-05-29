FROM gcc:11

LABEL description="Native G++-11 on Raspberry Pi 3B"

RUN apt update && apt install -y cmake && apt clean && rm -rf /var/lib/apt/lists/*

ADD https://github.com/google/benchmark/archive/refs/tags/v1.5.3.tar.gz /google-benchmark-src.tar.gz

RUN cd $(mktemp -d) && \
    tar -xzf /google-benchmark-src.tar.gz --strip-components=1 && \
    rm /google-benchmark-src.tar.gz && \
    mkdir build && \
    cd build && \
    cmake -DCMAKE_BUILD_TYPE=Release -DCMAKE_CXX_STANDARD=20 -DBENCHMARK_ENABLE_TESTING=OFF -DBENCHMARK_ENABLE_GTEST_TESTS=OFF .. && \
    cmake --build . --target install -- -j2 && \
    cd / && \
    rm -rf /tmp/*

COPY run.sh .

CMD ./run.sh
