#!/usr/bin/env python3
"""
Generate Docker Compose configuration from green-agent TOML specification.

This script reads a green-agent.toml file and generates:
1. docker-compose.yml - Docker Compose configuration
2. .env.example - Example environment variables file

Usage:
    python generate_compose.py <path-to-toml> [--output-dir <dir>]

Example:
    python generate_compose.py sample-debate-green-agent/green-agent.toml
"""

import argparse
import sys
from pathlib import Path
from typing import Any, Dict, List

try:
    import tomli
except ImportError:
    try:
        import tomllib as tomli
    except ImportError:
        print("Error: tomli or tomllib module required. Install with: pip install tomli")
        sys.exit(1)


def parse_toml(toml_path: Path) -> Dict[str, Any]:
    """Parse the TOML configuration file."""
    try:
        with open(toml_path, "rb") as f:
            return tomli.load(f)
    except Exception as e:
        print(f"Error parsing TOML file: {e}")
        sys.exit(1)


def validate_config(config: Dict[str, Any]) -> None:
    """Validate that required fields are present in the config."""
    required_fields = ["green_agent"]
    for field in required_fields:
        if field not in config:
            print(f"Error: Required field '{field}' not found in TOML")
            sys.exit(1)

    green_agent = config["green_agent"]
    required_green_fields = ["image", "port"]
    for field in required_green_fields:
        if field not in green_agent:
            print(f"Error: Required field 'green_agent.{field}' not found in TOML")
            sys.exit(1)

    # Validate participants
    participants = config.get("participants", {})
    required_roles = participants.get("required_roles", [])

    if len(required_roles) < 1:
        print("Error: At least one participant role is required")
        sys.exit(1)

    for i, role in enumerate(required_roles):
        required_role_fields = ["name", "image", "port"]
        for field in required_role_fields:
            if field not in role:
                print(f"Error: Required field 'participants.required_roles[{i}].{field}' not found in TOML")
                sys.exit(1)


def generate_docker_compose(config: Dict[str, Any]) -> str:
    """Generate Docker Compose YAML content from config."""
    green_agent = config["green_agent"]
    participants = config.get("participants", {})
    required_roles = participants.get("required_roles", [])

    # Start building compose file
    lines = [
        "# Auto-generated Docker Compose file from scenario.toml",
        "# Do not edit manually - regenerate using generate_compose.py",
        "",
        "version: '3.8'",
        "",
        "services:",
    ]

    # Green agent service
    lines.extend([
        "  green-agent:",
        f"    image: {green_agent['image']}",
        f"    container_name: green-agent",
        f"    command: [\"--host\", \"0.0.0.0\", \"--port\", \"{green_agent['port']}\", \"--card-url\", \"http://green-agent:{green_agent['port']}\"]",
        "    healthcheck:",
        f"      test: [\"CMD\", \"python\", \"-c\", \"import urllib.request; urllib.request.urlopen('http://localhost:{green_agent['port']}/.well-known/agent-card.json')\"]",
        "      interval: 5s",
        "      timeout: 3s",
        "      retries: 10",
        "      start_period: 30s",
    ])

    # Green agent environment variables
    green_env = green_agent.get("environment", [])
    if green_env:
        lines.append("    environment:")
        for var in green_env:
            var_name = var["name"]
            if "default" in var:
                lines.append(f"      - {var_name}={var['default']}")
            else:
                # Required secret - use environment variable substitution
                lines.append(f"      - {var_name}=${{{var_name}}}")

    # Dependencies on participant services
    if required_roles:
        lines.append("    depends_on:")
        for role in required_roles:
            lines.append(f"      - {role['name']}")

    # Network
    lines.extend([
        "    networks:",
        "      - agent-network",
        "",
    ])

    # Participant services
    for role in required_roles:
        role_name = role["name"]
        role_image = role["image"]
        role_port = role["port"]

        lines.extend([
            f"  {role_name}:",
            f"    image: {role_image}",
            f"    container_name: {role_name}",
            f"    command: [\"--host\", \"0.0.0.0\", \"--port\", \"{role_port}\", \"--card-url\", \"http://{role_name}:{role_port}\"]",
            "    healthcheck:",
            f"      test: [\"CMD\", \"python\", \"-c\", \"import urllib.request; urllib.request.urlopen('http://localhost:{role_port}/.well-known/agent-card.json')\"]",
            "      interval: 5s",
            "      timeout: 3s",
            "      retries: 10",
            "      start_period: 30s",
        ])

        # Participant environment variables
        role_env = role.get("environment", [])
        if role_env:
            lines.append("    environment:")
            for var in role_env:
                var_name = var["name"]
                if "default" in var:
                    lines.append(f"      - {var_name}={var['default']}")
                else:
                    lines.append(f"      - {var_name}=${{{var_name}}}")

        lines.extend([
            "    networks:",
            "      - agent-network",
            "",
        ])

    # Collect all service names for runner dependencies
    all_services = ["green-agent"] + [role["name"] for role in required_roles]

    # AgentBeats runner service
    lines.extend([
        # TODO Change this line to the public image once it is set
        "  agentbeats-runner:",
        "    image: ghcr.io/komyo-ai/agentbeats-runner:latest",
        "    container_name: agentbeats-runner",
        "    volumes:",
        "      - ./runner-scenario.toml:/scenario/scenario.toml",
        "      - ./output:/app/output",
        "    command: [\"/scenario/scenario.toml\", \"/app/output/score.json\"]",
        "    depends_on:",
    ])
    for service in all_services:
        lines.extend([
            f"      {service}:",
            "        condition: service_healthy",
        ])
    lines.extend([
        "    networks:",
        "      - agent-network",
        "",
    ])

    # Networks definition
    lines.extend([
        "networks:",
        "  agent-network:",
        "    driver: bridge",
        "",
    ])

    return "\n".join(lines)


