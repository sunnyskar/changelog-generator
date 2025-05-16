#!/usr/bin/env python3

"""
Changelog Generator

A tool to generate user-friendly changelogs from git commit history.
Supports local repositories and GitHub URLs, with features for filtering,
previewing, and interactive selection of commits.

Dependencies:
    click: Command-line interface creation
    requests: HTTP requests for GitHub API
    gitpython: Git repository interaction
    tabulate: Table formatting
    questionary: Interactive command-line prompts
"""

from datetime import datetime
import json
import os
import re
from typing import Dict, List, Optional, Tuple, Union

import click
import git
import questionary
import requests
from tabulate import tabulate
from dataclasses import dataclass

# Constants
API_KEY = os.getenv("ANTHROPIC_API_KEY", "")  # Get API key from environment variable
API_URL = "https://api.anthropic.com/v1/messages"

# Commit scoring constants
IMPORTANT_KEYWORDS = {
    'feat': 3, 'feature': 3, 'add': 2, 'implement': 2,
    'fix': 2, 'bug': 2, 'issue': 2, 'resolve': 2,
    'breaking': 4, 'security': 4, 'vulnerability': 4,
    'performance': 3, 'optimize': 3, 'improve': 2,
    'refactor': 1, 'update': 1, 'upgrade': 2
}

TRIVIAL_KEYWORDS = {
    'chore': -1, 'typo': -1, 'format': -1, 'style': -1,
    'merge': -1, 'wip': -1, 'temp': -1
}

IMPORTANT_DIRS = {'src/', 'app/', 'lib/', 'core/', 'api/'}
SCORE_RANGE = (-5, 10)  # (min_score, max_score)

# Display constants
MAX_MESSAGE_LENGTH = 60
SHORT_HASH_LENGTH = 7
DATE_FORMAT = '%Y-%m-%d %H:%M'

@dataclass
class ChangelogParams:
    """Parameters for changelog generation."""
    repo_path: str
    num_commits: int
    output: Optional[str] = None
    from_date: Optional[str] = None
    to_date: Optional[str] = None
    exclude_patterns: List[str] = None
    categories: List[str] = None
    tags: List[str] = None
    silent: bool = False
    preview: bool = False
    interactive: bool = False
    hide_scores: bool = False

    def __post_init__(self):
        """Initialize default values for lists."""
        if self.exclude_patterns is None:
            self.exclude_patterns = []
        if self.categories is None:
            self.categories = []
        if self.tags is None:
            self.tags = []

def extract_github_info(repo_url: str) -> Tuple[str, str]:
    """
    Extract owner and repo name from GitHub URL.
    
    Args:
        repo_url (str): GitHub repository URL
        
    Returns:
        Tuple[str, str]: (owner, repo_name)
        
    Raises:
        ValueError: If the URL is not a valid GitHub repository URL
    """
    pattern = r'(?:https://github\.com/|git@github\.com:)([^/]+)/([^/]+?)(?:\.git)?$'
    match = re.match(pattern, repo_url)

    if not match:
        raise ValueError("Invalid GitHub repository URL")
    
    return match.groups()

def get_github_commits(owner: str, repo: str, num_commits: int, 
                      from_date: Optional[str] = None, 
                      to_date: Optional[str] = None) -> List[Dict]:
    """
    Fetch commits from GitHub using the REST API.
    
    Args:
        owner (str): Repository owner
        repo (str): Repository name
        num_commits (int): Number of commits to fetch
        from_date (Optional[str]): Only include commits after this date (ISO format)
        to_date (Optional[str]): Only include commits before this date (ISO format)
        
    Returns:
        List[Dict]: List of commit information
        
    Raises:
        requests.exceptions.RequestException: If the API request fails
    """
    url = f"https://api.github.com/repos/{owner}/{repo}/commits"
    params = {"per_page": num_commits}
    
    if from_date:
        params["since"] = from_date
    if to_date:
        params["until"] = to_date
    
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        commits_data = response.json()
        
        return [
            {
                "hash": commit["sha"],
                "author": commit["commit"]["author"]["name"],
                "date": commit["commit"]["author"]["date"],
                "message": commit["commit"]["message"].strip()
            }
            for commit in commits_data
        ]
    except requests.exceptions.RequestException as e:
        raise requests.exceptions.RequestException(f"Error fetching commits from GitHub: {str(e)}")

