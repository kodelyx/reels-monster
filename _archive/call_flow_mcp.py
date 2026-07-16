#!/usr/bin/env python3
import sys
import json
import subprocess
import argparse
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(description="Call Flow MCP inside Docker safely.")
    parser.add_argument("--tool_name", required=True, help="Name of the MCP tool to invoke")
    parser.add_argument("--args", default="{}", help="JSON string of arguments for the tool")
    args = parser.parse_args()

    # 1. Parse arguments JSON
    try:
        tool_args = json.loads(args.args)
    except json.JSONDecodeError as e:
        print(f"❌ Failed to parse --args as JSON: {e}")
        sys.exit(1)

    # 2. Construct JSON-RPC Request
    request_data = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": args.tool_name,
            "arguments": tool_args
        }
    }

    # 3. Run via docker exec
    try:
        proc = subprocess.run(
            ["docker", "exec", "-i", "flow-agent-server", "python3", "-u", "/app/flow_mcp_server.py"],
            input=json.dumps(request_data),
            capture_output=True,
            text=True,
            check=True
        )
    except subprocess.CalledProcessError as e:
        print(f"❌ Docker execution failed: {e}")
        print(f"Stderr: {e.stderr}")
        sys.exit(1)

    # 4. Parse JSON-RPC Response
    stdout_lines = proc.stdout.strip().split("\n")
    json_response = None
    for line in stdout_lines:
        # The flow mcp server outputs log lines starting with [Flow MCP], we ignore those
        if line.startswith("{") and line.endswith("}"):
            try:
                json_response = json.loads(line)
                break
            except json.JSONDecodeError:
                continue

    if not json_response:
        print("❌ Failed to find valid JSON response from Flow MCP server.")
        print(f"Raw Output:\n{proc.stdout}")
        sys.exit(1)

    # Check for error in JSON-RPC
    if "error" in json_response:
        print(f"❌ MCP Tool Error: {json_response['error']}")
        sys.exit(1)

    result = json_response.get("result", {})
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()