def generate_env_example(config: Dict[str, Any]) -> str:
    """Generate .env.example content from config."""
    green_agent = config["green_agent"]
    participants = config.get("participants", {})
    required_roles = participants.get("required_roles", [])

    lines = [
        "# Environment variables for agents",
        "# Copy this file to .env and fill in the required values",
        "",
    ]

    # Collect all environment variables from all agents
    all_required_vars = []
    all_optional_with_defaults = []

    # Green agent env vars
    green_env = green_agent.get("environment", [])
    for var in green_env:
        if "default" in var:
            all_optional_with_defaults.append(("green-agent", var))
        else:
            all_required_vars.append(("green-agent", var))

    # Participant env vars
    for role in required_roles:
        role_env = role.get("environment", [])
        for var in role_env:
            if "default" in var:
                all_optional_with_defaults.append((role["name"], var))
            else:
                all_required_vars.append((role["name"], var))

    # Required variables (secrets)
    if all_required_vars:
        lines.append("# Required variables (no defaults)")
        for agent_name, var in all_required_vars:
            var_name = var["name"]
            lines.append(f"# {agent_name}")
            lines.append(f"{var_name}=")
        lines.append("")

    # Optional variables with defaults
    if all_optional_with_defaults:
        lines.append("# Optional variables (defaults are set in docker-compose.yml)")
        for agent_name, var in all_optional_with_defaults:
            var_name = var["name"]
            default = var["default"]
            lines.append(f"# {agent_name}: {var_name}={default}")
        lines.append("")

    return "\n".join(lines)


