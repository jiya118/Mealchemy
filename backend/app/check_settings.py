"""
Settings Configuration Validator
Run this script to validate your .env file against your Settings class.
This helps catch configuration errors before starting the application.
"""

import re
import sys
from pathlib import Path
from typing import Set, Tuple


class Colors:
    """ANSI color codes for terminal output."""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'


def extract_env_variables(env_path: str = ".env") -> Set[str]:
    """
    Extract all variable names from .env file.
    
    Args:
        env_path: Path to the .env file
        
    Returns:
        Set of variable names found in .env
    """
    env_file = Path(env_path)
    if not env_file.exists():
        print(f"{Colors.RED}❌ {env_path} not found!{Colors.END}")
        return set()
    
    variables = set()
    with open(env_file, encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            # Skip empty lines and comments
            if not line or line.startswith('#'):
                continue
            
            # Extract variable name
            if '=' in line:
                var_name = line.split('=')[0].strip()
                if var_name:
                    variables.add(var_name)
            else:
                print(f"{Colors.YELLOW}⚠️  Line {line_num}: Invalid format (missing '='): {line}{Colors.END}")
    
    return variables


def extract_settings_fields(settings_path: str = "app/core/settings.py") -> Set[str]:
    """
    Extract all field names from Settings class.
    
    Args:
        settings_path: Path to the settings.py file
        
    Returns:
        Set of field names defined in Settings class
    """
    settings_file = Path(settings_path)
    if not settings_file.exists():
        print(f"{Colors.RED}❌ {settings_path} not found!{Colors.END}")
        return set()
    
    fields = set()
    with open(settings_file, encoding='utf-8') as f:
        content = f.read()
        
        # Find all uppercase field definitions with type hints
        # Pattern matches: FIELD_NAME: type = ...
        pattern = r'^\s+([A-Z][A-Z0-9_]*):\s*'
        matches = re.finditer(pattern, content, re.MULTILINE)
        
        for match in matches:
            field_name = match.group(1)
            # Skip if it's inside a comment
            line_start = content.rfind('\n', 0, match.start()) + 1
            line = content[line_start:match.end()]
            if not line.strip().startswith('#'):
                fields.add(field_name)
    
    return fields


def check_required_fields(settings_path: str = "app/core/settings.py") -> Set[str]:
    """
    Find fields that are marked as required (no default value).
    
    Args:
        settings_path: Path to the settings.py file
        
    Returns:
        Set of required field names
    """
    settings_file = Path(settings_path)
    if not settings_file.exists():
        return set()
    
    required = set()
    with open(settings_file, encoding='utf-8') as f:
        content = f.read()
        
        # Pattern matches fields with Field(...) - no default
        # Also matches fields with just type annotation and ... (e.g., MONGODB_URL: str = ...)
        patterns = [
            r'^\s+([A-Z][A-Z0-9_]*):\s*.*?Field\(\s*\.\.\.',
            r'^\s+([A-Z][A-Z0-9_]*):\s*\w+\s*=\s*\.\.\.',
        ]
        
        for pattern in patterns:
            matches = re.finditer(pattern, content, re.MULTILINE | re.DOTALL)
            for match in matches:
                required.add(match.group(1))
    
    return required


def analyze_configuration() -> Tuple[bool, dict]:
    """
    Analyze the configuration and return validation results.
    
    Returns:
        Tuple of (is_valid, results_dict)
    """
    print(f"{Colors.BOLD}{Colors.BLUE}")
    print("=" * 70)
    print("🔍 SETTINGS CONFIGURATION VALIDATOR")
    print("=" * 70)
    print(Colors.END)
    print()
    
    # Extract variables and fields
    env_vars = extract_env_variables()
    settings_fields = extract_settings_fields()
    required_fields = check_required_fields()
    
    # Display counts
    print(f"{Colors.BOLD}Configuration Summary:{Colors.END}")
    print(f"📄 Variables in .env: {len(env_vars)}")
    print(f"⚙️  Fields in Settings: {len(settings_fields)}")
    print(f"🔒 Required fields: {len(required_fields)}")
    print()
    
    results = {
        'env_vars': env_vars,
        'settings_fields': settings_fields,
        'required_fields': required_fields,
        'extra_in_env': set(),
        'missing_required': set(),
        'missing_optional': set(),
    }
    
    # Check for extra variables in .env
    extra_in_env = env_vars - settings_fields
    results['extra_in_env'] = extra_in_env
    
    # Check for missing required fields
    missing_required = required_fields - env_vars
    results['missing_required'] = missing_required
    
    # Check for missing optional fields (informational only)
    missing_optional = (settings_fields - required_fields) - env_vars
    results['missing_optional'] = missing_optional
    
    is_valid = True
    
    # Report extra variables
    if extra_in_env:
        is_valid = False
        print(f"{Colors.RED}{Colors.BOLD}❌ CRITICAL: Extra variables in .env{Colors.END}")
        print(f"{Colors.RED}These variables are not defined in Settings class:{Colors.END}")
        for var in sorted(extra_in_env):
            print(f"   {Colors.RED}• {var}{Colors.END}")
        print()
        print(f"{Colors.YELLOW}💡 Fix: Add these fields to app/core/settings.py or remove from .env{Colors.END}")
        print()
    
    # Report missing required fields
    if missing_required:
        is_valid = False
        print(f"{Colors.RED}{Colors.BOLD}❌ CRITICAL: Missing required fields{Colors.END}")
        print(f"{Colors.RED}These fields are required but not in .env:{Colors.END}")
        for var in sorted(missing_required):
            print(f"   {Colors.RED}• {var}{Colors.END}")
        print()
        print(f"{Colors.YELLOW}💡 Fix: Add these variables to your .env file{Colors.END}")
        print()
    
    # Report missing optional fields (informational)
    if missing_optional:
        print(f"{Colors.YELLOW}ℹ️  Optional fields not in .env (using defaults):{Colors.END}")
        for var in sorted(missing_optional):
            print(f"   {Colors.YELLOW}• {var}{Colors.END}")
        print()
    
    # Success message
    if is_valid:
        print(f"{Colors.GREEN}{Colors.BOLD}✅ Configuration is valid!{Colors.END}")
        print(f"{Colors.GREEN}All .env variables are properly defined in Settings class.{Colors.END}")
        print(f"{Colors.GREEN}All required fields are present in .env file.{Colors.END}")
    else:
        print(f"{Colors.RED}{Colors.BOLD}❌ Configuration validation FAILED!{Colors.END}")
        print(f"{Colors.RED}Please fix the errors above before starting the application.{Colors.END}")
    
    print()
    print("=" * 70)
    print()
    
    return is_valid, results


def generate_missing_fields_code(missing_fields: Set[str]) -> None:
    """
    Generate Python code for missing fields to add to Settings class.
    
    Args:
        missing_fields: Set of field names to generate code for
    """
    if not missing_fields:
        return
    
    print(f"{Colors.BLUE}{Colors.BOLD}📝 Suggested code to add to Settings class:{Colors.END}")
    print()
    print("```python")
    for field in sorted(missing_fields):
        print(f"    {field}: str = Field(")
        print(f"        ...,  # or provide a default value")
        print(f'        description="Description for {field}"')
        print(f"    )")
        print()
    print("```")
    print()


def main() -> int:
    """
    Main entry point for the validator.
    
    Returns:
        Exit code (0 for success, 1 for failure)
    """
    try:
        is_valid, results = analyze_configuration()
        
        # Generate helpful code snippets
        if results['extra_in_env']:
            generate_missing_fields_code(results['extra_in_env'])
        
        return 0 if is_valid else 1
        
    except Exception as e:
        print(f"{Colors.RED}{Colors.BOLD}❌ Error during validation:{Colors.END}")
        print(f"{Colors.RED}{str(e)}{Colors.END}")
        return 1


if __name__ == "__main__":
    sys.exit(main())