def get_git_commits(repo_path: str, num_commits: int, from_date: Optional[str] = None, to_date: Optional[str] = None, 
                   exclude_patterns: Optional[List[str]] = None,
                   tags: Optional[List[str]] = None) -> List[Dict]:
    """
    Fetch the last n commits from the git repository.
    Returns a list of commit information.

    Args:
        repo_path (str): The path to the git repository or GitHub URL.
        num_commits (int): The number of commits to fetch.
        from_date (str): Only include commits after this date (ISO format)
        to_date (str): Only include commits before this date (ISO format)
        exclude_patterns (List[str]): List of patterns to exclude from commit messages
        tags (List[str]): List of specific tags to include commits from

    Returns:
        List[Dict]: A list of dictionaries, each containing commit information.
    """
    try:
        # Check if it's a GitHub URL
        if repo_path.startswith(('https://github.com/', 'git@github.com:')):
            owner, repo = extract_github_info(repo_path)
            return get_github_commits(owner, repo, num_commits, from_date, to_date)
        else:
            # Handle local repository
            repo = git.Repo(repo_path)
            if repo.bare:
                click.echo(f"Error: Repository path '{repo_path}' is not a git repository")
                exit(1)
            
            # Get all commits first
            commits = list(repo.iter_commits())
            
            # Apply tag filters
            if tags:
                try:
                    # Get commits for each specified tag
                    tag_commits = []
                    for tag_name in tags:
                        if tag_name not in repo.tags:
                            click.echo(f"Warning: Tag {tag_name} not found in repository")
                            continue
                        tag_commits.append(repo.tags[tag_name].commit)
                    
                    if tag_commits:
                        # Filter commits to only include those from the specified tags
                        commits = [c for c in commits if c in tag_commits]
                    else:
                        click.echo("Error: None of the specified tags were found in the repository")
                        exit(1)
                except Exception as e:
                    click.echo(f"Error processing tags: {str(e)}")
                    exit(1)
            
            # Apply date filters
            if from_date:
                from_date_obj = datetime.fromisoformat(from_date)
                commits = [c for c in commits if c.committed_datetime >= from_date_obj]
            if to_date:
                to_date_obj = datetime.fromisoformat(to_date)
                commits = [c for c in commits if c.committed_datetime <= to_date_obj]
            if exclude_patterns:
                commits = [c for c in commits if not any(p in c.message for p in exclude_patterns)]
            
            # Take the requested number of commits
            commits = commits[:num_commits]
            
            return [
                {
                    "hash": commit.hexsha,
                    "author": commit.author.name,
                    "date": commit.committed_datetime.isoformat(),
                    "message": commit.message.strip()
                }
                for commit in commits
            ]
    
    except Exception as e:
        click.echo(f"Error fetching commits: {str(e)}")
        exit(1)

