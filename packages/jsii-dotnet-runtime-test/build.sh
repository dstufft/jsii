#!/bin/bash
set -euo pipefail

# TODO: Auto-rev NuGet package versions on each local build.
# Because we we don't rev the versions, dotnet will pick
# up an old build from the cache if it exists. So we
# explicitly clear the cache as a temporary workaround.
dotnet nuget locals all --clear
dotnet build -c Release ./test/Amazon.JSII.Runtime.IntegrationTests
