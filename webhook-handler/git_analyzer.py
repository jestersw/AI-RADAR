from git import Repo
import tempfile
import shutil
from dependency_parser import DependencyParser

class GitAnalyzer:
    def __init__(self):
        self.dependency_parser = DependencyParser()
    
    def handle_push_event(self, payload):
        repo_url = payload['repository']['clone_url']
        branch = payload['ref'].split('/')[-1]
        commits = payload['commits']
        results = []
        for commit in commits:
            commit_analysis = self.analyze_commit(
                repo_url,
                commit['id'],
                branch,
                commit.get('message', '')
            )
            if commit_analysis['dependency_changes']:
                results.append(commit_analysis)
        return results

    def handle_pr_event(self, payload):
        if payload.get('action') not in ['opened', 'synchronize']:
            return []
        repo_url = payload['repository']['clone_url']
        pr_branch = payload['pull_request']['head']['ref']
        base_branch = payload['pull_request']['base']['ref']
        return self.analyze_pr_diff(repo_url, base_branch, pr_branch)
    
    def analyze_commit(self, repo_url, commit_sha, branch, commit_message):
        temp_dir = tempfile.mkdtemp()
        try:
            repo = Repo.clone_from(repo_url, temp_dir)
            commit = repo.commit(commit_sha)
            if commit.parents:
                diff_index = commit.parents[0].diff(commit)
            else:
                diff_index = commit.diff(None)
            dependency_changes = []
            for diff_item in diff_index:
                file_path = diff_item.a_path or diff_item.b_path
                if self.is_dependency_file(file_path):
                    change_info = self.analyze_dependency_change(diff_item)
                    if change_info:
                        dependency_changes.append(change_info)
            return {
                'commit_sha': commit_sha,
                'branch': branch,
                'message': commit_message,
                'dependency_changes': dependency_changes
            }
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
    
    def is_dependency_file(self, file_path):
        dependency_files = [
            'package.json', 'package-lock.json', 'yarn.lock',
            'requirements.txt', 'Pipfile', 'Pipfile.lock',
            'pyproject.toml', 'poetry.lock',
            'Gemfile', 'Gemfile.lock',
            'go.mod', 'go.sum',
            'composer.json', 'composer.lock'
        ]
        return any(file_path.endswith(dep_file) for dep_file in dependency_files)
    
    def analyze_dependency_change(self, diff_item):
        file_path = diff_item.a_path or diff_item.b_path
        change_type = diff_item.change_type
        if change_type == 'D':
            return {'type': 'deleted', 'file': file_path}
        elif change_type == 'A':
            return {'type': 'added', 'file': file_path}
        elif change_type == 'M':
            return self.analyze_file_content_changes(diff_item, file_path)
        return None

    def analyze_file_content_changes(self, diff_item, file_path):
        try:
            old_content = ""
            new_content = ""
            if diff_item.a_blob:
                old_content = diff_item.a_blob.data_stream.read().decode('utf-8', errors='ignore')
            if diff_item.b_blob:
                new_content = diff_item.b_blob.data_stream.read().decode('utf-8', errors='ignore')
            changes = self.dependency_parser.parse_changes(
                file_path, old_content, new_content
            )
            return {
                'type': 'modified',
                'file': file_path,
                'changes': changes
            }
        except Exception as e:
            return {
                'type': 'error',
                'file': file_path,
                'error': str(e)
            }
