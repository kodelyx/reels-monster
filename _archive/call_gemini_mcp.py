#!/usr/bin/env python3
import sys
import json
import subprocess
import argparse
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(description="Call Gemini MCP inside Docker safely.")
    parser.add_argument("--prompt_path", help="Path to the prompt markdown file")
    parser.add_argument("--prompt", help="Direct text prompt instead of loading from a file")
    parser.add_argument("--tool_name", default="chat", help="Name of the MCP tool to invoke")
    parser.add_argument("--prompt_key", default="prompt", help="Key name for the prompt argument")
    parser.add_argument("--vars", default="{}", help="JSON string of variables to format the prompt with")
    parser.add_argument("--output_path", help="Optional path to save the parsed text result")
    args = parser.parse_args()

    # 1. Get prompt content
    if args.prompt:
        prompt_content = args.prompt
    elif args.prompt_path:
        prompt_path = Path(args.prompt_path)
        if not prompt_path.exists():
            print(f"❌ Prompt file not found: {prompt_path}")
            sys.exit(1)
        prompt_content = prompt_path.read_text(encoding="utf-8")
    else:
        print("❌ Either --prompt or --prompt_path must be specified.")
        sys.exit(1)

    # 2. Parse variables and substitute if variables exist
    if args.vars != "{}":
        try:
            variables = json.loads(args.vars)
        except json.JSONDecodeError as e:
            print(f"❌ Failed to parse --vars as JSON: {e}")
            sys.exit(1)

        formatted_prompt = prompt_content
        for key, value in variables.items():
            placeholder_curly = f"{{{key}}}"
            placeholder_double = f"{{{{{key}}}}}"
            formatted_prompt = formatted_prompt.replace(placeholder_double, str(value))
            formatted_prompt = formatted_prompt.replace(placeholder_curly, str(value))
    else:
        formatted_prompt = prompt_content

    # 3. Construct JSON-RPC Request
    request_data = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": args.tool_name,
            "arguments": {
                args.prompt_key: formatted_prompt
            }
        }
    }

    # 4. Run via docker exec
    try:
        from config import GEMINI_MCP_CMD
        proc = subprocess.run(
            GEMINI_MCP_CMD,
            input=json.dumps(request_data),
            capture_output=True,
            text=True,
            check=True
        )
    except subprocess.CalledProcessError as e:
        print(f"❌ Docker execution failed: {e}")
        print(f"Stderr: {e.stderr}")
        sys.exit(1)

    # 5. Parse JSON-RPC Response
    # The output might contain startup logs (like "🔌 Starting Gemini MCP Server...") 
    # followed by the JSON response. We need to find the JSON boundary.
    stdout_lines = proc.stdout.strip().split("\n")
    json_response = None
    for line in stdout_lines:
        if line.startswith("{") and line.endswith("}"):
            try:
                json_response = json.loads(line)
                break
            except json.JSONDecodeError:
                continue

    if not json_response:
        print("❌ Failed to find valid JSON response from MCP server.")
        print(f"Raw Output:\n{proc.stdout}")
        sys.exit(1)

    # Check for error in JSON-RPC
    if "error" in json_response:
        print(f"❌ MCP Tool Error: {json_response['error']}")
        sys.exit(1)

    result = json_response.get("result", {})
    content = ""
    # Extract content from result
    if "content" in result and isinstance(result["content"], list):
        for item in result["content"]:
            if item.get("type") == "text":
                content += item.get("text", "")

    if not content:
        # Fallback to string result
        content = str(result)

    # 6. Save or Print output
    if args.output_path:
        out_path = Path(args.output_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(content, encoding="utf-8")
        print(f"✅ Output successfully saved to: {out_path}")
    else:
        print(content)

if __name__ == "__main__":
    main()