def generate_runner_scenario(config: Dict[str, Any]) -> str:
    """Generate runner scenario.toml with URLs instead of images/ports."""
    green_agent = config["green_agent"]
    participants = config.get("participants", {})
    required_roles = participants.get("required_roles", [])

    lines = []

    # Green agent with URL
    lines.append("[green_agent]")
    lines.append(f"endpoint = \"http://green-agent:{green_agent['port']}\"")

    # Copy additional green agent fields (excluding known Docker-specific fields)
    docker_specific_keys = {"image", "port", "environment"}
    for key, value in green_agent.items():
        if key not in docker_specific_keys:
            if isinstance(value, str):
                lines.append(f"{key} = \"{value}\"")
            elif isinstance(value, bool):
                lines.append(f"{key} = {str(value).lower()}")
            elif isinstance(value, (int, float)):
                lines.append(f"{key} = {value}")
            elif isinstance(value, list):
                lines.append(f"{key} = {value}")

    # Copy green agent environment variables if present
    green_env = green_agent.get("environment", [])
    if green_env:
        lines.append("")
        for var in green_env:
            lines.append("[[green_agent.environment]]")
            lines.append(f"name = \"{var['name']}\"")
            if "default" in var:
                lines.append(f"default = \"{var['default']}\"")

    lines.append("")

    # Participants with URLs - use flat structure expected by client_cli.py
    for role in required_roles:
        lines.append("[[participants]]")
        lines.append(f"role = \"{role['name']}\"")
        lines.append(f"endpoint = \"http://{role['name']}:{role['port']}\"")

        # Copy additional participant fields (excluding known Docker-specific fields)
        participant_docker_keys = {"name", "image", "port", "environment"}
        for key, value in role.items():
            if key not in participant_docker_keys:
                if isinstance(value, str):
                    lines.append(f"{key} = \"{value}\"")
                elif isinstance(value, bool):
                    lines.append(f"{key} = {str(value).lower()}")
                elif isinstance(value, (int, float)):
                    lines.append(f"{key} = {value}")
                elif isinstance(value, list):
                    lines.append(f"{key} = {value}")

        # Copy participant environment variables if present
        role_env = role.get("environment", [])
        if role_env:
            lines.append("")
            for var in role_env:
                lines.append(f"[[participants.environment]]")
                lines.append(f"name = \"{var['name']}\"")
                if "default" in var:
                    lines.append(f"default = \"{var['default']}\"")

        lines.append("")

    # Preserve any additional configuration sections from the original TOML
    # Skip the known sections (green_agent, participants) and copy everything else
    known_sections = {"green_agent", "participants"}
    for section_name, section_value in config.items():
        if section_name not in known_sections:
            lines.append(f"[{section_name}]")
            if isinstance(section_value, dict):
                for key, value in section_value.items():
                    if isinstance(value, str):
                        lines.append(f"{key} = \"{value}\"")
                    elif isinstance(value, bool):
                        lines.append(f"{key} = {str(value).lower()}")
                    elif isinstance(value, (int, float)):
                        lines.append(f"{key} = {value}")
                    elif isinstance(value, list):
                        # Handle arrays
                        lines.append(f"{key} = {value}")
            lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Generate Docker Compose configuration from scenario TOML"
    )
    parser.add_argument(
        "toml_path",
        type=Path,
        help="Path to scenario.toml file"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path.cwd(),
        help="Directory to write output files (default: current directory)"
    )

    args = parser.parse_args()

    # Validate input file exists
    if not args.toml_path.exists():
        print(f"Error: TOML file not found: {args.toml_path}")
        sys.exit(1)

    # Create output directory if it doesn't exist
    args.output_dir.mkdir(parents=True, exist_ok=True)

    # Parse and validate config
    print(f"Reading configuration from {args.toml_path}")
    config = parse_toml(args.toml_path)
    validate_config(config)

    # Generate docker-compose.yml
    compose_content = generate_docker_compose(config)
    compose_path = args.output_dir / "docker-compose.yml"
    print(f"Writing {compose_path}")
    with open(compose_path, "w") as f:
        f.write(compose_content)

    # Generate runner-scenario.toml
    runner_scenario_content = generate_runner_scenario(config)
    runner_scenario_path = args.output_dir / "runner-scenario.toml"
    print(f"Writing {runner_scenario_path}")
    with open(runner_scenario_path, "w") as f:
        f.write(runner_scenario_content)

    # Generate .env.example (if there are any required env vars)
    env_content = generate_env_example(config)
    if env_content.strip():
        env_path = args.output_dir / ".env.example"
        print(f"Writing {env_path}")
        with open(env_path, "w") as f:
            f.write(env_content)

    print("\nSuccess! Generated files:")
    print(f"  - {compose_path}")
    print(f"  - {runner_scenario_path}")
    if env_content.strip():
        print(f"  - {env_path}")
    print("\nNext steps:")
    print("  1. Review the generated docker-compose.yml")
    if env_content.strip():
        print("  2. Copy .env.example to .env and fill in required values")
        print("  3. Run: docker-compose up")
    else:
        print("  2. Run: docker-compose up")


if __name__ == "__main__":
    main()
