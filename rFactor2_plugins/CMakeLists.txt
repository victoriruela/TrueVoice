cmake_minimum_required(VERSION 3.20)
project(TrueVoicePlugin VERSION 1.0.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# ── Sources ────────────────────────────────────────────────────────

set(SOURCES
    src/TrueVoicePlugin.cpp
    src/EventDetector.cpp
    src/JsonWriter.cpp
)

set(HEADERS
    src/TrueVoicePlugin.h
    src/EventDetector.h
    src/JsonWriter.h
    include/InternalsPlugin.hpp
    include/PluginObjects.hpp
)

# ── Shared library (DLL) ──────────────────────────────────────────

add_library(TrueVoicePlugin SHARED ${SOURCES} ${HEADERS})

target_include_directories(TrueVoicePlugin PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/include
    ${CMAKE_CURRENT_SOURCE_DIR}/src
)

# rF2 requires 4-byte struct packing on MSVC
# Use static CRT (/MT) to avoid conflicts with rFactor2's MSVCR120 runtime
if(MSVC)
    target_compile_options(TrueVoicePlugin PRIVATE /W3)
    set_property(TARGET TrueVoicePlugin PROPERTY
        MSVC_RUNTIME_LIBRARY "MultiThreaded$<$<CONFIG:Debug>:Debug>")
endif()

# ── Output naming ─────────────────────────────────────────────────

set_target_properties(TrueVoicePlugin PROPERTIES
    OUTPUT_NAME "TrueVoicePlugin"
    PREFIX ""
    SUFFIX ".dll"
)

# ── Install ───────────────────────────────────────────────────────

install(TARGETS TrueVoicePlugin
    RUNTIME DESTINATION bin
    LIBRARY DESTINATION lib
)
