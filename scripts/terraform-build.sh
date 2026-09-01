#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
gradle_version="8.14.3"
tools_dir="$project_dir/.tools"
gradle_home="$tools_dir/gradle-$gradle_version"

case "$(uname -s)" in
  Darwin) adoptium_os="mac" ;;
  Linux)  adoptium_os="linux" ;;
  *) echo "Unsupported operating system: $(uname -s)" >&2; exit 1 ;;
esac

case "$(uname -m)" in
  arm64|aarch64) adoptium_arch="aarch64" ;;
  x86_64|amd64)  adoptium_arch="x64" ;;
  *) echo "Unsupported CPU architecture: $(uname -m)" >&2; exit 1 ;;
esac

jdk_home="$tools_dir/jdk-21-$adoptium_os-$adoptium_arch"

if [[ ! -x "$jdk_home/bin/javac" ]]; then
  mkdir -p "$tools_dir" "$jdk_home"
  jdk_archive="$tools_dir/jdk-21.tar.gz"
  curl --fail --location --silent --show-error \
    "https://api.adoptium.net/v3/binary/latest/21/ga/$adoptium_os/$adoptium_arch/jdk/hotspot/normal/eclipse" \
    --output "$jdk_archive"
  tar -xzf "$jdk_archive" --strip-components=1 -C "$jdk_home"
fi

if [[ ! -x "$gradle_home/bin/gradle" ]]; then
  mkdir -p "$tools_dir"
  archive="$tools_dir/gradle-$gradle_version-bin.zip"
  curl --fail --location --silent --show-error "https://services.gradle.org/distributions/gradle-$gradle_version-bin.zip" --output "$archive"
  unzip -q -o "$archive" -d "$tools_dir"
fi

if ! JAVA_HOME="$jdk_home" "$gradle_home/bin/gradle" -p "$project_dir" clean test lambdaZip --no-daemon --console=plain >&2; then
  if [[ -d "$project_dir/build/test-results" ]]; then
    find "$project_dir/build/test-results" -name '*.xml' -type f -exec sh -c 'echo "--- $1" >&2; cat "$1" >&2' _ {} \;
  fi
  exit 1
fi
artifact="$project_dir/build/distributions/strava-calendar-sync.zip"
hash="$(openssl dgst -sha256 -binary "$artifact" | openssl base64 -A)"
printf '{"artifact_path":"%s","source_code_hash":"%s"}\n' "$artifact" "$hash"