def generate_changelog(commits: List[Dict], categories: Optional[List[str]] = None) -> str:
    """
    Generate a changelog using the Claude API based on commit information.

    Args:
        commits (List[Dict]): A list of dictionaries, each containing commit information.
        categories (List[str]): Optional list of custom categories to use

    Returns:
        str: The generated changelog in markdown format.
    """
    if not API_KEY:
        raise ValueError("ANTHROPIC_API_KEY environment variable is not set")

    # Prepare the prompt
    commit_info = "\n".join([
        f"Commit: {commit['hash']}\n"
        f"Author: {commit['author']}\n"
        f"Date: {commit['date']}\n"
        f"Message: {commit['message']}\n"
        for commit in commits
    ])
    
    categories_text = ""
    if categories:
        categories_text = f"\nCustom Categories to use: {', '.join(categories)}"
    
    prompt = f"""Based on the following git commit history, generate a user-friendly changelog in markdown format.
    The output should ONLY contain the markdown content, with no additional text or explanations.
    
    Requirements:
    1. Use proper markdown formatting with headers (##), lists (-), and code blocks where appropriate
    2. Categorize changes under headers like "## Features", "## Bug Fixes", "## Improvements"{categories_text}
    3. Group related commits together under single bullet points
    4. Filter out trivial changes (typos, whitespace, formatting) unless they're significant
    5. Focus on user-relevant changes and high-level summaries
    6. For multiple similar commits, combine them into a single meaningful entry
    7. Use clear, concise language that emphasizes impact
    8. Follow standard changelog format
    9. Do not include any text before or after the markdown content
    10. Do not include any explanations or notes about the formatting
    11. If there are many small commits, focus on the most impactful changes
    12. Group commits by feature or component when possible

    Commit History:
    {commit_info}

    Generate a clean markdown changelog suitable for a company website. Focus on meaningful changes that users would care about, and group related changes together."""

    # Prepare API request
    headers = {
        "x-api-key": API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json"
    }
    
    data = {
        "model": "claude-3-5-sonnet-20241022",
        "max_tokens": 4096,
        "temperature": 0.5,
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ]
    }

    try:
        response = requests.post(API_URL, headers=headers, json=data)
        response.raise_for_status()
        result = response.json()
        
        if "content" not in result or not result["content"]:
            raise ValueError("Invalid response format from API")
            
        changelog = result["content"][0]["text"].strip()
        
        # Ensure the output starts with a markdown header
        if not changelog.startswith('#'):
            changelog = f"# Changelog\n\n{changelog}"
            
        return changelog
    
    except requests.exceptions.RequestException as e:
        click.echo(f"Error generating changelog: {str(e)}")
        if hasattr(e.response, 'text'):
            click.echo(f"API Response: {e.response.text}")
        exit(1)
    except Exception as e:
        click.echo(f"Error generating changelog: {str(e)}")
        exit(1)

def score_commit(commit: Dict, repo: Optional[git.Repo] = None) -> Tuple[int, str]:
    """
    Score a commit based on various factors.
    
    Args:
        commit (Dict): Commit information
        repo (Optional[git.Repo]): Git repository object for local repos
        
    Returns:
        Tuple[int, str]: (score, explanation)
    """
    score = 0
    explanations = []
    
    # Score based on commit message
    message = commit['message'].lower()
    
    # Check important keywords
    for keyword, points in IMPORTANT_KEYWORDS.items():
        if keyword in message:
            score += points
            explanations.append(f"+{points} for '{keyword}'")
    
    # Check trivial keywords
    for keyword, points in TRIVIAL_KEYWORDS.items():
        if keyword in message:
            score += points
            explanations.append(f"{points} for '{keyword}'")
    
    # Score based on message length
    if len(message) > 100:
        score += 1
        explanations.append("+1 for detailed message")
    
    # For local repositories, score based on diff
    if repo and 'hash' in commit:
        try:
            commit_obj = repo.commit(commit['hash'])
            stats = commit_obj.stats.total
            
            # Score based on number of files changed
            if stats['files'] > 5:
                score += 2
                explanations.append("+2 for many files changed")
            elif stats['files'] > 2:
                score += 1
                explanations.append("+1 for multiple files changed")
            
            # Score based on number of insertions/deletions
            total_changes = stats['insertions'] + stats['deletions']
            if total_changes > 100:
                score += 2
                explanations.append("+2 for large changes")
            elif total_changes > 50:
                score += 1
                explanations.append("+1 for significant changes")
            
            # Check if changes are in important directories
            for file in commit_obj.stats.files.keys():
                if any(file.startswith(d) for d in IMPORTANT_DIRS):
                    score += 1
                    explanations.append("+1 for changes in important directory")
                    break
            
        except Exception:
            pass
    
    # Cap the score
    score = max(SCORE_RANGE[0], min(SCORE_RANGE[1], score))
    
    # Create explanation string
    explanation = " | ".join(explanations) if explanations else "No significant factors"
    
    return score, explanation

