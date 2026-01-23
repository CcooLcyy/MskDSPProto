file(GLOB PROTO_FILE_SRCS *.proto)

add_library(dspProto SHARED ${PROTO_FILE_SRCS})
set_target_properties(dspProto PROPERTIES
  POSITION_INDEPENDENT_CODE ON
  LIBRARY_OUTPUT_DIRECTORY ${libPath}
)
target_link_libraries(dspProto PUBLIC
  gRPC::grpc++
  protobuf::libprotobuf
)
target_link_options(dspProto INTERFACE
  $<$<PLATFORM_ID:Linux>:-Wl,--no-as-needed>
)

protobuf_generate(TARGET dspProto)

set(MSKDSP_GRPC_CPP_PLUGIN $<TARGET_FILE:gRPC::grpc_cpp_plugin>)
set(_mskdsp_host_triplet "")
if(DEFINED VCPKG_HOST_TRIPLET AND NOT VCPKG_HOST_TRIPLET STREQUAL "")
  set(_mskdsp_host_triplet "${VCPKG_HOST_TRIPLET}")
elseif(CMAKE_CROSSCOMPILING)
  if(CMAKE_HOST_SYSTEM_NAME STREQUAL "Linux")
    if(CMAKE_HOST_SYSTEM_PROCESSOR MATCHES "^(x86_64|amd64)$")
      set(_mskdsp_host_triplet "x64-linux")
    elseif(CMAKE_HOST_SYSTEM_PROCESSOR MATCHES "^(aarch64|arm64)$")
      set(_mskdsp_host_triplet "arm64-linux")
    elseif(CMAKE_HOST_SYSTEM_PROCESSOR MATCHES "^armv7")
      set(_mskdsp_host_triplet "arm-linux")
    else()
      message(FATAL_ERROR "Unsupported host processor for vcpkg host triplet: ${CMAKE_HOST_SYSTEM_PROCESSOR}")
    endif()
  else()
    message(FATAL_ERROR "Unsupported host system for vcpkg host triplet: ${CMAKE_HOST_SYSTEM_NAME}")
  endif()
endif()

if(DEFINED VCPKG_INSTALLED_DIR AND _mskdsp_host_triplet)
  set(MSKDSP_GRPC_CPP_PLUGIN
      "${VCPKG_INSTALLED_DIR}/${_mskdsp_host_triplet}/tools/grpc/grpc_cpp_plugin")
  if(NOT EXISTS "${MSKDSP_GRPC_CPP_PLUGIN}")
    message(FATAL_ERROR "grpc_cpp_plugin not found for host triplet: ${MSKDSP_GRPC_CPP_PLUGIN}")
  endif()
  message(STATUS "Using host grpc_cpp_plugin: ${MSKDSP_GRPC_CPP_PLUGIN}")
endif()

protobuf_generate(
  TARGET dspProto
  LANGUAGE grpc
  PLUGIN protoc-gen-grpc=${MSKDSP_GRPC_CPP_PLUGIN}
  PLUGIN_OPTIONS generate_mock_code=true
  GENERATE_EXTENSIONS .grpc.pb.h .grpc.pb.cc
)

target_include_directories(dspProto PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_BINARY_DIR}>
)
