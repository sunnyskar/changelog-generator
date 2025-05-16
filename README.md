# Changelog Generator

A Python-based tool for automating the creation of changelogs from git commit history. The tool supports both local repositories and GitHub URLs, offering features such as commit filtering, interactive selection, and intelligent commit scoring.

## Features

- Support for both local git repositories and GitHub URLs
- Commit filtering by date range and patterns
- Interactive commit selection
- Commit scoring system based on message content and file changes
- Integration with Anthropic Claude API for changelog generation
- Command-line interface with extensive customization options

## Installation

1. Clone the repository:
```bash
git clone https://github.com/your-username/changelog-generator.git
cd changelog-generator
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up your Anthropic API key:
```bash
export ANTHROPIC_API_KEY="your-api-key-here"
```

## Usage

Basic usage:
```bash
python changelog_generator.py /path/to/repo 10
```

Filter by date range:
```bash
python changelog_generator.py /path/to/repo 10 --from-date 2024-01-01 --to-date 2024-02-01
```

Use custom categories and exclude patterns:
```bash
python changelog_generator.py /path/to/repo 10 -c "New Features" -c "Bug Fixes" -e "chore:" -e "docs:"
```

Interactive mode:
```bash
python changelog_generator.py /path/to/repo 10 --interactive
```

## Documentation

For detailed documentation, please refer to the project report in `project_report.tex`.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- GitPython for repository interaction
- Click for command-line interface
- Questionary for interactive prompts
- Anthropic Claude API for changelog generation 