def format_commit_preview(commit: Dict, score_info: Optional[Tuple[int, str]] = None) -> List[str]:
    """
    Format a commit for preview display.
    
    Args:
        commit (Dict): Commit information
        score_info (Optional[Tuple[int, str]]): Score and explanation
        
    Returns:
        List[str]: Formatted commit information
    """
    # Truncate hash
    short_hash = commit['hash'][:SHORT_HASH_LENGTH]
    
    # Format date
    date = datetime.fromisoformat(commit['date'].replace('Z', '+00:00'))
    formatted_date = date.strftime(DATE_FORMAT)
    
    # Truncate message if too long
    message = commit['message']
    if len(message) > MAX_MESSAGE_LENGTH:
        message = message[:MAX_MESSAGE_LENGTH - 3] + "..."
    
    # Add score if available
    if score_info:
        score, _ = score_info
        return [short_hash, commit['author'], formatted_date, f"[{score:+d}] {message}"]
    else:
        return [short_hash, commit['author'], formatted_date, message]

def format_commit_choice(commit: Dict, score_info: Optional[Tuple[int, str]] = None) -> str:
    """
    Format a commit for interactive selection display.
    
    Args:
        commit (Dict): Commit information
        score_info (Optional[Tuple[int, str]]): Score and explanation
        
    Returns:
        str: Formatted commit information
    """
    # Truncate hash
    short_hash = commit['hash'][:SHORT_HASH_LENGTH]
    
    # Format date
    date = datetime.fromisoformat(commit['date'].replace('Z', '+00:00'))
    formatted_date = date.strftime(DATE_FORMAT)
    
    # Truncate message if too long
    message = commit['message']
    if len(message) > MAX_MESSAGE_LENGTH:
        message = message[:MAX_MESSAGE_LENGTH - 3] + "..."
    
    # Add score if available
    if score_info:
        score, _ = score_info
        return f"{short_hash} | {commit['author']} | {formatted_date} | [{score:+d}] {message}"
    else:
        return f"{short_hash} | {commit['author']} | {formatted_date} | {message}"

def validate_parameters(params: ChangelogParams) -> None:
    """
    Validate all command-line parameters for type and value correctness.
    
    Args:
        params (ChangelogParams): Parameters for changelog generation
        
    Raises:
        TypeError: If any parameter has incorrect type
        ValueError: If any parameter has invalid value
    """
    # Type checking for all parameters
    if not isinstance(params.num_commits, int):
        raise TypeError(f"Expected int for num_commits, got {type(params.num_commits)}")
    if not isinstance(params.repo_path, str):
        raise TypeError(f"Expected str for repo_path, got {type(params.repo_path)}")
    if params.output is not None and not isinstance(params.output, str):
        raise TypeError(f"Expected str or None for output, got {type(params.output)}")
    if params.from_date is not None and not isinstance(params.from_date, str):
        raise TypeError(f"Expected str or None for from_date, got {type(params.from_date)}")
    if params.to_date is not None and not isinstance(params.to_date, str):
        raise TypeError(f"Expected str or None for to_date, got {type(params.to_date)}")
    if not isinstance(params.exclude_patterns, list):
        raise TypeError(f"Expected list for exclude_patterns, got {type(params.exclude_patterns)}")
    if not isinstance(params.categories, list):
        raise TypeError(f"Expected list for categories, got {type(params.categories)}")
    if not isinstance(params.tags, list):
        raise TypeError(f"Expected list for tags, got {type(params.tags)}")
    if not isinstance(params.silent, bool):
        raise TypeError(f"Expected bool for silent, got {type(params.silent)}")
    if not isinstance(params.preview, bool):
        raise TypeError(f"Expected bool for preview, got {type(params.preview)}")
    if not isinstance(params.interactive, bool):
        raise TypeError(f"Expected bool for interactive, got {type(params.interactive)}")
    if not isinstance(params.hide_scores, bool):
        raise TypeError(f"Expected bool for hide_scores, got {type(params.hide_scores)}")

    # Validate num_commits
    if params.num_commits <= 0:
        raise ValueError("Number of commits must be greater than 0")

    # Validate dates if provided
    if params.from_date:
        try:
            datetime.fromisoformat(params.from_date)
        except ValueError:
            raise ValueError(f"Invalid from_date format. Expected ISO format (YYYY-MM-DD), got {params.from_date}")
    
    if params.to_date:
        try:
            datetime.fromisoformat(params.to_date)
        except ValueError:
            raise ValueError(f"Invalid to_date format. Expected ISO format (YYYY-MM-DD), got {params.to_date}")

    # Validate date range if both dates are provided
    if params.from_date and params.to_date:
        from_date_obj = datetime.fromisoformat(params.from_date)
        to_date_obj = datetime.fromisoformat(params.to_date)
        if from_date_obj > to_date_obj:
            raise ValueError("from_date must be earlier than to_date")

    # Validate output path if provided
    if params.output:
        try:
            # Check if the directory exists and is writable
            output_dir = os.path.dirname(params.output)
            if output_dir and not os.path.exists(output_dir):
                raise ValueError(f"Output directory does not exist: {output_dir}")
            if output_dir and not os.access(output_dir, os.W_OK):
                raise ValueError(f"No write permission for output directory: {output_dir}")
        except Exception as e:
            raise ValueError(f"Error validating output path: {str(e)}")

