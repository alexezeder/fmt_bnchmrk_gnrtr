#!/bin/bash -ex

# 1. gathering library stat

# 1.1. build format.o several times to get average compilation time
cd "$(mktemp -d)"
cmake -DCMAKE_BUILD_TYPE=Release -DCMAKE_CXX_STANDARD=20 -DFMT_DOC=OFF -DFMT_TEST=OFF /fmt
cmake --build . --target src/format.o
for i in {1..4}; do
    cmake --build . --target clean
    sleep 0.5
    { time cmake --build . --target src/format.o ; } 2> "/output/compilation_time_$i.txt"
done

# 1.3. build libfmt.so to get shared library size
cd "$(mktemp -d)"
cmake -DCMAKE_BUILD_TYPE=Release -DCMAKE_CXX_STANDARD=20 -DFMT_DOC=OFF -DFMT_TEST=OFF -DBUILD_SHARED_LIBS=ON /fmt
cmake --build . --target fmt -- -j2
stat --printf="%s" -L ./libfmt.so > /output/shared_library_size.txt

# 1.2. build libfmt.a to get static library size
cd "$(mktemp -d)"
cmake -DCMAKE_BUILD_TYPE=Release -DCMAKE_CXX_STANDARD=20 -DFMT_DOC=OFF -DFMT_TEST=OFF -DBUILD_SHARED_LIBS=OFF /fmt
cmake --build . --target fmt -- -j2
stat --printf="%s" -L ./libfmt.a > /output/static_library_size.txt
# 🠗🠗🠗 we will use libfmt.a in the next step 🠗🠗🠗


# 2. run benchmark suites

# 2.1. but first we need to build and install {fmt} library
# 🠕🠕🠕 we are using libfmt.a from the previous step 🠕🠕🠕
cmake --build . --target install -- -j2

# 2.2. then we can build and test benchmark suites
cd "$(mktemp -d)"
cmake -G "Unix Makefiles" -DCMAKE_BUILD_TYPE=Release -DCMAKE_CXX_STANDARD=20 /benchmarks
make all -k -j2 || true  # keep on errors so we can get at least some results
for suite_executable in output/*; do
    for i in {1..2}; do
        $suite_executable --benchmark_out="/output/$(basename -- "$suite_executable")_results_$i.json" --benchmark_out_format=json
    done
done