@click.command()
@click.argument('repo_path', type=str)
@click.argument('num_commits', type=int)
@click.option('--output', '-o', type=click.Path(), help='Save the changelog to a markdown file (optional)')
@click.option('--from-date', type=str, help='Only include commits after this date (ISO format, e.g., 2024-01-01)')
@click.option('--to-date', type=str, help='Only include commits before this date (ISO format, e.g., 2024-01-01)')
@click.option('--exclude', '-e', multiple=True, help='Exclude commits containing these patterns (can be used multiple times)')
@click.option('--categories', '-c', multiple=True, help='Custom categories to use in the changelog (can be used multiple times)')
@click.option('--tags', '-t', multiple=True, help='Include commits from specific tags (can be used multiple times)')
@click.option('--silent', '-s', is_flag=True, help='Suppress all output except the changelog content')
@click.option('--preview', '-p', is_flag=True, help='Preview commits that would be included in the changelog')
@click.option('--interactive', '-i', is_flag=True, help='Interactively select which commits to include')
@click.option('--hide-scores', is_flag=True, help='Hide impact scores for commits (scores are shown by default in preview and interactive modes)')
def main(num_commits: int, repo_path: str, output: str, from_date: str, to_date: str,
         exclude: tuple, categories: tuple, tags: tuple, silent: bool, preview: bool, 
         interactive: bool, hide_scores: bool) -> None:
    """
    Generate a user-friendly changelog from git commit history.

    REPO_PATH: Path to local git repository or GitHub URL (e.g., https://github.com/username/repo.git)
    
    NUM_COMMITS: Number of commits to include in the changelog

    This tool analyzes git commits and generates a well-formatted changelog that:
    - Groups related changes together
    - Categorizes changes (Features, Bug Fixes, etc.)
    - Focuses on user-relevant changes
    - Formats output in clean markdown

    Examples:
        # Generate changelog for last 10 commits from a local repository
        ./changelog_generator.py /path/to/repo 10

        # Generate changelog from GitHub repository and save to file
        ./changelog_generator.py https://github.com/username/repo.git 10 -o changelog.md

        # Filter commits by date range
        ./changelog_generator.py /path/to/repo 10 --from-date 2024-01-01 --to-date 2024-02-01

        # Use custom categories and exclude certain commits
        ./changelog_generator.py /path/to/repo 10 -c "New Features" -c "Breaking Changes" -e "chore:" -e "docs:"

        # Generate changelog for specific tags
        ./changelog_generator.py /path/to/repo 10 -t v1.0.0 -t v1.1.0 -t v1.2.0

        # Preview commits that would be included (with impact scores)
        ./changelog_generator.py /path/to/repo 10 --preview

        # Preview without impact scores
        ./changelog_generator.py /path/to/repo 10 --preview --hide-scores

        # Interactively select which commits to include (with impact scores)
        ./changelog_generator.py /path/to/repo 10 --interactive

        # Silent mode - only output the changelog content
        ./changelog_generator.py /path/to/repo 10 -s

        # Display help
        ./changelog_generator.py --help
    """
    # Create parameter struct
    params = ChangelogParams(
        repo_path=repo_path,
        num_commits=num_commits,
        output=output,
        from_date=from_date,
        to_date=to_date,
        exclude_patterns=list(exclude),
        categories=list(categories),
        tags=list(tags),
        silent=silent,
        preview=preview,
        interactive=interactive,
        hide_scores=hide_scores
    )

    try:
        # Validate all parameters
        validate_parameters(params)
    except (TypeError, ValueError) as e:
        click.echo(f"Error: {str(e)}")
        exit(1)

    if not params.silent:
        click.echo(f"Generating changelog for the last {params.num_commits} commits...")
    
    # Get commits
    commits = get_git_commits(
        params.repo_path, 
        params.num_commits, 
        params.from_date, 
        params.to_date, 
        params.exclude_patterns,
        params.tags
    )
    
    if not commits:
        click.echo("No commits found matching the specified criteria.")
        return

    # Get repository object for scoring if it's a local repo
    repo = None
    if not params.repo_path.startswith(('https://github.com/', 'git@github.com:')):
        try:
            repo = git.Repo(params.repo_path)
        except Exception:
            pass

    # Calculate scores if in preview or interactive mode and scores aren't hidden
    commit_scores = {}
    if (params.preview or params.interactive) and not params.hide_scores:
        for commit in commits:
            commit_scores[commit['hash']] = score_commit(commit, repo)
    
    # Show preview if requested
    if params.preview:
        click.echo("\nPreview of commits to be included in the changelog:")
        click.echo("=" * 100)
        
        # Format commits for display
        preview_data = [
            format_commit_preview(
                commit, 
                commit_scores.get(commit['hash']) if not params.hide_scores else None
            ) 
            for commit in commits
        ]
        
        # Create preview table
        headers = ["Hash", "Author", "Date", "Message"]
        if not params.hide_scores:
            headers[3] = "Message (with impact score)"
        table = tabulate(preview_data, headers=headers, tablefmt="grid")
        click.echo(table)
        
        if not params.hide_scores:
            click.echo("\nImpact Score Explanations:")
            click.echo("=" * 100)
            for commit in commits:
                score, explanation = commit_scores[commit['hash']]
                click.echo(f"{commit['hash'][:SHORT_HASH_LENGTH]}: {explanation}")
        
        click.echo(f"\nTotal commits: {len(commits)}")
        return

    # Interactive selection if requested
    if params.interactive:
        click.echo("\nSelect commits to include in the changelog:")
        click.echo("Use space to select/deselect, arrow keys to navigate, and enter to confirm")
        
        # Create choices for questionary
        choices = [
            questionary.Choice(
                title=format_commit_choice(
                    commit,
                    commit_scores.get(commit['hash']) if not params.hide_scores else None
                ),
                value=i,
                checked=True  # All commits selected by default
            )
            for i, commit in enumerate(commits)
        ]
        
        # Get user selection
        selected_indices = questionary.checkbox(
            "Select commits to include:",
            choices=choices
        ).ask()
        
        if not selected_indices:
            click.echo("No commits selected. Exiting.")
            return
            
        # Filter commits based on selection
        commits = [commits[i] for i in selected_indices]
        click.echo(f"\nSelected {len(commits)} commits for changelog generation.")
    
    # Generate changelog
    changelog = generate_changelog(commits, params.categories)
    
    # Save to file if output path is provided
    if params.output:
        try:
            with open(params.output, 'w') as f:
                f.write(changelog)
            if not params.silent:
                click.echo(f"Changelog saved to: {params.output}")
        except Exception as e:
            click.echo(f"Error saving changelog to file: {str(e)}")
            exit(1)
    else:
        # Only display the changelog if no output file is specified
        if not params.silent:
            click.echo("\nGenerated Changelog:")
            click.echo("=" * 50)
        click.echo(changelog)

if __name__ == '__main__':
    main() 